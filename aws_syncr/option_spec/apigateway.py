from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.lambdas import Lambda
from aws_syncr.errors import BadTemplate

from input_algorithms.spec_base import NotSpecified
from input_algorithms.errors import BadSpecValue
from input_algorithms import spec_base as sb
from input_algorithms.spec_base import Spec
from input_algorithms.dictobj import dictobj

from option_merge import MergedOptions
import six

formatted_string = lambda: sb.formatted(sb.string_or_int_as_string_spec(), MergedOptionStringFormatter)

api_key_spec = lambda: sb.create_spec(ApiKey
    , name = formatted_string()
    , stages = sb.listof(formatted_string())
    )

custom_domain_name_spec = lambda: sb.create_spec(DomainName
    , name = formatted_string()
    , stage = formatted_string()
    , base_path = sb.defaulted(formatted_string(), "(none)")
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
    fields = ['name', 'stage', 'base_path']

class Mapping(dictobj):
    fields = ['content_type', 'template']

class ResourceOptions(dictobj):
    fields = ['method_request', 'integration_request', 'method_response', 'integration_response']

class MethodExecutionRequest(dictobj):
    fields = ['require_api_key']

class MethodExecutionIntegrationRequest(dictobj):
    fields = ['function', 'location']

class MethodExecutionResponse(dictobj):
    fields = ['responses']

class MethodExecutionIntegrationResponse(dictobj):
    fields = ['responses']

class LambdaIntegrationOptions(dictobj):
    fields = ['function', 'location']

class LambdaPostMethod(dictobj):
    fields = ['function', 'location', 'require_api_key', 'mapping']

    @property
    def resource_options(self):
        return ResourceOptions(
              method_request = MethodExecutionRequest(require_api_key=self.require_api_key)
            , integration_request = MethodExecutionIntegrationRequest(integration_type="lambda", options=LambdaIntegrationOptions(function=self.function, location=self.location))
            , method_response = MethodExecutionResponse(responses={200: "application/json"})
            , integration_response = MethodExecutionIntegrationResponse(responses={200: self.mapping})
            )

class MockGetMethod(dictobj):
    fields = ['mapping', 'require_api_key']

    @property
    def resource_options(self):
        return ResourceOptions(
              method_request = MethodExecutionRequest(require_api_key=self.require_api_key)
            , integration_request = MethodExecutionIntegrationRequest(integration_type="mock")
            , method_response = MethodExecutionResponse(responses={200: "application/json"})
            , integration_response = MethodExecutionIntegrationResponse(responses={200: self.mapping})
            )

class GatewayMethods(dictobj):
    fields = ['POST_lambda', 'GET_mock']

class GatewayResource(dictobj):
    fields = ['name', 'methods']

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

