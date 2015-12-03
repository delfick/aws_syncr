from aws_syncr.errors import BadTemplate, UnknownStage, UnsyncedGateway, UnknownEndpoint, AwsSyncrError
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.lambdas import Lambda

from Crypto.Util import Counter
from Crypto.Cipher import AES

from input_algorithms.spec_base import NotSpecified
from input_algorithms.validators import Validator
from input_algorithms.errors import BadSpecValue
from input_algorithms import spec_base as sb
from input_algorithms.spec_base import Spec
from input_algorithms.dictobj import dictobj

from option_merge import MergedOptions
from textwrap import dedent
import logging
import base64
import json
import sys
import six

log = logging.getLogger("aws_syncr.option_spec.apigateway")

formatted_string = lambda: sb.formatted(sb.string_or_int_as_string_spec(), MergedOptionStringFormatter)

api_key_spec = lambda: sb.create_spec(ApiKey
    , name = formatted_string()
    , stages = sb.listof(formatted_string())
    )

class formatted_dictionary(sb.Spec):
    def normalise(self, meta, val):
        val = sb.dictionary_spec().normalise(meta, val)
        return self.formatted_dict(meta, val)

    def formatted_dict(self, meta, val, chain=None):
        result = {}
        for key, val in val.items():
            if type(val) is dict:
                result[key] = self.formatted_dict(meta.at(key), val, chain)
            elif isinstance(val, six.string_types):
                result[key] = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter).normalise(meta.at(key), val)
            else:
                result[key] = val
        return result

class valid_secret(Validator):
    def validate(self, meta, val):
        val = sb.dictionary_spec().normalise(meta, val)
        if 'plain' in val and 'kms' in val:
            raise BadSpecValue("Please only specify plain or kms", got=list(val.keys()), meta=meta)

        if 'plain' not in val and 'kms' not in val:
            raise BadSpecValue("Please specify plain or kms", got=list(val.keys()), meta=meta)

        if 'kms' in val and ('location' not in val or 'kms_data_key' not in val):
            raise BadSpecValue("Please specify location and kms_data_key if you specify kms", got=list(val.keys()), meta=meta)

        return val

secret_spec = lambda: sb.create_spec(Secret
    , valid_secret()

    , plain = sb.optional_spec(formatted_string())
    , kms = sb.optional_spec(formatted_string())
    , location = sb.optional_spec(formatted_string())
    , kms_data_key = sb.optional_spec(formatted_string())
    )

class certificate_spec(Spec):
    def normalise(self, meta, val):
        if isinstance(val, six.string_types):
            val = formatted_string().normalise(meta, val)

        return sb.create_spec(Certificate
            , name = sb.required(formatted_string())
            , body = sb.required(secret_spec())
            , key = sb.required(secret_spec())
            , chain = sb.required(secret_spec())
            ).normalise(meta, val)

class custom_domain_name_spec(Spec):
    def setup(self, gateway_location):
        self.gateway_location = gateway_location

    def normalise(self, meta, val):
        name = meta.key_names()["_key_name_0"]
        result = sb.create_spec(DomainName
            , name = sb.overridden(name)
            , gateway_location = sb.overridden(self.gateway_location)
            , zone = formatted_string()
            , stage = formatted_string()
            , base_path = sb.defaulted(formatted_string(), "(none)")
            , certificate = sb.required(certificate_spec())
            ).normalise(meta, val)

        while result.zone and result.zone.endswith("."):
            result.zone = result.zone[:-1]

        return result

formatted_dictionary_or_string = lambda : sb.match_spec(
      (six.string_types, formatted_string())
    , fallback = sb.dictof(sb.string_spec(), formatted_string())
    )

mapping_spec = lambda: sb.create_spec(Mapping
    , content_type = sb.defaulted(formatted_string(), "application/json")
    , template = sb.defaulted(formatted_dictionary_or_string(), "$input.json('$')")
    )

