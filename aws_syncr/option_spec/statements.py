from aws_syncr.option_spec.resources import resource_spec, iam_specs
from aws_syncr.errors import BadOption, BadPolicy

from input_algorithms.spec_base import NotSpecified, apply_validators
from input_algorithms import spec_base as sb, validators
from input_algorithms.dictobj import dictobj
from option_merge import MergedOptions
from collections import OrderedDict
from itertools import chain
import six

def capitalize(arg):
    sep = ""
    if type(arg) is tuple and all(type(part) is tuple for part in arg):
        arg = dict(arg)
        sep = arg.get("sep", sep)
        arg = arg["parts"]

    if type(arg) is tuple:
        capitalized = ''.join(part.capitalize() for part in arg)
        arg = sep.join(arg)
    else:
        capitalized = arg.capitalize()
    return arg, capitalized

class statement_spec(sb.Spec):
    args = None
    final_kls = None
    required = []
    validators = []
    conflicting = []
    invalid_args = []

    def setup(self, self_type, self_name):
        self.self_type = self_type
        self.self_name = self_name
        if self.args is None or not self.final_kls:
            raise NotImplementedError("Need to use a subclass of statement_spec that defines args and final_kls")

    def normalise(self, meta, val):
        self.complain_about_invalid_args(meta, val)

        apply_validators(meta, val, self.validators, chain_value=False)
        args, spec = self.make_spec()
        normalised = spec.normalise(meta, val)

        kwargs = self.make_kwargs(meta, args, normalised)
        self.complain_about_missing_args(meta, kwargs)
        self.complain_about_conflicting_args(meta, kwargs)

        return self.final_kls(**kwargs)

    def complain_about_invalid_args(self, meta, val):
        for arg in self.invalid_args:
            arg, capitalized = capitalize(arg)
            if arg in val or capitalized in val:
                raise BadOption("Cannot specify arg in this statement", arg=arg, capitalized=capitalized, meta=meta)

    def make_spec(self):
        nsd = lambda spec: sb.defaulted(spec, NotSpecified)
        args = {}
        for arg, spec in self.args(self.self_type, self.self_name).items():
            arg, capitalized = capitalize(arg)
            args[(arg, capitalized)] = spec

        kwargs = {}
        for (arg, capitalized), spec in list(args.items()):
            kwargs[arg] = nsd(spec)
            if capitalized not in kwargs:
                kwargs[capitalized] = sb.any_spec()

        filtered_args = dict([((a, c), s) for (a, c), s in args.items() if a and a[0].islower()])
        return filtered_args, sb.set_options(**kwargs)

    def make_kwargs(self, meta, args, normalised):
        kwargs = {}
        for (arg, capitalized) in args:
            if normalised.get(arg, NotSpecified) is not NotSpecified and normalised.get(capitalized, NotSpecified) is not NotSpecified:
                raise BadOption("Cannot specify arg as special and capitalized at the same time", arg=arg, special_val=normalised.get(arg), capitalized_val=normalised.get(capitalized), meta=meta)
            else:
                kwargs[arg] = normalised[capitalized] if normalised.get(capitalized, NotSpecified) is not NotSpecified else normalised[arg]
        return kwargs

    def complain_about_missing_args(self, meta, kwargs):
        missing = []
        for arg in self.required:
            if isinstance(arg, six.string_types):
                arg = (arg, )
            available = sorted(list(set(list(chain.from_iterable([capitalize(thing) for thing in arg])))))
            if not any(kwargs.get(option, NotSpecified) is not NotSpecified for option in available):
                missing.append(" or ".join(available))

        if missing:
            raise BadPolicy("Statement is missing required properties", missing=missing, meta=meta)

    def complain_about_conflicting_args(self, meta, kwargs):
        found = None
        conflicting_group = None

        for group in self.conflicting:
            found = [key for key in group if kwargs.get(key, NotSpecified) is not NotSpecified]
            if len(found) > 1:
                conflicting_group = group
                break

        if conflicting_group and found:
            raise BadPolicy("Statement has conflicting keys, please only choose one", only_one_from=group, found=found, meta=meta)

