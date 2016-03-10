# coding: spec

from aws_syncr.option_spec.statements import (
      statement_spec, resource_policy_dict, permission_dict, trust_dict, capitalize
    , trust_statement_spec, TrustStatement
    , grant_statement_spec, GrantStatement
    , principal_service_spec, principal_spec
    , permission_statement_spec, PermissionStatement
    , resource_policy_statement_spec, ResourcePolicyStatement
    )
from aws_syncr.errors import BadOption, BadPolicy

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.spec_base import NotSpecified
from input_algorithms.validators import Validator
from input_algorithms.errors import BadSpecValue
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from tests.helpers import TestCase
import mock

describe TestCase, "statement_spec":
    it "takes in self_type and self_name":
        self_type = mock.Mock(name="self_type")
        self_name = mock.Mock(name="self_name")

        class sub(statement_spec):
            args = []
            final_kls = type("Something", (object, ), {})

        instance = sub(self_type, self_name)
        self.assertEqual(instance.self_type, self_type)
        self.assertEqual(instance.self_name, self_name)

    it "complains if your subclass doesn't define args or final_kls":
        self_type = mock.Mock(name="self_type")
        self_name = mock.Mock(name="self_name")
        with self.fuzzyAssertRaisesError(NotImplementedError, "Need to use a subclass of statement_spec that defines args and final_kls"):
            statement_spec(self_type, self_name)

    describe "normalise":
        it "applies a processing pipeline":
            val = mock.Mock(name="val")
            meta = mock.Mock(name="meta")
            args = mock.Mock(name="args")
            spec = mock.Mock(name="spec")
            kwarg1 = mock.Mock(name="kwarg1")
            kwarg2 = mock.Mock(name="kwarg2")
            kwargs = {"kwarg1": kwarg1, "kwarg2": kwarg2}
            result = mock.Mock(name="result")
            normalised = mock.Mock(name="normalised")
            svalidators = mock.Mock(name="svalidators")

            called = []
            caller = lambda num: lambda *args, **kwargs: called.append(num)

            def complain_about_invalid_args(m, v):
                caller(1)()
                self.assertIs(m, meta)
                self.assertIs(v, val)
            complain_about_invalid_args = mock.Mock(name="complain_about_invalid_args", side_effect=complain_about_invalid_args)

            def apply_validators(m, v, vals, chain_value):
                caller(2)()
                self.assertIs(m, meta)
                self.assertIs(v, val)
                self.assertIs(vals, svalidators)
                self.assertEqual(chain_value, False)
            apply_validators = mock.Mock(name="apply_validators", side_effect=apply_validators)

            def make_spec():
                caller(3)()
                return args, spec
            make_spec = mock.Mock(name="make_spec", side_effect=make_spec)

            def normalise(m, v):
                caller(4)()
                self.assertIs(m, meta)
                self.assertIs(v, val)
                return normalised
            spec.normalise = mock.Mock(name="normalise", side_effect=normalise)

            def make_kwargs(m, a, n):
                caller(5)()
                self.assertIs(m, meta)
                self.assertIs(a, args)
                self.assertIs(n, normalised)
                return kwargs
            make_kwargs = mock.Mock(name="make_kwargs", side_effect=make_kwargs)

            def complain_about_missing_args(m, kw):
                caller(6)()
                self.assertIs(m, meta)
                self.assertIs(kw, kwargs)
            complain_about_missing_args = mock.Mock(name="complain_about_missing_args", side_effect=complain_about_missing_args)

            def kls(**kws):
                caller(7)()
                self.assertIs(kws.get('kwarg1'), kwarg1)
                self.assertIs(kws.get('kwarg2'), kwarg2)
                return result
            kls = mock.Mock(name="final_kls", side_effect=kls)

            mocks = dict((m._mock_name, m) for m in [
                  complain_about_invalid_args, make_spec
                , make_kwargs, complain_about_missing_args
                ]
            )

            with mock.patch.multiple("aws_syncr.option_spec.statements.statement_spec", **mocks):
                with mock.patch.multiple("aws_syncr.option_spec.statements", apply_validators=apply_validators):
                    class sub(statement_spec):
                        args = []
                        final_kls = kls
                        validators = svalidators
                    self.assertIs(sub("random", "random").normalise(meta, val), result)

            self.assertEqual(called, [1, 2, 3, 4, 5, 6, 7])

        it "propagates errors from complain_about_invalid_args":
            error = Exception("error!")
            class sub(statement_spec):
                args = []
                final_kls = type

                def complain_about_invalid_args(self, meta, val):
                    raise error

            try:
                sub("random", "random").normalise(None, None)
                assert False, "Expected an error"
            except Exception as e:
                self.assertIs(e, error)

        it "propagates errors from apply_validators":
            error = Exception("validation!")
            class validator(Validator):
                def validate(self, meta, val):
                    raise error

            class sub(statement_spec):
                args = []
                final_kls = type
                validators = [validator()]

            try:
                sub("random", "random").normalise(None, None)
                assert false, "expected an error"
            except Exception as e:
                self.assertIs(e, error)

        it "propagates errors from complain_about_missing_args":
            error = Exception("validation!")
            class sub(statement_spec):
                args = lambda *args, **kwargs: {}
                final_kls = type

                def complain_about_missing_args(self, meta, kwargs):
                    raise error

            try:
                sub("random", "random").normalise(None, {})
                assert false, "expected an error"
            except Exception as e:
                self.assertIs(e, error)

    describe "capitalize":
        it "joins if receives a tuple":
            self.assertEqual(capitalize(("one", "two")), ("onetwo", "OneTwo"))

        it "just capitalizes if not a tuple":
            self.assertEqual(capitalize("onetwo"), ("onetwo", "Onetwo"))

    describe "complain_about_invalid_args":
        it "complains if arg or it's captialized_val is in the val for any invalid_arg":
            val = mock.MagicMock(name="val")
            meta = mock.Mock(name="meta")
            invalid_arg = mock.Mock(name="invalid_arg")

            arg = mock.Mock(name="arg")
            capitalized = mock.Mock(name="captialized")
            capitalize = mock.Mock(name="capitalize", side_effect = lambda ia: (arg, capitalized))

            class sub(statement_spec):
                args = lambda: []
                final_kls = type
                invalid_args = [invalid_arg]
            instance = sub("random", "random")

            with mock.patch("aws_syncr.option_spec.statements.capitalize", capitalize):
                val.__contains__.return_value = False
                instance.complain_about_invalid_args(meta, val)
                assert True, "Expect no error"
                self.assertEqual(val.__contains__.mock_calls, [mock.call(arg), mock.call(capitalized)])

                val.__contains__.return_value = True
                with self.fuzzyAssertRaisesError(BadOption, "Cannot specify arg in this statement", arg=arg, capitalized=capitalized, meta=meta):
                    instance.complain_about_invalid_args(meta, val)
                self.assertEqual(val.__contains__.mock_calls, [mock.call(arg), mock.call(capitalized), mock.call(arg)])

    describe "make_spec":
        it "returns dict of (arg, capitalized) to spec":
            self_type = mock.Mock(name="self_type")
            self_name = mock.Mock(name="self_name")

            spec1 = sb.string_spec()
            spec2 = sb.integer_spec()

            def args(st, sn):
                self.assertIs(st, self_type)
                self.assertIs(sn, self_name)
                return {('three', 'four'):spec1, "two":spec2}
            args_lst = mock.Mock(name="args_lst", side_effect=args)

            class sub(statement_spec):
                args = args_lst
                final_kls = type
            args, _ = sub(self_type, self_name).make_spec()

            self.assertEqual(sorted(args.keys()), sorted([("threefour", "ThreeFour"), ("two", "Two")]))

            s = args[("threefour", "ThreeFour")]
            self.assertEqual(s.normalise(None, "asdf"), "asdf")

            s = args[("two", "Two")]
            self.assertEqual(s.normalise(None, 1), 1)

        it "returns a set_options with defaulted NotSpecified for arg and capitalized of all args":
            self_type = mock.Mock(name="self_type")
            self_name = mock.Mock(name="self_name")

            spec1 = sb.string_spec()
            spec2 = sb.integer_spec()

            def args(st, sn):
                self.assertIs(st, self_type)
                self.assertIs(sn, self_name)
                return {('three', 'four'):spec1, "two":spec2}
            args_lst = mock.Mock(name="args_lst", side_effect=args)

            class sub(statement_spec):
                args = args_lst
                final_kls = type
            _, spec = sub(self_type, self_name).make_spec()
            meta = Meta({}, [])

            self.assertEqual(spec.normalise(meta, {})
                , {"threefour": NotSpecified, "ThreeFour": NotSpecified, "two": NotSpecified, "Two": NotSpecified}
                )

            self.assertEqual(spec.normalise(meta, {"ThreeFour": "blah"})
                , {"threefour": NotSpecified, "ThreeFour": "blah", "two": NotSpecified, "Two": NotSpecified}
                )

            self.assertEqual(spec.normalise(meta, {"ThreeFour": "blah", "two": 1})
                , {"threefour": NotSpecified, "ThreeFour": "blah", "two": 1, "Two": NotSpecified}
                )

    describe "make_kwargs":
        it "complains arg and capitalized for an arg both have values in normalised":
            arg = mock.Mock(name="arg")
            meta = mock.Mock(name="meta")
            capitalized = mock.Mock(name="capitalized")

            args = [(arg, capitalized)]
            normalised = {arg: "value", capitalized: "value"}

            class sub(statement_spec):
                args = lambda: []
                final_kls = type

            with self.fuzzyAssertRaisesError(BadOption, "Cannot specify arg as special and capitalized at the same time", arg=arg, special_val="value", capitalized_val="value"):
                sub("random", "random").make_kwargs(meta, args, normalised)

        it "makes kwargs from just the arg using capitalized or special val as appropriate":
            arg1, capitalized1 = mock.Mock(name="arg1"), mock.Mock(name="capitalized1")
            arg2, capitalized2 = mock.Mock(name="arg2"), mock.Mock(name="capitalized2")
            arg3, capitalized3 = mock.Mock(name="arg3"), mock.Mock(name="capitalized3")
            args = [(arg1, capitalized1), (arg2, capitalized2), (arg3, capitalized3)]

            meta = mock.Mock(name="meta")
            normalised = {arg1: "v1", capitalized1: NotSpecified, arg2: NotSpecified, capitalized2: "v2", arg3: NotSpecified, capitalized3: NotSpecified}

            class sub(statement_spec):
                args = lambda: []
                final_kls = type

            kwargs = sub("random", "random").make_kwargs(meta, args, normalised)
            self.assertEqual(kwargs, {arg1:"v1", arg2:"v2", arg3:NotSpecified})

    describe "complain_about_missing_args":
        it "complains if arg or capitalized is not present for any required args":
            meta = mock.Mock(name='meta')
            class sub(statement_spec):
                args = lambda: []
                final_kls = type
                required = [("one", ("three", "four")), "two"]

            kwargs = {"one": 'v1', "two": "v2"}
            sub("random", "random").complain_about_missing_args(meta, kwargs)
            assert True, "Don't expect an error"

            kwargs = {"ThreeFour": 'v3', "Two": "v4"}
            sub("random", "random").complain_about_missing_args(meta, kwargs)
            assert True, "Don't expect an error"

            kwargs = {}
            missing = ["One or ThreeFour or one or threefour", "Two or two"]
            with self.fuzzyAssertRaisesError(BadPolicy, "Statement is missing required properties", missing=missing, meta=meta):
                sub("random", "random").complain_about_missing_args(meta, kwargs)

