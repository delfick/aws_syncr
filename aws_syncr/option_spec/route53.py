from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.errors import BadTemplate

from input_algorithms.errors import BadSpecValue
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb

from option_merge import MergedOptions
import six

class route_spec(sb.Spec):
    def normalise(self, meta, val):
        if 'use' in val:
            template = val['use']
            if template not in meta.everything['templates']:
                available = list(meta.everything['templates'].keys())
                raise BadTemplate("Template doesn't exist!", wanted=template, available=available, meta=meta)

            val = MergedOptions.using(meta.everything['templates'][template], val)

        formatted_string = sb.formatted(sb.string_spec(), MergedOptionStringFormatter)
        route_name = meta.key_names()['_key_name_0']

        val = sb.create_spec(DNSRoute
            , name = sb.overridden(route_name)
            , zone = formatted_string
            , record_type = sb.string_choice_spec(["CNAME"])
            , record_target = formatted_string
            ).normalise(meta, val)

        if not val.zone.endswith("."):
            val.zone = "{0}.".format(val.zone)

        if not isinstance(val.record_target, six.string_types):
            if not hasattr(val.record_target, "cname"):
                raise BadSpecValue("record_target must point at an object with a cname property", got=type(val.record_target), meta=meta)
            val.record_target = val.record_target.cname

        return val

class DNSRoutes(dictobj):
    fields = ['items']

    def sync_one(self, aws_syncr, amazon, route):
        """Make sure this role exists and has only what policies we want it to have"""
        route_info = amazon.route53.route_info(route.name, route.zone)
        target = route.record_target
        if callable(target):
            target = target(amazon)

        if not route_info:
            amazon.route53.create_route(route.name, route.zone, route.record_type, target)
        else:
            amazon.route53.modify_route(route_info, route.name, route.zone, route.record_type, target)

class DNSRoute(dictobj):
    fields = {
        "name": "The name of the record"
      , "zone": "The zone this record sits in"
      , "record_type": "The type of the record"
      , "record_target": "Where the record points at"
      }

def __register__():
    return {(100, "dns"): sb.container_spec(DNSRoutes, sb.dictof(sb.string_spec(), route_spec()))}

