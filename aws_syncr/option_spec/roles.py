from aws_syncr.option_spec.statements import trust_statement_spec, permission_statement_spec
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.documents import Document
from aws_syncr.errors import BadOption

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb

import logging
import six

log = logging.getLogger("aws_syncr.option_spec.roles")

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