class resource_policy_dict(sb.Spec):
    def setup(self, effect=NotSpecified):
        self.effect = effect

    def normalise(self, meta, val):
        if isinstance(val, MergedOptions):
            val = val.as_dict()
        val = sb.dictionary_spec().normalise(meta, val)
        if self.effect is not NotSpecified:
            if val.get('effect', self.effect) != self.effect or val.get('Effect', self.effect) != self.effect:
                raise BadOption("Defaulted effect is being overridden", default=self.effect, overridden=val.get("Effect", val.get("effect")), meta=meta)

            if val.get('effect', NotSpecified) is NotSpecified and val.get("Effect", NotSpecified) is NotSpecified:
                val['Effect'] = self.effect
        return val

class permission_dict(resource_policy_dict):
    pass

class trust_dict(sb.Spec):
    def setup(self, principal):
        self.principal = principal

    def normalise(self, meta, val):
        if isinstance(val, MergedOptions):
            val = val.as_dict()
        val = sb.dictionary_spec().normalise(meta, val)
        if self.principal == "notprincipal":
            opposite = "principal"
        else:
            opposite = ("not", "principal")
        opposite, cap_opposite = capitalize(opposite)
        if opposite in val or cap_opposite in val:
            raise BadPolicy("Specifying opposite principal type in statement", wanted=self.principal, got=opposite, meta=meta)

        capitalized = self.principal
        if capitalized in ("principal", "Principal"):
            arg, capitalized = "principal", "Principal"
        else:
            arg, capitalized = "notprincipal", "NotPrincipal"

        if arg not in val and capitalized not in val:
            return {self.principal: val}
        return val

class permission_statement_spec(statement_spec):
    args = lambda s, self_type, self_name: {
          'sid': sb.string_spec()
        , 'effect': sb.string_choice_spec(choices=["Deny", "Allow"])

        , 'action': sb.listof(sb.string_spec())
        , ("not", "action"): sb.listof(sb.string_spec())

        , 'resource': resource_spec(self_type, self_name)
        , ('not', 'resource'): resource_spec(self_type, self_name)

        , 'condition': sb.dictionary_spec()
        , ('not', 'condition'): sb.dictionary_spec()
        }
    validators = [
          validators.deprecated_key('allow', "Use 'effect: Allow|Deny' instead")
        , validators.deprecated_key('disallow', "Use 'effect: Allow|Deny' instead")
        ]
    required = [('action', ('not', 'action')), 'effect', ('resource', ('not', 'resource'))]
    invalid_args = ['principal', ('not', 'principal')]
    final_kls = lambda s, *args, **kwargs: PermissionStatement(*args, **kwargs)

class resource_policy_statement_spec(statement_spec):
    args = lambda s, self_type, self_name: {
          'sid': sb.string_spec()

        , 'effect': sb.string_choice_spec(choices=["Deny", "Allow"])

        , 'action': sb.listof(sb.string_spec())
        , ("not", "action"): sb.listof(sb.string_spec())

        , 'resource': resource_spec(self_type, self_name)
        , ('not', 'resource'): resource_spec(self_type, self_name)

        , 'principal': sb.listof(principal_spec(self_type, self_name))
        , ('not', 'principal'): sb.listof(principal_spec(self_type, self_name))

        , 'condition': sb.dictionary_spec()
        , ('not', 'condition'): sb.dictionary_spec()
        }
    validators = [
          validators.deprecated_key('allow', "Use 'effect: Allow|Deny' instead")
        , validators.deprecated_key('disallow', "Use 'effect: Allow|Deny' instead")
        ]
    final_kls = lambda s, *args, **kwargs: ResourcePolicyStatement(*args, **kwargs)

class grant_statement_spec(statement_spec):
    args = lambda s, self_type, self_name: {
          'grantee': sb.required(resource_spec(self_type, self_name, only="iam"))
        , 'retiree': resource_spec(self_type, self_name, only="iam")
        , 'operations': sb.required(sb.listof(sb.string_spec()))
        , 'constraints': sb.any_spec()
        , 'grant_tokens': sb.any_spec()
        }
    final_kls = lambda s, *args, **kwargs: GrantStatement(*args, **kwargs)

class trust_statement_spec(resource_policy_statement_spec):
    final_kls = lambda s, *args, **kwargs: TrustStatement(*args, **kwargs)

class principal_service_spec(sb.Spec):
    def normalise(self, meta, val):
        if val == "ec2":
            return "ec2.amazonaws.com"
        raise BadOption("Unknown special principal service", specified=val, meta=meta)

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
            , federated = resource_spec(self.self_type, self.self_name)
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
                continue

            # Amazon gets rid of the lists if only one item
            # And this mucks around with the diffing....
            if len(val) is 1:
                result[key] = val[0]
            else:
                result[key] = sorted(val)

        return result