describe TestCase, "policy_dict":
    __only_run_tests_in_children__ = True

    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "takes in effect":
        effect = mock.Mock(name="effect")
        instance = self.kls(effect)
        self.assertIs(instance.effect, effect)

    it "expects a dictionary":
        with self.fuzzyAssertRaisesError(BadSpecValue, "Expected a dictionary"):
            self.kls().normalise(self.meta, "")

    it "returns as is if there is no effect":
        val = {"one": "one"}
        self.assertEqual(self.kls().normalise(self.meta, val), val)

    it "complains if defaulted effect is being overridden":
        for val in ({"effect": "Deny"}, {"Effect": "Deny"}):
            spec = self.kls(effect="Allow")
            with self.fuzzyAssertRaisesError(BadOption, "Defaulted effect is being overridden", default="Allow", overridden="Deny", meta=self.meta):
                spec.normalise(self.meta, val)

    it "sets Effect if not already set":
        spec = self.kls(effect="Allow")
        self.assertEqual(spec.normalise(self.meta, {}), {"Effect": "Allow"})
        self.assertEqual(spec.normalise(self.meta, {"Effect": "Allow"}), {"Effect": "Allow"})
        self.assertEqual(spec.normalise(self.meta, {"effect": "Allow"}), {"effect": "Allow"})

    describe "resource_policy_dict":
        kls = resource_policy_dict

    describe "permission_dict":
        kls = permission_dict

