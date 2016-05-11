from aws_syncr.option_spec.statements import grant_statement_spec, resource_policy_statement_spec
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.documents import Document
from aws_syncr.errors import BadTemplate

from input_algorithms import spec_base as sb
from input_algorithms.spec_base import Spec
from input_algorithms.dictobj import dictobj

from option_merge import MergedOptions
import six

class encryption_keys_spec(Spec):
    def normalise(self, meta, val):
        if 'use' in val:
            template = val['use']
            if template not in meta.everything['templates']:
                available = list(meta.everything['templates'].keys())
                raise BadTemplate("Template doesn't exist!", wanted=template, available=available, meta=meta)

            val = MergedOptions.using(meta.everything['templates'][template], val)

        formatted_string = sb.formatted(sb.string_or_int_as_string_spec(), MergedOptionStringFormatter, expected_type=six.string_types)
        key_name = meta.key_names()['_key_name_0']

        key = sb.create_spec(EncryptionKey
            , name = sb.overridden(key_name)
            , location = sb.required(formatted_string)
            , description = formatted_string
            , grant = sb.listof(grant_statement_spec('key', key_name))
            , admin_users = sb.listof(sb.any_spec())
            , permission = sb.listof(sb.dictionary_spec())
            , no_root_access = sb.defaulted(sb.boolean(), False)
            ).normalise(meta, val)

        statements = key.permission
        if not key.no_root_access:
            statements.append({"principal": {"iam": "root"}, "action": "kms:*", "resource": "*", "Sid": ""})

        if key.admin_users:
            for admin_user in key.admin_users:
                statements.append({"principal": admin_user, "action": "kms:*", "resource": { "kms": "__self__" }, "Sid": ""})

        key.policy = sb.container_spec(Document, sb.listof(resource_policy_statement_spec('key', key_name))).normalise(meta.at("admin_users"), statements)
        return key

class EncryptionKeys(dictobj):
    fields = ["items"]

    def sync_one(self, aws_syncr, amazon, key):
        """Make sure this key is as defined"""
        key_info = amazon.kms.key_info(key.name, key.location)
        if not key_info:
            amazon.kms.create_key(key.name, key.description, key.location, key.grant, key.policy.document)
        else:
            amazon.kms.modify_key(key_info, key.name, key.description, key.location, key.grant, key.policy.document)

class EncryptionKey(dictobj):
    fields = {
          'name': "Name of the key"
        , 'location': "The region the key exists in"
        , 'description': "Description of the key"
        , 'admin_users': "The admin_users for this key"
        , 'grant': "The grants given to the key"
        , "permission": "The permissions given to the key"
        , "no_root_access": "Whether to not give root access to the policy"
        }

def __register__():
    return {(10, "encryption_keys"): sb.container_spec(EncryptionKeys, sb.dictof(sb.string_spec(), encryption_keys_spec()))}

