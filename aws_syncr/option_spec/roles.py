from aws_syncr.option_spec.statements import trust_statement_spec, permission_statement_spec, permission_dict, trust_dict
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.documents import Document
from aws_syncr.errors import BadOption, BadTemplate

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb

from option_merge import MergedOptions
import logging
import six

log = logging.getLogger("aws_syncr.option_spec.roles")

class role_spec(object):
    def normalise(self, meta, val):
        if 'use' in val:
            template = val['use']
            if template not in meta.everything['templates']:
                available = list(meta.everything['templates'].keys())
                raise BadTemplate("Template doesn't exist!", wanted=template, available=available, meta=meta)

            val = MergedOptions.using(meta.everything['templates'][template], val)

        formatted_string = sb.formatted(sb.string_spec(), MergedOptionStringFormatter, expected_type=six.string_types)
        role_name = meta.key_names()['_key_name_0']

        original_permission = sb.listof(permission_dict()).normalise(meta.at("permission"), val.get("permission", NotSpecified))
        deny_permission = sb.listof(permission_dict(effect='Deny')).normalise(meta.at("deny_permission"), val.get("deny_permission", NotSpecified))
        allow_permission = sb.listof(permission_dict(effect='Allow')).normalise(meta.at("allow_permission"), val.get("allow_permission", NotSpecified))

        allow_to_assume_me = sb.listof(trust_dict("principal")).normalise(meta.at("allow_to_assume_me"), val.get("allow_to_assume_me", NotSpecified))
        disallow_to_assume_me = sb.listof(trust_dict("notprincipal")).normalise(meta.at("disallow_to_assume_me"), val.get("disallow_to_assume_me", NotSpecified))

        val['trust'] = allow_to_assume_me + disallow_to_assume_me
        val['permission'] = original_permission + deny_permission + allow_permission
        return sb.create_spec(Role
            , name = sb.overridden(role_name)
            , description = formatted_string
            , trust = sb.container_spec(Document, sb.listof(trust_statement_spec('role', role_name)))
            , permission = sb.container_spec(Document, sb.listof(permission_statement_spec('role', role_name)))
            , make_instance_profile = sb.defaulted(sb.boolean(), False)
            ).normalise(meta, val)

class Roles(dictobj):
    fields = ['roles']

class Role(dictobj):
    fields = {
        "name": "The name of the role"
      , "description": "The description of the role!"
      , "make_instance_profile": "Whether to make an instance profile for this role as well"

      , "trust": "The trust document"
      , "permission": "Combination of allow_permission and deny_permission"
      }