describe TestCase, "trust_dict":
    it "takes in a principal":
        principal = mock.Mock(name="principal")
        instance = trust_dict(principal)
        self.assertIs(instance.principal, principal)

    describe "normalise":
        before_each:
            self.meta = mock.Mock(name="meta", spec=Meta)

        it "expects a dictionary":
            with self.fuzzyAssertRaisesError(BadSpecValue, "Expected a dictionary"):
                trust_dict(principal="principal").normalise(self.meta, "")

        it "complains if the opposite principal type is already set":
            spec = trust_dict(principal="principal")
            with self.fuzzyAssertRaisesError(BadPolicy, "Specifying opposite principal type in statement", wanted="principal", got="notprincipal", meta=self.meta):
                spec.normalise(self.meta, {"notprincipal": "val"})

            with self.fuzzyAssertRaisesError(BadPolicy, "Specifying opposite principal type in statement", wanted="principal", got="notprincipal", meta=self.meta):
                spec.normalise(self.meta, {"NotPrincipal": "val"})

            spec = trust_dict(principal="notprincipal")
            with self.fuzzyAssertRaisesError(BadPolicy, "Specifying opposite principal type in statement", wanted="notprincipal", got="principal", meta=self.meta):
                spec.normalise(self.meta, {"principal": "val"})

            with self.fuzzyAssertRaisesError(BadPolicy, "Specifying opposite principal type in statement", wanted="notprincipal", got="principal", meta=self.meta):
                spec.normalise(self.meta, {"Principal": "val"})

        it "sets principal if not already set":
            spec = trust_dict(principal="principal")
            self.assertEqual(spec.normalise(self.meta, {"principal": "val1"}), {"principal": "val1"})
            self.assertEqual(spec.normalise(self.meta, {"Principal": "val1"}), {"Principal": "val1"})
            self.assertEqual(spec.normalise(self.meta, {"one": "two"}), {"principal": {"one": "two"}})

            spec = trust_dict(principal="notprincipal")
            self.assertEqual(spec.normalise(self.meta, {"notprincipal": "val1"}), {"notprincipal": "val1"})
            self.assertEqual(spec.normalise(self.meta, {"NotPrincipal": "val1"}), {"NotPrincipal": "val1"})
            self.assertEqual(spec.normalise(self.meta, {"one": "two"}), {"notprincipal": {"one": "two"}})

