from aws_syncr.option_spec.resources import resource_spec, iam_specs
from aws_syncr.errors import BadOption, BadPolicy

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb

class statement_spec(sb.Spec):
    args = None
    final_kls = None
    required = []
    invalid_args = []

    def setup(self, self_type, self_name):
        self.self_type = self_type
        self.self_name = self_name
        if not self.args or not self.final_kls:
            raise NotImplementedError("Need to use a subclass of statement_spec that defines args and final_kls")

    def normalise(self, meta, val):
        nsd = lambda spec: sb.defaulted(spec, NotSpecified)
        args = {}
        for arg, spec in self.args(self.self_type, self.self_name).items():
            if type(arg) is tuple:
                capitalized = ''.join(part.capitalize() for part in arg)
                arg = ''.join(arg)
            else:
                capitalized = arg.capitalize()
            args[(arg, capitalized)] = spec

        kwargs = {}
        for (arg, capitalized), spec in list(args.items()):
            kwargs[arg] = nsd(spec)
            kwargs[capitalized] = sb.any_spec()
        val = sb.set_options(**kwargs).normalise(meta, val)

        kwargs = {}
        for (arg, capitalized) in args:
            if val.get(arg, NotSpecified) is not NotSpecified and val.get(capitalized, NotSpecified) is not NotSpecified:
                raise BadOption("Cannot specify arg as special and capitalized at the same time", arg=arg, special_val=val.get(arg), captialized_val=val.get(capitalized), meta=meta)
            else:
                kwargs[arg] = val[capitalized] if val.get(capitalized, NotSpecified) is not NotSpecified else val[arg]

        for arg in self.invalid_args:
            if type(arg) is tuple:
                capitalized = ''.join(part.capitalize() for part in arg)
                arg = ''.join(arg)
            else:
                capitalized = arg.capitalize()

            if arg in val or capitalized in val:
                raise BadOption("Cannot specify arg in this statement", arg=arg, capitalized=capitalized, meta=meta)

        missing = []
        for thing in self.required:
            if type(thing) is tuple:
                if not any(kwargs.get(option, NotSpecified) is not NotSpecified for option in thing):
                    missing.append(" or ".join(thing))
            else:
                if kwargs.get(thing, NotSpecified) is NotSpecified:
                    missing.append(thing)
        if missing:
            raise BadPolicy("Statement is missing required properties", missing=missing, meta=meta)

        return self.final_kls(**kwargs)

class resource_policy_dict(sb.Spec):
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

class permission_dict(resource_policy_dict):
    pass

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

        , 'action': sb.listof(sb.string_spec())
        , ("not", "action"): sb.listof(sb.string_spec())

        , 'resource': resource_spec(self_type, self_name)
        , ('not', 'resource'): resource_spec(self_type, self_name)

        , 'condition': sb.dictionary_spec()
        , ('not', 'condition'): sb.dictionary_spec()
        }
    required = [('action', 'notaction'), 'effect', ('resource', 'notresource')]
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

        for thing in ("Action", "NotAction", "Resource", "NotResource"):
            if thing in statement and isinstance(statement[thing], list):
                if len(statement[thing]) == 1:
                    statement[thing] = statement[thing][0]
                else:
                    statement[thing] = sorted(statement[thing])

        return statement

class ResourcePolicyStatement(dictobj):
    fields = ['sid', 'effect', 'action', 'notaction', 'resource', 'notresource', 'principal', 'notprincipal', 'condition', 'notcondition']

    def merge_principal(self, val, key):
        if len(val[key]) == 1:
            val[key] = val[key][0]
            return

        result = {}
        for item in val[key]:
            for service, lst in item.items():
                if not isinstance(lst, list):
                    lst = [lst]
                if service in result:
                    result[service].extend(lst)
                else:
                    result[service] = lst

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
                self.merge_principal(statement, principal)

            for key, v in list(statement.get(principal, {}).items()):
                if not v:
                    del statement[principal][key]

        for thing in ("Action", "NotAction", "Resource", "NotResource"):
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
        statement = {
              "GranteePrincipal": self.grantee, "RetireePrincipal": self.retiree
            , "Operations": sorted(self.operations), "GrantTokens": self.grant_tokens
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

