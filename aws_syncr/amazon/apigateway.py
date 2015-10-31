from aws_syncr.amazon.common import AmazonMixin
from aws_syncr.errors import MissingDomain
from aws_syncr.differ import Differ

import boto3

import logging
import json

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
                info = {"identity": identity}
                self.load_info(client, info)
                return info

    def load_info(self, client, info):
        """Fill out information about the gateway"""
        if 'identity' in info:
            info['stages'] = client.get_stages(restApiId=info['identity'])['item']
            info['resources'] = client.get_resources(restApiId=info['identity'])['items']
            info['deployment'] = client.get_deployments(restApiId=info['identity'])['items']

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
        current_domain_names = [domain['domainName'] for domain in gateway_info['domains']]
        missing = set(d.name for d in domains) - set(current_domain_names)
        if missing:
            raise MissingDomain("Please manually add the domains in the console (it requires giving ssl certificates)", missing=list(missing))

        client = self.client(location)
        if 'identity' in gateway_info:
            self.modify_stages(client, gateway_info, name, stages)

        self.modify_domains(client, gateway_info, name, domains)
        self.modify_api_keys(client, gateway_info, name, api_keys)

    def modify_stages(self, client, gateway_info, name, stages):
        current_stages = [stage['stageName'] for stage in gateway_info['stages']]
        missing = set(stages) - set(current_stages)
        for_removal = set(current_stages) - set(stages)

        for stage in for_removal:
            with self.catch_boto_400("Couldn't remove stage", gateway=name, stage=stage):
                for _ in self.change("-", "gateway stage", gateway=name, stage=stage):
                    client.delete_stage(restApiId=gateway_info['identity'], stageName=stage)

        deployments = client.get_deployments(restApiId=gateway_info['identity'])['items']
        stages = client.get_stages(restApiId=gateway_info['identity'])['item']
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
                old_api_key = [api_key for api_key in gateway_info['api_keys'] if api_key['name'] == keyname][0]
                other_api_stages = [key for key in old_api_key['stageKeys'] if key[:key.find('/')] != gateway_info['identity']]

                operations = []

                new_stage_keys = ["{0}/{1}".format(gateway_info['identity'], key) for key in api_key.stages] + other_api_stages
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
        for domain in domains:
            found = []
            matches = [d for d in gateway_info['domains'] if d['domainName'] == domain.name]
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
                            client.update_base_path_mapping(domainName=name, basePath=mapping['basePath']
                                , patchOperations = [{"op": "remove", "path": "/"}]
                                )

                with self.catch_boto_400("Couldn't add domain name bindings", gateway=name):
                    for mapping in for_addition:
                        for _ in self.change("+", "domain name gateway association", gateway=name, base_path=mapping['basePath'], stage=mapping['stage']):
                            client.create_base_path_mapping(domainName=name, basePath=mapping['basePath'], restApiId=gateway_info['identity'], stage=mapping['stage'])

                with self.catch_boto_400("Couldn't modify domain name bindings", gateway=name):
                    for old, new in for_modification:
                        changes = Differ.compare_two_documents(old, new)
                        for _ in self.change("M", "domain name gateway association", gateway=name, stage=new['stage'], base_path=new["basePath"], changes=changes):
                            operations = []

                            if old['restApiId'] != new['restApiId']:
                                operations.append({"op": "replace", "path": "/restApiId", "value": new['restApiId']})

                            if old.get('stage') != new.get('stage'):
                                operations.append({"op": "replace", "path": "/stage", "value": new['restApiId']})

                            client.update_base_path_mapping(domainName=name, basePath=wanted['basePath'], patchOperations = operations)