class PermissionStatement(dictobj):
    fields = ['sid', 'effect', 'action', 'notaction', 'resource', 'notresource', 'condition', 'notcondition']

    @property
    def statement(self):
        statement = {
              "Sid": self.sid, "Effect": self.effect, "Action": self.action, "NotAction": self.notaction
            , "Resource": self.resource, "NotResource": self.notresource
            , "Condition": self.condition, "NotCondition": self.notcondition
            }

        for key, val in list(statement.items()):
            if val is NotSpecified:
                del statement[key]

        for thing in ("Action", "NotAction", "Resource", "NotResource", "Condition", "NotCondition"):
            if thing in statement and isinstance(statement[thing], list):
                if len(statement[thing]) == 1:
                    statement[thing] = statement[thing][0]
                else:
                    statement[thing] = sorted(statement[thing])

        return statement

class ResourcePolicyStatement(dictobj):
    fields = ['sid', 'effect', 'action', 'notaction', 'resource', 'notresource', 'principal', 'notprincipal', 'condition', 'notcondition']

    def merge_principal(self, val, key):
        if len(val[key]) == 1 and isinstance(val[key], list):
            val[key] = val[key][0]
            return val[key]

        if not isinstance(val[key], list):
            val[key] = [val[key]]

        result = {}
        string_results = []
        for item in val[key]:
            if isinstance(item, six.string_types):
                string_results.append(item)
            else:
                for service, lst in item.items():
                    if not isinstance(lst, list):
                        lst = [lst]
                    if service in result:
                        result[service].extend(lst)
                    else:
                        result[service] = lst

        if len(string_results) == 1:
            if result:
                raise BadOption("Please don't specify string principal and dictionary principal for the same policy", got=[string_results, result])
            return string_results[0]

        elif len(string_results) > 1:
            raise BadOption("Please only specify a string for principal once", got=string_results)

        else:
            for service, lst in list(result.items()):
                if len(lst) == 1:
                    result[service] = lst[0]

        return result

    @property
    def statement(self):
        statement = {
              "Sid": self.sid, "Effect": self.effect, "Action": self.action, "NotAction": self.notaction
            , "Resource": self.resource, "NotResource": self.notresource
            , "Principal": self.principal, "NotPrincipal": self.notprincipal
            , "Condition": self.condition, "NotCondition": self.notcondition
            }

        for key, val in list(statement.items()):
            if val is NotSpecified:
                del statement[key]

        if "Sid" not in statement:
            statement["Sid"] = ""

        if "Effect" not in statement:
            statement["Effect"] = "Allow"

        for principal in ("Principal", "NotPrincipal"):
            if principal in statement:
                statement[principal] = self.merge_principal(statement, principal)

        for thing in ("Action", "NotAction", "Resource", "NotResource", "Condition", "NotCondition", "Principal", "NotPrincipal"):
            if thing in statement and isinstance(statement[thing], list):
                if len(statement[thing]) == 1:
                    statement[thing] = statement[thing][0]
                else:
                    statement[thing] = sorted(statement[thing])

        return statement

class TrustStatement(ResourcePolicyStatement):

    @property
    def statement(self):
        statement = super(TrustStatement, self).statement

        if "Action" not in statement and 'NotAction' not in statement:
            if "Principal" in statement or "NotPrincipal" in statement:
                have_federated = "Principal" in statement and "Federated" in statement["Principal"] or "NotPrincipal" in statement and "Federated" in statement["NotPrincipal"]
                if have_federated:
                    statement["Action"] = "sts:AssumeRoleWithSAML"
                else:
                    statement["Action"] = "sts:AssumeRole"

        return statement

class GrantStatement(dictobj):
    fields = ['grantee', 'retiree', 'operations', 'grant_tokens', 'constraints']

    @property
    def statement(self):
        operations = self.operations
        if operations is not NotSpecified:
            operations = sorted(self.operations)
        statement = {
              "GranteePrincipal": self.grantee, "RetireePrincipal": self.retiree
            , "Operations": self.operations, "GrantTokens": self.grant_tokens
            , "Constraints": self.constraints
            }

        for key, val in list(statement.items()):
            if val is NotSpecified:
                del statement[key]

        for thing in ("GranteePrincipal", "RetireePrincipal"):
            if thing in statement and isinstance(statement[thing], list):
                if len(statement[thing]) == 1:
                    statement[thing] = statement[thing][0]
                else:
                    statement[thing] = sorted(statement[thing])

        return statement

