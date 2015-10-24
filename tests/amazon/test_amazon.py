# coding: spec

from aws_syncr.amazon.amazon import ValidatingMemoizedProperty, Amazon
from aws_syncr.errors import BadCredentials

from tests.helpers import TestCase
import boto3
import mock

describe TestCase, "ValidatingMemoizedProperty":
    it "takes in kls and key":
        kls = mock.Mock(name="kls")
        key = mock.Mock(name="key")
        prop = ValidatingMemoizedProperty(kls, key)
        self.assertIs(prop.kls, kls)
        self.assertIs(prop.key, key)

    describe "__get__":
        it "returns the object if already on the instance":
            s3 = mock.Mock(name="s3")
            instance = mock.Mock(name="instance")
            instance.s3 = s3
            prop = ValidatingMemoizedProperty(None, "s3")
            self.assertIs(prop.__get__(instance, None), s3)

        it "validates the account if not _validated and not _validating":
            res = mock.Mock(name="s3")
            instance = mock.Mock(name="instance", _validated=False, _validating=False, s3=None)
            prop = ValidatingMemoizedProperty(lambda *args, **kwargs: res, "s3")
            self.assertIs(prop.__get__(instance, None), res)
            instance.validate_account.assert_called_once_with()

        it "doesn't validate the account if _validated or _validating":
            res = mock.Mock(name="s3")

            instance = mock.Mock(name="instance", _validated=True, _validating=False, s3=None)
            prop = ValidatingMemoizedProperty(lambda *args, **kwargs: res, "s3")
            self.assertIs(prop.__get__(instance, None), res)
            self.assertEqual(instance.validate_account.mock_calls, [])

            instance = mock.Mock(name="instance", _validated=False, _validating=True, s3=None)
            prop = ValidatingMemoizedProperty(lambda *args, **kwargs: res, "s3")
            self.assertIs(prop.__get__(instance, None), res)
            self.assertEqual(instance.validate_account.mock_calls, [])

        it "instantiates the object and puts it on instance":
            res = mock.Mock(name="res")
            kls = mock.Mock(name="kls", return_value=res)
            key = "s3"
            instance = mock.Mock(name="instance", **{key: None, "_validated": True})
            prop = ValidatingMemoizedProperty(kls, key)
            self.assertIs(prop.__get__(instance, None), res)

            self.assertIs(getattr(instance, key), res)
            kls.assert_called_once_with(instance, instance.environment, instance.accounts, instance.dry_run)

describe TestCase, "Amazon":
    it "takes in environment, accounts, debug and dry_run":
        debug = mock.Mock(name="debug")
        dry_run = mock.Mock(name="dry_run")
        accounts = mock.Mock(name="accounts")
        environment = mock.Mock(name="environment")
        amazon = Amazon(environment, accounts, debug, dry_run)

        self.assertIs(amazon.debug, debug)
        self.assertIs(amazon.dry_run, dry_run)
        self.assertIs(amazon.accounts, accounts)
        self.assertIs(amazon.environment, environment)

    it "Instantiates changes and session":
        amazon = Amazon("dev", {})
        self.assertEqual(amazon.changes, False)
        self.assertEqual(type(amazon.session), boto3.session.Session)

    it "gets all_roles from validate_account":
        all_roles = mock.Mock(name="all_roles")
        called = []
        class sub(Amazon):
            def validate_account(self):
                called.append(1)
                self._all_roles = all_roles

        self.assertIs(sub("dev", {}).all_roles, all_roles)
        self.assertEqual(called, [1])

    it "gets all_users from validate_account":
        all_users = mock.Mock(name="all_users")
        called = []
        class sub(Amazon):
            def validate_account(self):
                called.append(1)
                self._all_users = all_users

        self.assertIs(sub("dev", {}).all_users, all_users)
        self.assertEqual(called, [1])

    describe "validate_account":
        it "gets all roles and all users":
            role_meta = mock.Mock(name="role_meta", data={"Arn": "arn:aws:iam::123456789123:role/blah"})
            role1 = mock.Mock(name="role1", meta=role_meta)
            iam_roles = [role1]

            user1 = mock.Mock(name="user1")
            iam_users = [user1]

            iam_roles_manager = mock.Mock(name="iam_roles_manager", all=mock.Mock(name="all", return_value=iam_roles))
            iam_users_manager = mock.Mock(name="iam_users_manager", all=mock.Mock(name="all", return_value=iam_users))
            iam_resource = mock.Mock(name="iam_resource", roles=iam_roles_manager, users=iam_users_manager)

            class sub(Amazon):
                iam = mock.Mock(name="iam", resource=iam_resource)

            instance = sub("dev", {"dev": "123456789123"})

            assert not hasattr(instance, "_all_roles")
            assert not hasattr(instance, "_all_users")
            instance.validate_account()

            self.assertEqual(instance._all_roles, iam_roles)
            self.assertEqual(instance._all_users, iam_users)

        it "complains if arn in the first role isn't correct":
            role_meta = mock.Mock(name="role_meta", data={"Arn": "arn:aws:iam::123456789123:role/blah"})
            role1 = mock.Mock(name="role1", meta=role_meta)
            iam_roles = [role1]

            iam_roles_manager = mock.Mock(name="iam_roles_manager", all=mock.Mock(name="all", return_value=iam_roles))
            iam_resource = mock.Mock(name="iam_resource", roles=iam_roles_manager)

            class sub(Amazon):
                iam = mock.Mock(name="iam", resource=iam_resource)

            instance = sub("dev", {"dev": "383902804"})
            with self.fuzzyAssertRaisesError(BadCredentials, "Don't have credentials for the correct account!", got="123456789123", wanted="383902804"):
                instance.validate_account()

        it "sets _validated to True":
            role_meta = mock.Mock(name="role_meta", data={"Arn": "arn:aws:iam::123456789123:role/blah"})
            role1 = mock.Mock(name="role1", meta=role_meta)
            iam_roles = [role1]

            user1 = mock.Mock(name="user1")
            iam_users = [user1]

            iam_roles_manager = mock.Mock(name="iam_roles_manager", all=mock.Mock(name="all", return_value=iam_roles))
            iam_users_manager = mock.Mock(name="iam_users_manager", all=mock.Mock(name="all", return_value=iam_users))
            iam_resource = mock.Mock(name="iam_resource", roles=iam_roles_manager, users=iam_users_manager)

            class sub(Amazon):
                iam = mock.Mock(name="iam", resource=iam_resource)

            instance = sub("dev", {"dev": "123456789123"})
            assert not hasattr(instance, "_validating")
            assert not hasattr(instance, "_validated")
            instance.validate_account()

            self.assertEqual(instance._validating, False)
            self.assertEqual(instance._validated, True)
