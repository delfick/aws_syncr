# coding: spec

from aws_syncr.option_spec.statements import (
      statement_spec, resource_policy_dict, permission_dict, trust_dict
    , capitalize
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
        self.assertIs(self.kls().normalise(self.meta, val), val)

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