describe TestCase, "permission_statement_spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "deprecates allow and disallow":
        spec = permission_statement_spec("random", "random")
        with self.assertRaisesDeprecated("allow", "Use 'effect: Allow|Deny' instead", self.meta):
            spec.normalise(self.meta, {"allow": True})

        with self.assertRaisesDeprecated("disallow", "Use 'effect: Allow|Deny' instead", self.meta):
            spec.normalise(self.meta, {"disallow": True})

    it "requires action, effect and resource":
        spec = permission_statement_spec("random", "random")
        missing = ['Action or NotAction or action or notaction', 'Effect or effect', 'NotResource or Resource or notresource or resource']
        with self.fuzzyAssertRaisesError(BadPolicy, "Statement is missing required properties", missing=missing):
            spec.normalise(self.meta, {})

        missing = ['Effect or effect', 'NotResource or Resource or notresource or resource']
        with self.fuzzyAssertRaisesError(BadPolicy, "Statement is missing required properties", missing=missing):
            spec.normalise(self.meta, {'action': "s3:*"})

        missing = ['NotResource or Resource or notresource or resource']
        with self.fuzzyAssertRaisesError(BadPolicy, "Statement is missing required properties", missing=missing):
            spec.normalise(self.meta, {'action': "s3:*", "Effect": "Allow"})

        spec.normalise(self.meta, {'action': "s3:*", "Effect": "Allow", "notresource": ""})
        assert True, "Don't expect an error"

    it "doesn't like principal or notprincipal":
        spec = permission_statement_spec("random", "random")

        with self.fuzzyAssertRaisesError(BadOption, "Cannot specify arg in this statement", arg="principal", capitalized="Principal", meta=self.meta):
            spec.normalise(self.meta, {'action': "s3:*", "Effect": "Allow", "notresource": "", "principal": "parent"})

        with self.fuzzyAssertRaisesError(BadOption, "Cannot specify arg in this statement", arg="notprincipal", capitalized="NotPrincipal", meta=self.meta):
            spec.normalise(self.meta, {'action': "s3:*", "Effect": "Allow", "notresource": "", "NotPrincipal": "parent"})

    it "returns a PermissionStatement":
        spec = permission_statement_spec("random", "random")
        statement = spec.normalise(self.meta, {'action': "s3:*", "Effect": "Allow", "notresource": ""})
        self.assertEqual(type(statement), PermissionStatement)