class aws_resource_spec(Spec):
    def setup(self, method, resource_name):
        self.method = method
        self.resource_name = resource_name

    def normalise(self, meta, val):
        result = sb.create_spec(LambdaMethod
            , http_method = sb.overridden(self.method)
            , resource_name = sb.overridden(self.resource_name)

            , function = formatted_string()
            , location = formatted_string()
            , account = sb.optional_spec(formatted_string())
            , require_api_key = sb.defaulted(sb.boolean(), False)
            , request_mapping = sb.defaulted(mapping_spec(), Mapping("application/json", ""))
            , mapping = sb.defaulted(mapping_spec(), Mapping("application/json", "$input.json('$')"))
            , sample_event = sb.or_spec(formatted_dictionary(), sb.string_spec())
            , desired_output_for_test = sb.or_spec(formatted_dictionary(), sb.string_spec())
            ).normalise(meta, val)

        for key in ('sample_event', 'desired_output_for_test'):
            if isinstance(result[key], six.string_types):
                v = result[key]
                if v.startswith("{") and v.endswith("}"):
                    v = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter).normalise(meta.at(key), v)
                    result[key] = v

        function = result.function
        location = None

        if result.location is not NotSpecified and location is not None:
            raise BadSpecValue("Please don't specify a defined lambda function and location at the same time", meta=meta)

        if not isinstance(function, six.string_types):
            location = function.location
            function = function.name

        if location is None and result.location is NotSpecified:
            raise BadSpecValue("Location is a required key!", meta=meta)

        result.function = function
        result.location = location
        return result

class mock_resource_spec(Spec):
    def setup(self, method, resource_name):
        self.method = method
        self.resource_name = resource_name

    def normalise(self, meta, val):
        return sb.create_spec(MockMethod
            , http_method = sb.overridden(self.method)
            , resource_name = sb.overridden(self.resource_name)

            , request_mapping = sb.defaulted(mapping_spec(), Mapping("application/json", '{"statusCode": 200}'))
            , mapping = mapping_spec()
            , require_api_key = sb.defaulted(sb.boolean(), False)
            , sample_event = sb.or_spec(sb.dictionary_spec(), sb.string_spec())
            , desired_output_for_test = sb.or_spec(sb.dictionary_spec(), sb.string_spec())
            ).normalise(meta, val)

        for key in ('sample_event', 'desired_output_for_test'):
            if isinstance(result[key], six.string_types):
                v = result[key]
                if v.startswith("{") and v.endswith("}"):
                    v = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter).normalise(meta.at(key), v)
                    result[key] = v

class gateway_methods_spec(Spec):
    def normalise(self, meta, val):
        # Make sure we have integration
        integration_spec = sb.required(sb.string_choice_spec(["aws", "mock"]))
        sb.set_options(integration=integration_spec).normalise(meta, val)

        # Determine the http method and resource name
        method = meta.key_names()["_key_name_0"]
        resource_name = meta.key_names()["_key_name_2"]

        # We have integration if no exception was raised
        if val['integration'] == "aws":
            return aws_resource_spec(method, resource_name).normalise(meta, val)
        else:
            return mock_resource_spec(method, resource_name).normalise(meta, val)

gateway_resource_spec = lambda: sb.create_spec(GatewayResource
    , methods = sb.dictof(sb.string_spec(), gateway_methods_spec())
    )

class ApiKey(dictobj):
    fields = ['name', 'stages']

class DomainName(dictobj):
    fields = ['name', 'zone', 'stage', 'base_path', 'certificate', 'gateway_location']

    @property
    def full_name(self):
        return "{0}.{1}".format(self.name, self.zone)

    def cname(self, amazon):
        return amazon.apigateway.cname_for(self.gateway_location, self.full_name)

class Mapping(dictobj):
    fields = ['content_type', 'template']

class ResourceOptions(dictobj):
    fields = ['method_request', 'integration_request', 'method_response', 'integration_response']

class MethodExecutionRequest(dictobj):
    fields = ['require_api_key']

class MethodExecutionIntegrationRequest(dictobj):
    fields = ['integration_type', ('options', None)]

    def put_kwargs(self, gateway_location, accounts, environment):
        if self.options is None:
            kwargs = {}
        else:
            kwargs = self.options.put_kwargs(gateway_location, accounts, environment)
        kwargs['type'] = self.integration_type
        return kwargs

    def create_permissions(self, amazon, gateway_arn, gateway_name, accounts, environment):
        if self.integration_type == "AWS":
            self.options.create_permissions(amazon, gateway_arn, gateway_name, accounts, environment)

    def announce_create_permissions(self, gateway_name, changer):
        if self.integration_type == "AWS":
            self.options.announce_create_permissions(gateway_name, changer)

class MethodExecutionResponse(dictobj):
    fields = ['responses']

class MethodExecutionIntegrationResponse(dictobj):
    fields = ['responses']

