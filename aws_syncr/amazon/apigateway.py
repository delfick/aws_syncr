from aws_syncr.amazon.common import AmazonMixin
from aws_syncr.errors import AwsSyncrError
from aws_syncr.differ import Differ

from input_algorithms.spec_base import NotSpecified
import requests
import boto3

import logging
import json
import six
import re

log = logging.getLogger("aws_syncr.amazon.apigateway")

class ApiGateway(AmazonMixin, object):
    def __init__(self, amazon, environment, accounts, dry_run):
        self.amazon = amazon
        self.dry_run = dry_run

        self.accounts = accounts
        self.account_id = accounts[environment]
        self.environment = environment

        self.client = lambda region: self.amazon.session.client('apigateway', region)

    def gateway_info(self, gateway_name, region):
        client = self.client(region)
        apis = client.get_rest_apis()

        for item in apis['items']:
            if item['name'] == gateway_name:
                identity = item['id']
                info = {"identity": identity, 'name': gateway_name}
                self.load_info(client, info)
                return info

    def load_info(self, client, info):
        """Fill out information about the gateway"""
        if 'identity' in info:
            info['stages'] = client.get_stages(restApiId=info['identity'])['item']
            info['resources'] = client.get_resources(restApiId=info['identity'])['items']
            for resource in info['resources']:
                for method in resource.get('resourceMethods', {}):
                    resource['resourceMethods'][method] = client.get_method(restApiId=info['identity'], resourceId=resource['id'], httpMethod=method)
                    for status_code, options in resource['resourceMethods'][method]['methodResponses'].items():
                        options.update(client.get_method_response(restApiId=info['identity'], resourceId=resource['id'], httpMethod=method, statusCode=status_code))

            info['deployment'] = client.get_deployments(restApiId=info['identity'])['items']
        else:
            for key in ('stages', 'resources', 'deployment'):
                info[key] = []

        info['api_keys'] = client.get_api_keys()['items']
        info['domains'] = client.get_domain_names()['items']
        for domain in info['domains']:
            domain['mappings'] = client.get_base_path_mappings(domainName=domain['domainName']).get('items', [])

    def create_gateway(self, name, location, stages, resources, api_keys, domains):
        client = self.client(location)

        with self.catch_boto_400("Couldn't Make gateway", gateway=name):
            for _ in self.change("+", "gateway", gateway=name):
                result = client.create_rest_api(name=name)
                info = {"identity": result['id']}
                self.load_info(client, info)
                self.modify_gateway(info, name, location, stages, resources, api_keys, domains)

        if self.dry_run:
            info = {}
            self.load_info(client, info)
            self.modify_gateway(info, name, location, stages, resources, api_keys, domains)

    def modify_gateway(self, gateway_info, name, location, stages, resources, api_keys, domains):
        client = self.client(location)

        current_domain_names = [domain['domainName'] for domain in gateway_info['domains']]
        missing = set(d.full_name for d in domains.values()) - set(current_domain_names)

        for domain in missing:
            with self.catch_boto_400("Couldn't Make domain", domain=domain):
                for _ in self.change("+", "domain", domain=domain):
                    certificate = [d for d in domains.values() if d.full_name == domain][0].certificate
                    client.create_domain_name(domainName=domain
                        , certificateName = certificate.name
                        , certificateBody = certificate.body.resolve(self.amazon)
                        , certificateChain = certificate.chain.resolve(self.amazon)
                        , certificatePrivateKey = certificate.key.resolve(self.amazon)
                        )

        self.modify_resources(client, gateway_info, location, name, resources)
        self.modify_stages(client, gateway_info, name, stages)

        self.modify_domains(client, gateway_info, name, domains)
        self.modify_api_keys(client, gateway_info, name, api_keys)

    def modify_resources(self, client, gateway_info, location, name, resources):
        current_resources = [r['path'] for r in gateway_info['resources']]
        wanted_resources = [r for r in resources]

        resources_by_path = dict((r['path'], r) for r in gateway_info['resources'])

        for_removal = [key for key in list(set(current_resources) - set(wanted_resources)) if key != '/']
        for_addition = [key for key in list(set(wanted_resources) - set(current_resources)) if key != '/']
        for_modification = list(set(['/'] + [r for r in wanted_resources if r in current_resources] + list(for_addition)))

        for path in for_removal:
            with self.catch_boto_400("Couldn't remove resource", gateway=name, resource=path):
                for _ in self.change("-", "gateway resource", gateway=name, resource=path):
                    resource_id = resources_by_path[path]['id']
                    client.delete_resource(restApiId=gateway_info['identity'], resourceId=resource_id)

        for path in for_addition:
            with self.catch_boto_400("Couldn't add resource", gateway=name, resource=path):
                for _ in self.change("+", "gateway resource", gateway=name, resource=path):
                    parent_id = resources_by_path['/']['id']
                    while path and path.startswith("/"):
                        path = path[1:]

                    upto = ['']
                    for part in path.split('/'):
                        upto.append(part)
                        if '/'.join(upto) not in resources_by_path:
                            info = client.create_resource(restApiId=gateway_info['identity'], parentId=parent_id, pathPart=part)
                            resources_by_path['/'.join(upto)] = info
                            parent_id = info['id']
                        else:
                            parent_id = resources_by_path['/'.join(upto)]['id']

        for path in for_modification:
            wanted_methods = {}
            if path in resources:
                wanted_methods = dict(resources[path].method_options)

            current_methods = resources_by_path.get(path, {}).get('resourceMethods', {})
            self.modify_resource_methods(client, gateway_info, location, name, path, current_methods, wanted_methods, resources_by_path)

    def modify_resource_methods(self, client, gateway_info, location, name, path, old_methods, new_methods, resources_by_path):
        for_removal = set(old_methods) - set(new_methods)
        for_addition = set(new_methods) - set(old_methods)
        for_modification = [method for method in new_methods if method in old_methods] + list(for_addition)

        for method in for_removal:
            with self.catch_boto_400("Couldn't remove method", gateway=name, resource=path, method=method):
                for _ in self.change("-", "gateway resource method", gateway=name, resource=path, method=method):
                    resource_id = resources_by_path[path]['id']
                    client.delete_method(restApiId=gateway_info['identity'], resourceId=resource_id, httpMethod=method)

        for method in for_addition:
            with self.catch_boto_400("Couldn't add method", gateway=name, resource=path, method=method):
                for _ in self.change("+", "gateway resource method", gateway=name, resource=path, method=method):
                    resource_id = resources_by_path[path]['id']
                    client.put_method(restApiId=gateway_info['identity'], resourceId=resource_id, httpMethod=method
                        , apiKeyRequired=new_methods[method].method_request.require_api_key
                        , authorizationType = "none"
                        )

        for method in for_modification:
            with self.catch_boto_400("Couldn't modify method", gateway=name, resource=path, method=method):
                if method in old_methods:
                    if old_methods[method]['apiKeyRequired'] != new_methods[method].method_request.require_api_key:
                        for _ in self.change("M", "gateway resource method", gateway=name, resource=path, method=method):
                            resource_id = resources_by_path[path]['id']
                            operations = [{"op": "replace", "path": "/apiKeyRequired", "value": str(new_methods[method].method_request.require_api_key)}]
                            client.update_method(restApiId=gateway_info['identity'], resourceId=resource_id, httpMethod=method, patchOperations=operations)

                self.modify_resource_method_status_codes(client, gateway_info, name, path, method, old_methods.get(method, {}), new_methods[method], resources_by_path)
                self.modify_resource_method_integration(client, gateway_info, location, name, path, method, old_methods.get(method, {}), new_methods[method], resources_by_path)
                self.modify_resource_method_integration_response(client, gateway_info, name, path, method, old_methods.get(method, {}), new_methods[method], resources_by_path)

    def modify_resource_method_status_codes(self, client, gateway_info, name, path, method, old_method, new_method, resources_by_path):
        old_status_codes = list(old_method.get('methodResponses', {}).keys())
        new_status_codes = list(str(st) for st in new_method.method_response.responses.keys())

        for_removal = set(old_status_codes) - set(new_status_codes)
        for_addition = set(new_status_codes) - set(old_status_codes)
        for_modification = [status_code for status_code in new_status_codes if status_code in old_status_codes]

        for status_code in for_removal:
            for _ in self.change("-", "gateway resource method response", gateway=name, resource=path, method=method, status_code=status_code):
                resource_id = resources_by_path[path]['id']
                client.delete_method_response(restApiId=gateway_info['identity'], resourceId=resource_id, httpMethod=method, statusCode=str(status_code))

        for status_code in for_addition:
            for _ in self.change("+", "gateway resource method response", gateway=name, resource=path, method=method, status_code=status_code):
                resource_id = resources_by_path[path]['id']
                models = {new_method.method_response.responses[int(status_code)]: "Empty"}
                models = dict((ct, model) for ct, model in models.items() if ct != "application/json")
                client.put_method_response(restApiId=gateway_info['identity'], resourceId=resource_id, httpMethod=method, statusCode=str(status_code)
                    , responseParameters = {}
                    , responseModels = models
                    )

        for status_code in for_modification:
            new = {new_method.method_response.responses[int(status_code)]: "Empty"}
            new = dict((ct, model) for ct, model in new.items() if ct != "application/json")

            old = old_method["methodResponses"][status_code].get("responseModels", {})
            changes = list(Differ.compare_two_documents(old, new))

            old = dict((ct.replace('/', '~1'), v) for ct, v in old.items())
            new = dict((ct.replace('/', '~1'), v) for ct, v in new.items())

            if changes:
                for_removal = set(old) - set(new)
                for_addition = set(new) - set(old)
                for_mod = [content_type for content_type in new if content_type in old]
                operations = []

                for content_type in for_removal:
                    operations.append({"op": "remove", "path": "/responseModels/{0}".format(content_type)})
                for content_type in for_addition:
                    operations.append({"op": "add", "path":"/responseModels/{0}".format(content_type), 'value': new[content_type]})
                for content_type in for_mod:
                    operations.append({"op": "replace", "path":"/responseModels/{0}".format(content_type), 'value': new[content_type]})

                for _ in self.change("M", "gateway resource method response model", gateway=name, resource=path, method=method, status_code=status_code, changes=changes):
                    resource_id = resources_by_path[path]['id']
                    client.update_method_response(restApiId=gateway_info['identity'], resourceId=resource_id, httpMethod=method, statusCode=str(status_code)
                        , patchOperations = operations
                        )

    def modify_resource_method_integration(self, client, gateway_info, location, name, path, method, old_method, new_method, resources_by_path):
        old_integration = old_method.get('methodIntegration', {})
        new_integration = new_method.integration_request

        new_kwargs = new_integration.put_kwargs(location, self.accounts, self.environment)
        old_kwargs = {} if not old_integration else {"type": old_integration["type"], "httpMethod": old_integration.get("httpMethod")}

        if old_integration and old_integration.get('requestTemplates'):
            old_kwargs['requestTemplates'] = old_integration['requestTemplates']
            for ct, template in list(old_kwargs['requestTemplates'].items()):
                if not template:
                    old_kwargs['requestTemplates'][ct] = ""

        if old_kwargs and old_kwargs['type'] == 'AWS':
            old_kwargs['uri'] = old_integration['uri']
        elif old_kwargs and old_kwargs['type'] == 'MOCK':
            old_kwargs["httpMethod"] = method

        changes = list(Differ.compare_two_documents(old_kwargs, new_kwargs))

        # Make sure our integration can be called by apigateway
        if 'identity' in gateway_info:
            arn = "arn:aws:execute-api:{0}:{1}:{2}/*/".format(location, self.account_id, gateway_info['identity'])
            new_integration.create_permissions(self.amazon, arn, name, self.accounts, self.environment)
        else:
            # Only possible in dry-run
            new_integration.announce_create_permissions(name, self.change)

        if changes:
            symbol = "+" if not old_integration else 'M'
            for _ in self.change(symbol, "gateway resource method integration request", gateway=name, resource=path, method=method, type=new_kwargs['type'], changes=changes):
                resource_id = resources_by_path[path]['id']
                integration_method = new_kwargs.pop("httpMethod")
                res = client.put_integration(restApiId=gateway_info['identity'], resourceId=resource_id, httpMethod=method
                    , integrationHttpMethod=integration_method
                    , **new_kwargs
                    )

                # put_integration removes the integration response so we take it away from our record
                # And let modify_resource_method_integration_response deal with the dissapearance
                if 'integrationResponses' in old_method.get("methodIntegration", {}):
                    del old_method["methodIntegration"]['integrationResponses']
                new_kwargs['responseTemplates'] = new_method.integration_response.responses.items()

    def modify_resource_method_integration_response(self, client, gateway_info, name, path, method, old_method, new_method, resources_by_path):
        old_integration = old_method.get('methodIntegration', {}).get("integrationResponses", {})
        wanted_integration = dict((str(s), v) for s, v in new_method.integration_response.responses.items())

        for_removal = set(old_integration) - set(wanted_integration)
        for_addition = set(wanted_integration) - set(old_integration)
        for_modification = [s for s in wanted_integration if s in old_integration]

        for status_code in for_removal:
            for _ in self.change("-", "gateway resource integration response", gateway=name, resource=path, method=method, status_code=status_code):
                resource_id = resources_by_path[path]['id']
                client.delete_integration_response(restApiId=gateway_info['identity'], resourceId=resource_id, httpMethod=method, statusCode=str(status_code))

        for status_code in for_addition:
            for _ in self.change("+", "gateway resource integration response", gateway=name, resource=path, method=method, status_code=status_code):
                resource_id = resources_by_path[path]['id']
                client.put_integration_response(restApiId=gateway_info['identity'], resourceId=resource_id, httpMethod=method, statusCode=str(status_code)
                    , responseTemplates = {} if not wanted_integration[status_code] else dict((m.content_type, m.template) for m in wanted_integration[status_code])
                    )

        # Modify response Templates
        for status_code in for_modification:
            old = old_integration[status_code].get('responseTemplates', {})
            for ct, template in old.items():
                if template is None:
                    old[ct] = ""

            new = {}
            if wanted_integration[status_code]:
                new = dict((m.content_type, m.template) for m in wanted_integration[status_code])
            changes = list(Differ.compare_two_documents(old, new))

            old = dict((ct.replace('/', '~1'), v) for ct, v in old.items())
            new = dict((ct.replace('/', '~1'), v) for ct, v in new.items())

            if changes:
                for_removal = set(old) - set(new)
                for_addition = set(new) - set(old)
                for_mod = [content_type for content_type in new if content_type in old]
                operations = []

                for content_type in for_removal:
                    operations.append({"op": "remove", "path": "/responseTemplates/{0}".format(content_type)})
                for content_type in for_addition:
                    operations.append({"op": "add", "path":"/responseTemplates/{0}".format(content_type), 'value': new[content_type]})
                for content_type in for_mod:
                    operations.append({"op": "replace", "path":"/responseTemplates/{0}".format(content_type), 'value': new[content_type]})

                for _ in self.change("M", "gateway resource integration response", gateway=name, resource=path, method=method, status_code=status_code, changes=changes):
                    resource_id = resources_by_path[path]['id']
                    client.update_integration_response(restApiId=gateway_info['identity'], resourceId=resource_id, httpMethod=method, statusCode=str(status_code)
                        , patchOperations = operations
                        )

    def modify_stages(self, client, gateway_info, name, stages):
        current_stages = [stage['stageName'] for stage in gateway_info['stages']]
        missing = set(stages) - set(current_stages)
        for_removal = set(current_stages) - set(stages)

        for stage in for_removal:
            with self.catch_boto_400("Couldn't remove stage", gateway=name, stage=stage):
                for _ in self.change("-", "gateway stage", gateway=name, stage=stage):
                    client.delete_stage(restApiId=gateway_info['identity'], stageName=stage)

        if 'identity' in gateway_info:
            deployments = client.get_deployments(restApiId=gateway_info['identity'])['items']
            stages = client.get_stages(restApiId=gateway_info['identity'])['item']
        else:
            stages = []
            deployments = []

        stage_deployments = [stage['deploymentId'] for stage in stages]
        for_removal = [deployment['id'] for deployment in deployments if deployment['id'] not in stage_deployments]
        for deployment in for_removal:
            with self.catch_boto_400("Couldn't remove deployment", gateway=name, deployment=deployment):
                for _ in self.change("-", "gateway deployment", gateway=name, deployment=deployment):
                    client.delete_deployment(restApiId=gateway_info['identity'], deploymentId=deployment)

        for stage in missing:
            with self.catch_boto_400("Couldn't add stage", gateway=name, stage=stage):
                for _ in self.change("+", "gateway stage", gateway=name, stage=stage):
                    if gateway_info.get('deployment'):
                        client.create_stage(restApiId=gateway_info['identity'], deploymentId=gateway_info['deployment'][0]['id'], stageName=stage)
                    else:
                        client.create_deployment(restApiId=gateway_info['identity'], stageName=stage)

    def modify_api_keys(self, client, gateway_info, name, api_keys):
        current = [ak['name'] for ak in gateway_info['api_keys']]
        wanted = [api_key.name for api_key in api_keys]

        for_addition = list(set(wanted) - set(current))
        for keyname in for_addition:
            with self.catch_boto_400("Couldn't add api keys", api_key=keyname):
                for _ in self.change("+", "gateway api key", gateway=name, api_key=keyname):
                    api_key = [api_key for api_key in api_keys if api_key.name == keyname][0]
                    client.create_api_key(name=keyname, enabled=True
                        , stageKeys=[{'restApiId': gateway_info['identity'], 'stageName': stage} for stage in api_key.stages]
                        )

        for_modification = [key for key in current if key in wanted]
        for keyname in for_modification:
            with self.catch_boto_400("Couldn't modify api keys", api_key=keyname):
                api_key = [api_key for api_key in api_keys if api_key.name == keyname][0]
                old_api_key = [ak for ak in gateway_info['api_keys'] if api_key['name'] == keyname][0]
                other_api_stages = [key for key in old_api_key['stageKeys'] if key[:key.find('/')] != gateway_info.get('identity')]

                operations = []

                new_stage_keys = ["{0}/{1}".format(gateway_info.get('identity'), key) for key in api_key.stages] + other_api_stages
                changes = list(Differ.compare_two_documents(sorted(old_api_key['stageKeys']), sorted(new_stage_keys)))

                if changes:
                    for_removal = set(old_api_key['stageKeys']) - set(new_stage_keys)
                    for key in for_removal:
                        operations.append({"op": "remove", "path": "/stages", "value": key})

                    for_addition = set(new_stage_keys) - set(old_api_key['stageKeys'])
                    for key in for_addition:
                        operations.append({"op": "add", "path": "/stages", "value": key})

                if operations:
                    for _ in self.change("M", "gateway api key", gateway=name, api_key=keyname, changes=changes):
                        client.update_api_key(apiKey=old_api_key['id'], patchOperations=operations)

    def modify_domains(self, client, gateway_info, name, domains):
        for domain in domains.values():
            found = []
            matches = [d for d in gateway_info['domains'] if d['domainName'] == domain.full_name]
            if matches:
                for mapping in matches[0]['mappings']:
                    if ('identity' in gateway_info and mapping['restApiId'] == gateway_info['identity']) or mapping['basePath'] == domain.base_path:
                        found.append(mapping)

            current = [dict((key, mapping.get(key)) for key in ('restApiId', 'stage', 'basePath')) for mapping in found]
            wanted = {'restApiId': gateway_info.get('identity', '<gateway id>'), 'stage': domain.stage, 'basePath': domain.base_path}

            if list(Differ.compare_two_documents(current, [wanted])):
                for_removal = [mapping for mapping in current if mapping['basePath'] != wanted['basePath']]
                for_addition = [mapping for mapping in [wanted] if mapping['basePath'] not in [m['basePath'] for m in found]]

                for_modification = []
                for new in [wanted]:
                    for old in found:
                        if old['basePath'] == new['basePath']:
                            for_modification.append((old, new))

                with self.catch_boto_400("Couldn't remove domain name bindings", gateway=name):
                    for mapping in for_removal:
                        for _ in self.change("-", "domain name gateway association", gateway=name, base_path=mapping['basePath']):
                            client.update_base_path_mapping(domainName=domain.full_name, basePath=mapping['basePath']
                                , patchOperations = [{"op": "remove", "path": "/"}]
                                )

                with self.catch_boto_400("Couldn't add domain name bindings", gateway=name):
                    for mapping in for_addition:
                        for _ in self.change("+", "domain name gateway association", gateway=name, base_path=mapping['basePath'], stage=mapping['stage']):
                            client.create_base_path_mapping(domainName=domain.full_name, basePath=mapping['basePath'], restApiId=gateway_info['identity'], stage=mapping['stage'])

                with self.catch_boto_400("Couldn't modify domain name bindings", gateway=name):
                    for old, new in for_modification:
                        changes = Differ.compare_two_documents(old, new)
                        for _ in self.change("M", "domain name gateway association", gateway=name, stage=new['stage'], base_path=new["basePath"], changes=changes):
                            operations = []

                            if old['restApiId'] != new['restApiId']:
                                operations.append({"op": "replace", "path": "/restapiId", "value": new['restApiId']})

                            if old.get('stage') != new.get('stage'):
                                operations.append({"op": "replace", "path": "/stage", "value": new['restApiId']})

                            client.update_base_path_mapping(domainName=domain.full_name, basePath=wanted['basePath'], patchOperations = operations)

    def deploy_stage(self, gateway_info, location, stage, description):
        client = self.client(location)
        for _ in self.change("D", "Deployment", gateway=gateway_info['name'], stage=stage):
            log.info("Deploying stage {0} for gateway {1}".format(stage, gateway_info['name']))
            client.create_deployment(restApiId=gateway_info['identity'], stageName=stage, description=description)
            print("https://{0}.execute-api.{1}.amazonaws.com/{2}".format(gateway_info['identity'], location, stage))

        previous_deployments = [s['deploymentId'] for s in gateway_info['stages'] if s['stageName'] == stage]
        if previous_deployments:
            for previous_deployment in previous_deployments:
                for _ in self.change("-", "deployment", gateway=gateway_info['name'], deployment=previous_deployment):
                    client.delete_deployment(restApiId=gateway_info['identity'], deploymentId=previous_deployment)

    def cname_for(self, gateway_location, record):
        with self.ignore_missing():
            return self.client(gateway_location).get_domain_name(domainName=record)['distributionDomainName']
        raise AwsSyncrError("Please do a sync first!")

    def test_stage(self, gateway_info, location, stage, method, endpoint, sample_event, desired_output_for_test):
        kwargs = {}
        if sample_event:
            if not isinstance(sample_event, six.string_types) and sample_event is not NotSpecified:
                kwargs['data'] = json.dumps(dict(sample_event.items()))

        # Find the url to use
        url = "https://{0}.execute-api.{1}.amazonaws.com/{2}".format(gateway_info['identity'], location, stage)
        for domain in gateway_info['domains']:
            if 'mappings' in domain:
                for mapping in domain['mappings']:
                    if mapping['restApiId'] == gateway_info['identity'] and mapping['stage'] == stage:
                        url = "https://{0}".format(domain['domainName'])
        url = "{0}{1}".format(url, endpoint)
        log.info("{0}ing to {1}".format(method, url))

        # Find an api-key
        api_key = ""
        stagekey = "{0}/{1}".format(gateway_info['identity'], stage)
        for api_key in gateway_info['api_keys']:
            if stagekey in api_key['stageKeys']:
                log.info("Found an api key to use ({0})".format(api_key['name']))
                api_key = api_key['id']
                break

        # Use the api key if it is required
        resource = [r for r in gateway_info['resources'] if r['path'] == endpoint][0]
        method_options = [o for m, o in resource['resourceMethods'].items() if m == method][0]
        if method_options['apiKeyRequired']:
            kwargs['headers'] = {'x-api-key': api_key}

        # make the request
        res = getattr(requests, method.lower())(url, **kwargs)

        print("Got result with status_code={0}".format(res.status_code))
        print(res.content.decode('utf-8'))

        if res.status_code != 200:
            # Say we failed if status code isn't 200
            return False
        else:
            # Say we succeeded if we meet the desired_output_for_test
            if desired_output_for_test and desired_output_for_test is not NotSpecified:
                if isinstance(desired_output_for_test, six.string_types):
                    content = res.content.decode('utf-8')
                    if not re.match(desired_output_for_test, content):
                        print("content '{0}' does not match pattern '{1}'".format(content, desired_output_for_test))
                        return False

                else:
                    content = json.loads(res.content.decode('utf-8'))
                    if any(key not in content or content[key] != val for key, val in desired_output_for_test.items()):
                        print("Not all of the values match our desired output of '{0}'".format(desired_output_for_test))
                        return False

        return True