describe TestCase, "resource_policy_statement_spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "deprecates allow and disallow":
        spec = resource_policy_statement_spec("random", "random")
        with self.assertRaisesDeprecated("allow", "Use 'effect: Allow|Deny' instead", self.meta):
            spec.normalise(self.meta, {"allow": True})

        with self.assertRaisesDeprecated("disallow", "Use 'effect: Allow|Deny' instead", self.meta):
            spec.normalise(self.meta, {"disallow": True})

    it "has no required args":
        spec = resource_policy_statement_spec("random", "random")
        spec.normalise(self.meta, {})
        assert True, "Don't expect an error"

    it "returns a ResourcePolicyStatement":
        spec = resource_policy_statement_spec("random", "random")
        statement = spec.normalise(self.meta, {})
        self.assertEqual(type(statement), ResourcePolicyStatement)

describe TestCase, "grant_statement_spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "has no required args":
        spec = grant_statement_spec("random", "random")
        spec.normalise(self.meta, {})
        assert True, "Don't expect an error"

    it "returns a GrantStatement":
        spec = grant_statement_spec("random", "random")
        statement = spec.normalise(self.meta, {})
        self.assertEqual(type(statement), GrantStatement)

describe TestCase, "trust_statement_spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "has no required args":
        spec = trust_statement_spec("random", "random")
        spec.normalise(self.meta, {})
        assert True, "Don't expect an error"

    it "returns a TrustStatement":
        spec = trust_statement_spec("random", "random")
        statement = spec.normalise(self.meta, {})
        self.assertEqual(type(statement), TrustStatement)

describe TestCase, "principal_service_spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "converts ec2 into ec2.amazonaws.com":
        self.assertEqual(principal_service_spec().normalise(self.meta, "ec2"), "ec2.amazonaws.com")

    it "complains about unknown services":
        with self.fuzzyAssertRaisesError(BadOption, "Unknown special principal service", specified="unknown", meta=self.meta):
            principal_service_spec().normalise(self.meta, "unknown")