class LambdaIntegrationOptions(dictobj):
    fields = ['http_method', 'resource_name', 'function', 'location', 'account', 'mapping']

    def arn(self, accounts, environment):
        if self.account is NotSpecified:
            account = accounts[environment]
        else:
            if self.account in accounts:
                account = accounts[self.account]
            else:
                account = self.account

        return "arn:aws:lambda:{0}:{1}:function:{2}".format(self.location, account, self.function)

    def put_kwargs(self, gateway_location, accounts, environment):
        arn = self.arn(accounts, environment)
        uri = "arn:aws:apigateway:{0}:lambda:path/2015-03-31/functions/{1}/invocations".format(gateway_location, arn)
        template = self.mapping.template
        if not isinstance(template, six.string_types):
            template = json.dumps(template, sort_keys=True)
        request_templates = {self.mapping.content_type: template}
        return {'uri': uri, 'requestTemplates': request_templates, 'httpMethod': "POST"}

    def create_permissions(self, amazon, gateway_arn, gateway_name, accounts, environment):
        arn = self.arn(accounts, environment)
        gateway_arn = "{0}{1}{2}".format(gateway_arn, self.http_method, self.resource_name)
        amazon.lambdas.modify_resource_policy_for_gateway(arn, self.location, gateway_arn, gateway_name)

    def announce_create_permissions(self, gateway_name, changer):
        # Purely for announcing the change we want to make
        for _ in changer("M", "Lambda resource policy", gateway=gateway_name, function=self.function):
            pass

class MockIntegrationOptions(dictobj):
    fields = ['http_method', 'mapping']

    def put_kwargs(self, gateway_location, accounts, environment):
        template = self.mapping.template
        if not isinstance(template, six.string_types):
            template = json.dumps(template, sort_keys=True)
        return {'requestTemplates': {self.mapping.content_type: template}, 'httpMethod': self.http_method}

class LambdaMethod(dictobj):
    fields = ['http_method', 'resource_name', 'function', 'location', 'account', 'require_api_key', 'request_mapping', 'mapping', 'sample_event', 'desired_output_for_test']

    @property
    def resource_options(self):
        return ResourceOptions(
              method_request = MethodExecutionRequest(require_api_key=self.require_api_key)
            , integration_request = MethodExecutionIntegrationRequest(integration_type="AWS", options=LambdaIntegrationOptions(mapping=self.request_mapping, http_method=self.http_method, resource_name=self.resource_name, function=self.function, location=self.location, account=self.account))
            , method_response = MethodExecutionResponse(responses={200: self.mapping.content_type})
            , integration_response = MethodExecutionIntegrationResponse(responses={200: [self.mapping]})
            )

class MockMethod(dictobj):
    fields = ['http_method', 'resource_name', 'request_mapping', 'mapping', 'require_api_key', 'sample_event', 'desired_output_for_test']

    @property
    def resource_options(self):
        return ResourceOptions(
              method_request = MethodExecutionRequest(require_api_key=self.require_api_key)
            , integration_request = MethodExecutionIntegrationRequest(integration_type="MOCK", options=MockIntegrationOptions(http_method=self.http_method, mapping=self.request_mapping))
            , method_response = MethodExecutionResponse(responses={200: "application/json"})
            , integration_response = MethodExecutionIntegrationResponse(responses={200: [self.mapping]})
            )

class GatewayResource(dictobj):
    fields = ['methods']

    @property
    def method_options(self):
        for key, val in self.methods.items():
            yield val.http_method, val.resource_options

class gateways_spec(Spec):
    def normalise(self, meta, val):
        if 'use' in val:
            template = val['use']
            if template not in meta.everything['templates']:
                available = list(meta.everything['templates'].keys())
                raise BadTemplate("Template doesn't exist!", wanted=template, available=available, meta=meta)

            val = MergedOptions.using(meta.everything['templates'][template], val)

        gateway_name = meta.key_names()['_key_name_0']
        gateway_location = formatted_string().normalise(meta.at('location'), val.get('location', ''))

        return sb.create_spec(Gateway
            , name = sb.overridden(gateway_name)
            , location = sb.required(formatted_string())
            , stages = sb.listof(formatted_string())
            , api_keys = sb.listof(api_key_spec())
            , domain_names = sb.dictof(sb.string_spec(), custom_domain_name_spec(gateway_location))
            , resources = sb.dictof(sb.string_spec(), gateway_resource_spec())
            ).normalise(meta, val)

