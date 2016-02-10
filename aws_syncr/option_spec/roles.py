from aws_syncr.option_spec.statements import trust_statement_spec, permission_statement_spec, permission_dict, trust_dict
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.documents import Document
from aws_syncr.errors import BadOption, BadTemplate

from input_algorithms.spec_base import NotSpecified
from input_algorithms.errors import BadSpecValue
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

        original_permission = sb.listof(permission_dict()).normalise(meta.at("permission"), NotSpecified if "permission" not in val else val["permission"])
        deny_permission = sb.listof(permission_dict(effect='Deny')).normalise(meta.at("deny_permission"), NotSpecified if "deny_permission" not in val else val["deny_permission"])
        allow_permission = sb.listof(permission_dict(effect='Allow')).normalise(meta.at("allow_permission"), NotSpecified if "allow_permission" not in val else val["allow_permission"])

        allow_to_assume_me = sb.listof(trust_dict("principal")).normalise(meta.at("allow_to_assume_me"), val.get("allow_to_assume_me", NotSpecified))
        disallow_to_assume_me = sb.listof(trust_dict("notprincipal")).normalise(meta.at("disallow_to_assume_me"), val.get("disallow_to_assume_me", NotSpecified))

        if not allow_to_assume_me and not disallow_to_assume_me:
            raise BadSpecValue("Roles must have either allow_to_assume_me or disallow_to_assume_me specified", meta=meta)

        val = val.wrapped()
        val['trust'] = allow_to_assume_me + disallow_to_assume_me
        val['permission'] = original_permission + deny_permission + allow_permission
        return sb.create_spec(Role
            , name = sb.overridden(role_name)
            , description = formatted_string
            , attached_policies = sb.listof(formatted_string)
            , trust = sb.container_spec(Document, sb.listof(trust_statement_spec('role', role_name)))
            , permission = sb.container_spec(Document, sb.listof(permission_statement_spec('role', role_name)))
            , make_instance_profile = sb.defaulted(sb.boolean(), False)
            ).normalise(meta, val)

class Roles(dictobj):
    fields = ['items']

    def sync_one(self, aws_syncr, amazon, role):
        """Make sure this role exists and has only what policies we want it to have"""
        trust_document = role.trust.document
        attached_policies = role.attached_policies
        permission_document = role.permission.document
        policy_name = "syncr_policy_{0}".format(role.name.replace('/', '__'))

        role_info = amazon.iam.role_info(role.name)
        if not role_info:
            amazon.iam.create_role(role.name, trust_document, policies={policy_name: permission_document}, attached_policies=attached_policies)
        else:
            amazon.iam.modify_role(role_info, role.name, trust_document, policies={policy_name: permission_document}, attached_policies=attached_policies)

        if role.make_instance_profile:
            amazon.iam.make_instance_profile(role.name)

class Role(dictobj):
    fields = {
        "name": "The name of the role"
      , "description": "The description of the role!"
      , "make_instance_profile": "Whether to make an instance profile for this role as well"

      , "trust": "The trust document"
      , "permission": "Combination of allow_permission and deny_permission"
      , "attached_policies": "List of managed policies to attach to the role"
      }

def __register__():
    return {(21, "roles"): sb.container_spec(Roles, sb.dictof(sb.string_spec(), role_spec()))}