describe TestCase, "principal_spec":
    before_each:
        self.meta = mock.Mock(name="meta", spec=Meta)

    it "takes in self_type and self_name":
        self_type = mock.Mock(name="self_type")
        self_name = mock.Mock(name='self_name')
        spec = principal_spec(self_type, self_name)
        self.assertIs(spec.self_type, self_type)
        self.assertIs(spec.self_name, self_name)

    describe "normalise":
        it "converts iam into AWS":
            val = {"iam": "etc"}
            self_type = mock.Mock(name='self_type')
            self_name = mock.Mock(name="self_name")

            iam_spec = mock.Mock(name="iam_spec")
            def iam_specs(v, st, sn):
                self.assertIs(v, val)
                self.assertIs(st, self_type)
                self.assertIs(sn, self_name)
                return iam_spec
            iam_specs = mock.Mock(name="iam_specs", side_effect=iam_specs)
            iam_spec.normalise.return_value = ["arn:aws:iam:etc"]

            spec = principal_spec(self_type, self_name)
            with mock.patch("aws_syncr.option_spec.statements.iam_specs", iam_specs):
                self.assertEqual(spec.normalise(self.meta, val), {"AWS": "arn:aws:iam:etc"})

        it "converts service into principal_service_spec":
            val = {"service": "ec2"}
            self_type = mock.Mock(name='self_type')
            self_name = mock.Mock(name="self_name")

            ret = mock.Mock(name="ret")
            principal_service_spec_instance = mock.Mock(name='principal_service_spec_instance')
            principal_service_spec = mock.Mock(name="principal_service_spec", return_value=principal_service_spec_instance)
            principal_service_spec_instance.normalise.return_value = ret

            iam_spec = mock.Mock(name="iam_spec")
            iam_specs = mock.Mock(name="iam_specs")
            iam_specs.return_value = iam_spec
            iam_spec.normalise.return_value = []

            spec = principal_spec(self_type, self_name)
            with mock.patch("aws_syncr.option_spec.statements.iam_specs", iam_specs):
                with mock.patch("aws_syncr.option_spec.statements.principal_service_spec", principal_service_spec):
                    self.assertEqual(spec.normalise(self.meta, val), {"Service": ret})

        it "converts federated into a resource_spec":
            val = {"federated": "ec2"}
            self_type = mock.Mock(name='self_type')
            self_name = mock.Mock(name="self_name")

            ret = mock.Mock(name="ret")
            resource_spec_instance = mock.Mock(name='resource_spec_instance')
            resource_spec = mock.Mock(name="resource_spec", return_value=resource_spec_instance)
            resource_spec_instance.normalise.return_value = [ret]

            iam_spec = mock.Mock(name="iam_spec")
            iam_specs = mock.Mock(name="iam_specs")
            iam_specs.return_value = iam_spec
            iam_spec.normalise.return_value = []

            spec = principal_spec(self_type, self_name)
            with mock.patch("aws_syncr.option_spec.statements.iam_specs", iam_specs):
                with mock.patch("aws_syncr.option_spec.statements.resource_spec", resource_spec):
                    self.assertEqual(spec.normalise(self.meta, val), {"Federated": ret})

describe TestCase, "PermissionStatement":
    before_each:
        self.sid = mock.Mock(name="sid")
        self.effect = mock.Mock(name="effect")
        self.action = mock.Mock(name="action")
        self.notaction = mock.Mock(name="notaction")
        self.resource = mock.Mock(name="resource")
        self.notresource = mock.Mock(name="notresource")
        self.condition = mock.Mock(name="condition")
        self.notcondition = mock.Mock(name="notcondition")
        self.statement = PermissionStatement(self.sid, self.effect, self.action, self.notaction, self.resource, self.notresource, self.condition, self.notcondition)

    describe "statement":
        it "returns statement of all the capitalized fields":
            self.assertEqual(self.statement.statement, {
                  "Sid": self.sid, "Effect": self.effect, "Action": self.action, "NotAction": self.notaction
                , "Resource": self.resource, "NotResource": self.notresource
                , "Condition": self.condition, "NotCondition": self.notcondition
                }
            )

        it "removes attributes that are NotSpecified":
            self.statement.action = NotSpecified
            self.statement.notresource = NotSpecified
            self.statement.condition = NotSpecified
            self.assertEqual(self.statement.statement, {
                  "Sid": self.sid, "Effect": self.effect,                        "NotAction": self.notaction
                , "Resource": self.resource
                ,                              "NotCondition": self.notcondition
                }
            )

        it "collapses single item lists":
            self.statement.action = ["action2", "action1"]
            self.statement.resource = ["res"]
            self.assertEqual(self.statement.statement, {
                  "Sid": self.sid, "Effect": self.effect
                , "Action": ["action1", "action2"], "NotAction": self.notaction
                , "Resource": "res", "NotResource": self.notresource
                , "Condition": self.condition, "NotCondition": self.notcondition
                }
            )

