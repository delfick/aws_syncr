from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.lambdas import Lambda
from aws_syncr.errors import BadTemplate

from Crypto.Util import Counter
from Crypto.Cipher import AES

from input_algorithms.spec_base import NotSpecified
from input_algorithms.validators import Validator
from input_algorithms.errors import BadSpecValue
from input_algorithms import spec_base as sb
from input_algorithms.spec_base import Spec
from input_algorithms.dictobj import dictobj

from option_merge import MergedOptions
import base64
import six

formatted_string = lambda: sb.formatted(sb.string_or_int_as_string_spec(), MergedOptionStringFormatter)

api_key_spec = lambda: sb.create_spec(ApiKey
    , name = formatted_string()
    , stages = sb.listof(formatted_string())
    )

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

certificate_spec = lambda: sb.create_spec(Certificate
    , name = sb.required(formatted_string())
    , body = sb.required(secret_spec())
    , key = sb.required(secret_spec())
    , chain = sb.required(secret_spec())
    )

custom_domain_name_spec = lambda: sb.create_spec(DomainName
    , name = formatted_string()
    , stage = formatted_string()
    , base_path = sb.defaulted(formatted_string(), "(none)")
    , certificate = sb.required(certificate_spec())
    )

mapping_spec = lambda: sb.create_spec(Mapping
    , content_type = sb.defaulted(formatted_string(), "application/json")
    , template = sb.defaulted(sb.string_spec(), "$input.json('$')")
    )

class post_lambda_spec(Spec):
    def normalise(self, meta, val):
        result = sb.create_spec(LambdaPostMethod
            , function = formatted_string()
            , location = formatted_string()
            , account = sb.optional_spec(formatted_string())
            , require_api_key = sb.defaulted(sb.boolean(), False)
            , mapping = sb.defaulted(mapping_spec(), Mapping("application/json", "$input.json('$')"))
            ).normalise(meta, val)

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

get_mock_spec = lambda : sb.create_spec(MockGetMethod
    , mapping = mapping_spec()
    , require_api_key = sb.defaulted(sb.boolean(), False)
    )

gateway_methods_spec = lambda: sb.create_spec(GatewayMethods
    , POST_lambda = sb.optional_spec(post_lambda_spec())
    , GET_mock = sb.optional_spec(get_mock_spec())
    )

gateway_resource_spec = lambda: sb.create_spec(GatewayResource
    , name = formatted_string()
    , methods = gateway_methods_spec()
    )

class ApiKey(dictobj):
    fields = ['name', 'stages']

class DomainName(dictobj):
    fields = ['name', 'stage', 'base_path', 'certificate']

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

class MethodExecutionResponse(dictobj):
    fields = ['responses']

class MethodExecutionIntegrationResponse(dictobj):
    fields = ['responses']

class LambdaIntegrationOptions(dictobj):
    fields = ['function', 'location', 'account']

    def put_kwargs(self, gateway_location, accounts, environment):
        if self.account is NotSpecified:
            account = accounts[environment]
        else:
            if self.account in accounts:
                account = accounts[self.account]
            else:
                account = self.account

        arn = "arn:aws:lambda:{0}:{1}:function:{2}".format(self.location, account, self.function)
        uri = "arn:aws:apigateway:{0}:lambda:path/2015-03-31/functions/{1}/invocations".format(gateway_location, arn)
        return {'uri': uri}

class LambdaPostMethod(dictobj):
    fields = ['function', 'location', 'account', 'require_api_key', 'mapping']
    http_method = "POST"

    @property
    def resource_options(self):
        return ResourceOptions(
              method_request = MethodExecutionRequest(require_api_key=self.require_api_key)
            , integration_request = MethodExecutionIntegrationRequest(integration_type="AWS", options=LambdaIntegrationOptions(function=self.function, location=self.location, account=self.account))
            , method_response = MethodExecutionResponse(responses={200: "application/json"})
            , integration_response = MethodExecutionIntegrationResponse(responses={200: [self.mapping]})
            )

class MockGetMethod(dictobj):
    fields = ['mapping', 'require_api_key']
    http_method = "GET"

    @property
    def resource_options(self):
        return ResourceOptions(
              method_request = MethodExecutionRequest(require_api_key=self.require_api_key)
            , integration_request = MethodExecutionIntegrationRequest(integration_type="MOCK")
            , method_response = MethodExecutionResponse(responses={200: "application/json"})
            , integration_response = MethodExecutionIntegrationResponse(responses={200: [self.mapping]})
            )

class GatewayMethods(dictobj):
    fields = ['POST_lambda', 'GET_mock']

class GatewayResource(dictobj):
    fields = ['name', 'methods']

    @property
    def method_options(self):
        for key, val in self.methods.items():
            if val is not NotSpecified:
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

        return sb.create_spec(Gateway
            , name = sb.overridden(gateway_name)
            , location = sb.required(formatted_string())
            , stages = sb.listof(formatted_string())
            , api_keys = sb.listof(api_key_spec())
            , domain_names = sb.listof(custom_domain_name_spec())
            , resources = sb.listof(gateway_resource_spec())
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

def __register__():
    return {"apigateway": sb.container_spec(Gateways, sb.dictof(sb.string_spec(), gateways_spec()))}