class Secret(dictobj):
    fields = ['plain', 'kms', 'location', 'kms_data_key']

    def resolve(self, amazon):
        if self.plain is not NotSpecified:
            return self.plain
        else:
            data_key = amazon.kms.decrypt(self.location, self.kms_data_key)
            counter = Counter.new(128)
            decryptor = AES.new(data_key[:32], AES.MODE_CTR, counter=counter)
            return decryptor.decrypt(base64.b64decode(self.kms)).decode('utf-8')

class Certificate(dictobj):
    fields = ['name', 'body', 'key', 'chain']

class Gateways(dictobj):
    fields = ['items']

    def sync_one(self, aws_syncr, amazon, gateway):
        """Make sure this gateway exists and has only attributes we want it to have"""
        gateway_info = amazon.apigateway.gateway_info(gateway.name, gateway.location)
        if not gateway_info:
            amazon.apigateway.create_gateway(gateway.name, gateway.location, gateway.stages, gateway.resources, gateway.api_keys, gateway.domain_names)
        else:
            amazon.apigateway.modify_gateway(gateway_info, gateway.name, gateway.location, gateway.stages, gateway.resources, gateway.api_keys, gateway.domain_names)

class Gateway(dictobj):
    fields = {
          'name': "Name of the gateway"
        , 'location': "The region the gateway exists in"
        , 'stages': "The deployment stages for the gateway"
        , 'resources': "The resources in the gateway"
        , "api_keys": "The api keys to associate with this gateway"
        , "domain_names": "The custom domain names to associate with the gateway"
        }

    @property
    def stage_names(self):
        return list(self.stages)

    def gateway_info(self, amazon):
        if not getattr(self, "_gateway_info", None):
            self._gateway_info = amazon.apigateway.gateway_info(self.name, self.location)
        return self._gateway_info

    def validate_stage(self, amazon, stage):
        if stage not in self.stage_names:
            raise UnknownStage("Please specify a defined stage", available=self.stage_names)

        log.info("Finding information for gateway {0}".format(self.name))
        if not self.gateway_info(amazon):
            raise UnsyncedGateway("Please do a sync before trying to deploy your gateway!")

        defined_stages = [stage['stageName'] for stage in self.gateway_info(amazon)['stages']]
        if stage not in defined_stages:
            raise UnknownStage("Please do a sync before trying to deploy your gateway!", only_have=defined_stages)

    def find_sample_event(self, amazon, method, endpoint):
        available = list(self.resources.keys())
        if endpoint not in available:
            raise UnknownEndpoint("Please specify an endpoint that exists", got=endpoint, available=available)

        methods = self.resources[endpoint].methods
        if method not in self.resources[endpoint].methods:
            raise UnknownEndpoint("Please specify a valid http_method for this endpoint", got=method, available=list(methods.keys()))

        return self.resources[endpoint].methods[method].sample_event, self.resources[endpoint].methods[method].desired_output_for_test

    def available_methods_and_endpoints(self):
        for endpoint, resource in self.resources.items():
            for method in resource.methods:
                yield method, endpoint

    def deploy(self, aws_syncr, amazon, stage):
        self.validate_stage(amazon, stage)
        amazon.apigateway.deploy_stage(self.gateway_info(amazon), self.location, stage, aws_syncr.extra)

    def test(self, aws_syncr, amazon, stage):
        endpoint = aws_syncr.extra.strip()
        if not endpoint or " " not in endpoint:
            options = sorted("{0} {1}".format(m, e) for m, e in list(self.available_methods_and_endpoints()))
            raise AwsSyncrError("{0}\n".format(dedent("""
            Please specify ' -- <http_method> <endpoint> ' at the end of the command

            For example:

                {0} -- <http_method> <endpoint>

            Where the available options are:

                {1}

            """.format(' '.join(sys.argv), '\n\t\t'.join(options)).strip()
            )))

        method, endpoint = endpoint.split(" ", 1)
        sample_event, desired_output_for_test = self.find_sample_event(amazon, method, endpoint)

        self.validate_stage(amazon, stage)
        return amazon.apigateway.test_stage(self.gateway_info(amazon), self.location, stage, method, endpoint, sample_event, desired_output_for_test)

def __register__():
    return {(99, "apigateway"): sb.container_spec(Gateways, sb.dictof(sb.string_spec(), gateways_spec()))}