describe TestCase, "ResourcePolicyStatement":
    before_each:
        self.sid = mock.Mock(name="sid")
        self.effect = mock.Mock(name="effect")
        self.action = mock.Mock(name="action")
        self.notaction = mock.Mock(name="notaction")
        self.resource = mock.Mock(name="resource")
        self.notresource = mock.Mock(name="notresource")
        self.principal = mock.Mock(name="principal")
        self.notprincipal = mock.Mock(name="notprincipal")
        self.condition = mock.Mock(name="condition")
        self.notcondition = mock.Mock(name="notcondition")
        self.statement = ResourcePolicyStatement(self.sid, self.effect, self.action, self.notaction, self.resource, self.notresource, self.principal, self.notprincipal, self.condition, self.notcondition)

    describe "merge_principal":
        it "can merge a list of principal":
            key = "principal"
            val = {key: [{"AWS": "arn:aws:iam:one"}, {"Service": "ec2.amazonaws.com"}, {"Federated": "arn:aws:iam:two"}, {"Service": "lambda.amazonaws.com"}]}
            self.assertEqual(self.statement.merge_principal(val, key), {"AWS": "arn:aws:iam:one", "Service": ["ec2.amazonaws.com", "lambda.amazonaws.com"], "Federated": "arn:aws:iam:two"})

        it "returns as is if not a list":
            key = 'principal'
            val = {key: {"AWS": "hi"}}
            self.assertEqual(self.statement.merge_principal(val, key), {"AWS": "hi"})

        it "returns the string if it only finds one string":
            key = 'principal'
            val = {key: "*"}
            self.assertEqual(self.statement.merge_principal(val, key), "*")

        it "complains if it gets multiple strings":
            key = 'principal'
            val = {key: ["*", "blah"]}
            with self.fuzzyAssertRaisesError(BadOption, "Please only specify a string for principal once", got=["*", "blah"]):
                self.statement.merge_principal(val, key)

        it "complains if it gets string and dictionaries":
            key = 'principal'
            val = {key: ["*", {"AWS": "stuff"}]}
            with self.fuzzyAssertRaisesError(BadOption, "Please don't specify string principal and dictionary principal for the same policy", got=[["*"], {"AWS": ["stuff"]}]):
                self.statement.merge_principal(val, key)

    describe "statement":
        it "returns a statement with all the capitalized versions of the keys":
            merge_principal = mock.Mock(name="merge_principal", side_effect=lambda v, k: v[k])
            with mock.patch.object(self.statement, "merge_principal", merge_principal):
                self.assertEqual(self.statement.statement, {
                      "Sid": self.sid, "Effect": self.effect, "Action": self.action, "NotAction": self.notaction
                    , "Resource": self.resource, "NotResource": self.notresource
                    , "Principal": self.principal, "NotPrincipal": self.notprincipal
                    , "Condition": self.condition, "NotCondition": self.notcondition
                    }
                )

        it "removes items that are notspecified":
            merge_principal = mock.Mock(name="merge_principal", side_effect=lambda v, k: v[k])
            self.statement.action = NotSpecified
            self.statement.condition = NotSpecified
            self.statement.notprincipal = NotSpecified
            with mock.patch.object(self.statement, "merge_principal", merge_principal):
                self.assertEqual(self.statement.statement, {
                      "Sid": self.sid, "Effect": self.effect,                        "NotAction": self.notaction
                    , "Resource": self.resource, "NotResource": self.notresource
                    , "Principal": self.principal
                    ,                              "NotCondition": self.notcondition
                    }
                )

        it "defaults Sid and Effect":
            self.statement.sid = NotSpecified
            self.statement.effect = NotSpecified

            merge_principal = mock.Mock(name="merge_principal", side_effect=lambda v, k: v[k])
            with mock.patch.object(self.statement, "merge_principal", merge_principal):
                self.assertEqual(self.statement.statement, {
                      "Sid": "", "Effect": "Allow", "Action": self.action, "NotAction": self.notaction
                    , "Resource": self.resource, "NotResource": self.notresource
                    , "Principal": self.principal, "NotPrincipal": self.notprincipal
                    , "Condition": self.condition, "NotCondition": self.notcondition
                    }
                )

        it "Merges principals":
            self.statement.principal = [{"AWS": "one"}, {"AWS": "two"}]
            self.statement.notprincipal = NotSpecified
            self.assertEqual(self.statement.statement, {
                  "Sid": self.sid, "Effect": self.effect, "Action": self.action, "NotAction": self.notaction
                , "Resource": self.resource, "NotResource": self.notresource
                , "Principal": {"AWS": ["one", "two"]}
                , "Condition": self.condition, "NotCondition": self.notcondition
                }
            )

    describe "TrustStatement":
        it "sets action depending on whether we have federated and action":
            self.principal = [{"Federated": "one"}]
            self.notprincipal = NotSpecified
            statement = TrustStatement(self.sid, self.effect, self.action, self.notaction, self.resource, self.notresource, self.principal, self.notprincipal, self.condition, self.notcondition)
            self.assertIs(statement.statement["Action"], self.action)

            self.action = NotSpecified
            statement = TrustStatement(self.sid, self.effect, self.action, self.notaction, self.resource, self.notresource, self.principal, self.notprincipal, self.condition, self.notcondition)
            result = statement.statement
            self.assertIs(result["NotAction"], self.notaction)
            assert 'Action' not in result, result

            self.notaction = NotSpecified
            statement = TrustStatement(self.sid, self.effect, self.action, self.notaction, self.resource, self.notresource, self.principal, self.notprincipal, self.condition, self.notcondition)
            self.assertEqual(statement.statement["Action"], "sts:AssumeRoleWithSAML")

            self.principal = [{"AWS": "two"}]
            statement = TrustStatement(self.sid, self.effect, self.action, self.notaction, self.resource, self.notresource, self.principal, self.notprincipal, self.condition, self.notcondition)
            self.assertEqual(statement.statement["Action"], "sts:AssumeRole")

            self.principal = NotSpecified
            statement = TrustStatement(self.sid, self.effect, self.action, self.notaction, self.resource, self.notresource, self.principal, self.notprincipal, self.condition, self.notcondition)
            result = statement.statement
            assert "Action" not in result, result
            assert "NotAction" not in result, result

            self.notprincipal = [{"AWS": "three"}]
            statement = TrustStatement(self.sid, self.effect, self.action, self.notaction, self.resource, self.notresource, self.principal, self.notprincipal, self.condition, self.notcondition)
            self.assertEqual(statement.statement["Action"], "sts:AssumeRole")

