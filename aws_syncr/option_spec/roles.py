from aws_syncr.option_spec.resources import resource_spec, iam_specs
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.statements import statement_spec
from aws_syncr.option_spec.documents import Document
from aws_syncr.errors import BadOption

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb

import logging
import six

log = logging.getLogger("aws_syncr.option_spec.roles")

class principal_service_spec(sb.Spec):
    def normalise(self, meta, val):
        if val == "ec2":
            return "ec2.amazonaws.com"
        raise BadOption("Unknown special principal service", specified=val)

class principal_spec(sb.Spec):
    def setup(self, self_type, self_name):
        self.self_type = self_type
        self.self_name = self_name

    def normalise(self, meta, val):
        iam_spec = iam_specs(val, self.self_type, self.self_name)

        result = sb.set_options(
              Service = sb.listof(sb.string_spec())
            , Federated = sb.listof(sb.string_spec())
            , AWS = sb.listof(sb.string_spec())
            ).normalise(meta, val)

        special = sb.set_options(
              service = sb.listof(principal_service_spec())
            , federated = iam_spec
            , iam = iam_spec
            ).normalise(meta, val)

        for arg, lst in special.items():
            capitalized = arg.capitalize()
            if arg == 'iam':
                capitalized = "AWS"
            result[capitalized].extend(lst)

        for key, val in list(result.items()):
            if not val:
                del result[key]

            # Amazon gets rid of the lists if only one item
            # And this mucks around with the diffing....
            if len(val) is 1:
                result[key] = val[0]
            else:
                result[key] = sorted(val)

        return result

class permission_dict(sb.Spec):
    def setup(self, effect=NotSpecified):
        self.effect = effect

    def normalise(self, meta, val):
        val = sb.dictionary_spec().normalise(meta, val)
        if self.effect is not NotSpecified:
            if val.get('effect', self.effect) != self.effect or val.get('Effect', self.effect) != self.effect:
                raise BadOption("Defaulted effect is being overridden", default=self.effect, overriden=val.get("Effect", val.get("effect")), meta=meta)

            if val.get('effect', NotSpecified) is NotSpecified and val.get("Effect", NotSpecified) is NotSpecified:
                val['Effect'] = self.effect
        return val

class trust_dict(sb.Spec):
    def setup(self, principal):
        self.principal = principal

    def normalise(self, meta, val):
        val = sb.dictionary_spec().normalise(meta, val)
        if self.principal in val:
            raise BadOption("Please don't manually specify principal or notprincipal in a trust statement", meta=meta)
        val[self.principal] = val
        return val

class permission_statement_spec(statement_spec):
    args = lambda s, self_type, self_name: {
          'sid': sb.string_spec()
        , 'effect': sb.string_choice_spec(choices=["Deny", "Allow"])
        , 'action': sb.string_spec()

        , 'resource': resource_spec(self_type, self_name)
        , ('not', 'resource'): resource_spec(self_type, self_name)

        , 'condition': sb.dictionary_spec()
        , ('not', 'condition'): sb.dictionary_spec()
        }
    required = [('action', 'notaction'), 'effect', ('resource', 'notresource')]
    invalid_args = ['principal', ('not', 'principal')]
    final_kls = lambda s, *args, **kwargs: PermissionStatement(*args, **kwargs)

class trust_statement_spec(statement_spec):
    args = lambda s, self_type, self_name: {
          'sid': sb.string_spec()
        , 'effect': sb.string_choice_spec(choices=["Deny", "Allow"])
        , 'action': sb.string_spec()

        , 'resource': resource_spec(self_type, self_name)
        , ('not', 'resource'): resource_spec(self_type, self_name)

        , 'principal': principal_spec(self_type, self_name)
        , ('not', 'principal'): principal_spec(self_type, self_name)

        , 'condition': sb.dictionary_spec()
        , ('not', 'condition'): sb.dictionary_spec()
        }
    final_kls = lambda s, *args, **kwargs: TrustStatement(*args, **kwargs)

    def normalise(self, meta, val):
        val = super(trust_statement_spec, self).normalise(meta, val)
        have_federated = val.principal is not NotSpecified and val.principal.get("Federated") or val.notprincipal is not NotSpecified and val.notprincipal.get("Federated")
        if have_federated and val.action is NotSpecified:
            val.action = "sts:AssumeRoleWithSAML"
        return val

class role_spec(object):
    def normalise(self, meta, val):
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
            , trust = sb.container_spec(Document, sb.listof(trust_statement_spec('roles', role_name)))
            , permission = sb.container_spec(Document, sb.listof(permission_statement_spec('roles', role_name)))
            ).normalise(meta, val)

class PermissionStatement(dictobj):
    fields = ['sid', 'effect', 'action', 'resource', 'notresource', 'condition', 'notcondition']

    @property
    def statement(self):
        statement = {
              "Sid": self.sid, "Effect": self.effect, "Action": self.action
            , "Resource": self.resource, "NotResource": self.notresource
            , "Condition": self.condition, "NotCondition": self.notcondition
            }

        for key, val in list(statement.items()):
            if val is NotSpecified:
                del statement[key]

        if "Sid" not in statement:
            statement["Sid"] = ""

        for thing in ("Action", "NotAction", "Resource", "NotResource"):
            if thing in statement and isinstance(statement[thing], list):
                if len(statement[thing]) == 1:
                    statement[thing] = statement[thing][0]
                else:
                    statement[thing] = sorted(statement[thing])

        return statement

class TrustStatement(dictobj):
    fields = ['sid', 'effect', 'action', 'resource', 'notresource', 'principal', 'notprincipal', 'condition', 'notcondition']

    @property
    def statement(self):
        statement = {
              "Sid": self.sid, "Effect": self.effect, "Action": self.action
            , "Resource": self.resource, "NotResource": self.notresource
            , "Principal": self.principal, "NotPrincipal": self.notprincipal
            , "Condition": self.condition, "NotCondition": self.notcondition
            }

        for key, val in list(statement.items()):
            if val is NotSpecified:
                del statement[key]

        if "Action" not in statement:
            statement["Action"] = "sts:AssumeRole"

        if "Sid" not in statement:
            statement["Sid"] = ""

        if "Effect" not in statement:
            statement["Effect"] = "Allow"

        for principal in ("principal", "notprincipal", "Principal", "NotPrincipal"):
            for key, v in list(statement.get(principal, {}).items()):
                if not v:
                    del statement[principal][key]

        return statement

class Roles(dictobj):
    fields = ['roles']

    def sync(self):
        for name, role in self.roles.items():
            log.info("Syncing %s role", name)
            role.sync()

class Role(dictobj):
    fields = {
        "name": "The name of the role"
      , "description": "The description of the role!"

      , "trust": "The trust document"
      , "permission": "Combination of allow_permission and deny_permission"
      }

    def sync(self):
        """Sync the role"""
        print(self.trust.document)
        print(self.permission.document)