describe TestCase, "GrantStatement":
    before_each:
        self.grantee = mock.Mock(name="grantee")
        self.retiree = mock.Mock(name="retiree")
        self.operations = ["op1", "op2"]
        self.grant_tokens = mock.Mock(name="grant_tokens")
        self.constraints = mock.Mock(name="constraints")
        self.statement = GrantStatement(self.grantee, self.retiree, self.operations, self.grant_tokens, self.constraints)

    describe "statement":
        it "returns a statement with the capitalized of all the fields":
            self.assertEqual(self.statement.statement, {
                  "GranteePrincipal": self.grantee, "RetireePrincipal": self.retiree
                , "Operations": sorted(self.operations), "GrantTokens": self.grant_tokens
                , "Constraints": self.constraints
                }
            )

        it "doesn't include NotSpecified fields":
            self.statement.operations = NotSpecified
            self.statement.constraints = NotSpecified
            self.assertEqual(self.statement.statement, {
                  "GranteePrincipal": self.grantee, "RetireePrincipal": self.retiree
                ,                                        "GrantTokens": self.grant_tokens
                }
            )

        it "Makes sure grantee and retiree are singles":
            self.statement.grantee = ['one']
            self.statement.retiree = ['two']
            self.assertEqual(self.statement.statement, {
                  "GranteePrincipal": "one", "RetireePrincipal": "two"
                , "Operations": sorted(self.operations), "GrantTokens": self.grant_tokens
                , "Constraints": self.constraints
                }
            )
