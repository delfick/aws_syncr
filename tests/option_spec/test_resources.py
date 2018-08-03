# coding: spec

from aws_syncr.option_spec.resources import resource_spec_base, iam_specs, s3_specs, kms_specs, arn_specs, resource_spec
from aws_syncr.errors import BadPolicy

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.meta import Meta
from tests.helpers import TestCase
import mock

def ensure_setup_from_resource_spec_base(self, kls):
    resource = mock.Mock(name="resource")
    self_type = mock.Mock(name="self_type")
    self_name = mock.Mock(name="self_name")
    spec = kls(resource, self_type, self_name)
    self.assertIs(spec.resource, resource)
    self.assertIs(spec.self_type, self_type)
    self.assertIs(spec.self_name, self_name)

describe TestCase, "resource_spec_base":
    before_each:
        self.environment = mock.Mock(name="environment")
        self.default_account_id = mock.Mock(name="default_account_id")
        self.meta = Meta({"accounts": {self.environment: self.default_account_id}, "aws_syncr": type("aws_syncr", (object, ), {"environment": self.environment})}, [])

    it "takes in resource, self_type and self_name":
        ensure_setup_from_resource_spec_base(self, resource_spec_base)

    describe "accounts":
        it "yields default account id if no account on the resource":
            resource = {}
            spec = resource_spec_base(resource, "resource", "resource")
            self.assertEqual(list(spec.accounts(self.meta)), [self.default_account_id])

        it "complains if it finds an account it doesn't know about":
            unknown_env = str(mock.Mock(name="unknown_env"))
            resource = {"account": unknown_env}

            spec = resource_spec_base(resource, "resource", "resource")

            with self.fuzzyAssertRaisesError(BadPolicy, "Unknown account specified", account=unknown_env, meta=self.meta):
                list(spec.accounts(self.meta))

        it "yields each account by getting from the accounts dictionary":
            env1, account1 = str(mock.Mock(name="env1")), 13371
            env2, account2 = str(mock.Mock(name="env2")), 13372
            env3, account3 = str(mock.Mock(name="env3")), 13373

            resource = {"account": [env1, env2, env3]}
            for env, account_id in ((env1, account1), (env2, account2), (env3, account3)):
                self.meta.everything["accounts"][env] = account_id

            spec = resource_spec_base(resource, "resource", "resource")
            self.assertEqual(list(spec.accounts(self.meta)), [account1, account2, account3])

    describe "default_location":
        it "gets location from aws_syncr":
            location = mock.Mock(name="location")
            self.meta.everything['aws_syncr'].location = location
            self.assertIs(resource_spec_base({}, "resource", "resource").default_location(self.meta), location)

    describe "location":
        it "defaults to default location":
            location = mock.Mock(name="location")
            default_location = mock.Mock(name="default_location", return_value=location)
            spec = resource_spec_base({}, "resource", "resource")
            with mock.patch.object(spec, "default_location", default_location):
                self.assertIs(spec.location(self.meta), location)
            default_location.assert_called_once_with(self.meta)

        it "uses the location specified in the resource":
            location = mock.Mock(name="location")
            default_location = mock.Mock(name="default_location", return_value=location)
            specified_location = str(mock.Mock(name="specified_location"))
            spec = resource_spec_base({"location": specified_location}, "resource", "resource")
            with mock.patch.object(spec, "default_location", default_location):
                self.assertIs(spec.location(self.meta), specified_location)

describe TestCase, "iam_specs":
    before_each:
        self.environment = mock.Mock(name="environment")
        self.default_account_id = mock.Mock(name="default_account_id")
        self.meta = Meta({"accounts": {self.environment: self.default_account_id}, "aws_syncr": type("aws_syncr", (object, ), {"environment": self.environment})}, [])

    it "takes in resource, self_type and self_name":
        ensure_setup_from_resource_spec_base(self, iam_specs)

    describe "normalise":
        it "iterates through accounts":
            accounts = ["a1", "a2", "a3"]
            val = "role/yolo"
            resource = {"iam": val}
            spec = iam_specs(resource, "role", "blah")
            with mock.patch.object(spec, "accounts", lambda m: accounts):
                self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:iam::a1:role/yolo", "arn:aws:iam::a2:role/yolo", "arn:aws:iam::a3:role/yolo"])

        it "uses default account":
            val = "role/yolo"
            resource = {"iam": val}
            spec = iam_specs(resource, "role", "blah")
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:iam::{0}:role/yolo".format(self.default_account_id)])

        it "iterates through users":
            val = "role/yolo"
            resource = {"iam": val, "users": ["bob", "sarah"]}
            spec = iam_specs(resource, "role", "blah")
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:iam::{0}:role/yolo/bob".format(self.default_account_id), "arn:aws:iam::{0}:role/yolo/sarah".format(self.default_account_id)])

        it "iterates through users and accounts":
            val = "role/yolo"
            accounts = ["a1", "a2", "a3"]
            resource = {"iam": val, "users": ["bob", "sarah"]}
            spec = iam_specs(resource, "role", "blah")
            with mock.patch.object(spec, "accounts", lambda m: accounts):
                self.assertEqual(list(spec.normalise(self.meta, val)), [
                      "arn:aws:iam::a1:role/yolo/bob", "arn:aws:iam::a1:role/yolo/sarah"
                    , "arn:aws:iam::a2:role/yolo/bob", "arn:aws:iam::a2:role/yolo/sarah"
                    , "arn:aws:iam::a3:role/yolo/bob", "arn:aws:iam::a3:role/yolo/sarah"
                    ])

        it "uses sts instead of iam if assumed-role":
            val = "assumed-role/yolo"
            resource = {"iam": val}
            spec = iam_specs(resource, "role", "blah")
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:sts::{0}:assumed-role/yolo".format(self.default_account_id)])

        it "allows a list for the val":
            val = ["assumed-role/yolo", "role/everything"]
            resource = {"iam": val}
            spec = iam_specs(resource, "role", "blah")
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:sts::{0}:assumed-role/yolo".format(self.default_account_id), "arn:aws:iam::{0}:role/everything".format(self.default_account_id)])

        it "expands name, account and users":
            val = ["assumed-role/yolo", "role/everything"]
            accounts = ["a1", "a2", "a3"]
            resource = {"iam": val, "users": ["bob", "sarah"]}
            spec = iam_specs(resource, "role", "blah")
            with mock.patch.object(spec, "accounts", lambda m: accounts):
                self.assertEqual(list(spec.normalise(self.meta, val)), [
                      "arn:aws:sts::a1:assumed-role/yolo/bob", "arn:aws:sts::a1:assumed-role/yolo/sarah", "arn:aws:iam::a1:role/everything/bob", "arn:aws:iam::a1:role/everything/sarah"
                    , "arn:aws:sts::a2:assumed-role/yolo/bob", "arn:aws:sts::a2:assumed-role/yolo/sarah", "arn:aws:iam::a2:role/everything/bob", "arn:aws:iam::a2:role/everything/sarah"
                    , "arn:aws:sts::a3:assumed-role/yolo/bob", "arn:aws:sts::a3:assumed-role/yolo/sarah", "arn:aws:iam::a3:role/everything/bob", "arn:aws:iam::a3:role/everything/sarah"
                    ])

        it "complains if __self__ is used with a self_type that isn't role":
            val = "__self__"
            resource = {"iam": val}
            spec = iam_specs(resource, "bucket", "blah_and_stuff")
            with self.fuzzyAssertRaisesError(BadPolicy, "No __self__ iam role for this policy", meta=self.meta):
                list(spec.normalise(self.meta, val))

        it "allows __self__ as a name":
            val = "__self__"
            resource = {"iam": val}
            spec = iam_specs(resource, "role", "blah")
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:iam::{0}:role/blah".format(self.default_account_id)])

        it "doesn't put __self__ in more than once":
            val = ["__self__", "assumed-role/yolo", "role/everything"]
            accounts = ["a1", "a2", "a3"]
            resource = {"iam": val, "users": ["bob", "sarah"]}
            spec = iam_specs(resource, "role", "blah")
            with mock.patch.object(spec, "accounts", lambda m: accounts):
                self.assertEqual(list(spec.normalise(self.meta, val)), [
                      "arn:aws:sts::a1:assumed-role/yolo/bob", "arn:aws:sts::a1:assumed-role/yolo/sarah", "arn:aws:iam::a1:role/everything/bob", "arn:aws:iam::a1:role/everything/sarah"
                    , "arn:aws:sts::a2:assumed-role/yolo/bob", "arn:aws:sts::a2:assumed-role/yolo/sarah", "arn:aws:iam::a2:role/everything/bob", "arn:aws:iam::a2:role/everything/sarah"
                    , "arn:aws:sts::a3:assumed-role/yolo/bob", "arn:aws:sts::a3:assumed-role/yolo/sarah", "arn:aws:iam::a3:role/everything/bob", "arn:aws:iam::a3:role/everything/sarah"
                    , "arn:aws:iam::{0}:role/blah/bob".format(self.default_account_id), "arn:aws:iam::{0}:role/blah/sarah".format(self.default_account_id)
                    ])

describe TestCase, "s3_specs":
    before_each:
        self.environment = mock.Mock(name="environment")
        self.default_account_id = mock.Mock(name="default_account_id")
        self.meta = Meta({"accounts": {self.environment: self.default_account_id}, "aws_syncr": type("aws_syncr", (object, ), {"environment": self.environment})}, [])

    it "takes in resource, self_type and self_name":
        ensure_setup_from_resource_spec_base(self, s3_specs)

    describe "normalise":
        it "uses self_name as the bucket name if name is __self__":
            spec = s3_specs({}, "bucket", "blah_and_stuff")
            val = "__self__"
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:s3:::blah_and_stuff", "arn:aws:s3:::blah_and_stuff/*"])

        it "__self__ can be used with a path":
            spec = s3_specs({}, "bucket", "blah_and_stuff")
            val = "__self__/path"
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:s3:::blah_and_stuff/path"])

        it "complains if __self__ is used with a self_type that isn't bucket":
            val = "__self__"
            resource = {"s3": val}
            spec = s3_specs(resource, "iam", "blah_and_stuff")
            with self.fuzzyAssertRaisesError(BadPolicy, "No __self__ bucket for this policy", meta=self.meta):
                list(spec.normalise(self.meta, val))

        it "uses val as the name of the bucket":
            val = "name_of_bucket"
            resource = {"s3": val}
            spec = s3_specs(resource, "iam", "blah_and_stuff")
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:s3:::name_of_bucket", "arn:aws:s3:::name_of_bucket/*"])

        it "doesn't do a second record if a path is in the name":
            val = "name_of_bucket/path"
            resource = {"s3": val}
            spec = s3_specs(resource, "iam", "blah_and_stuff")
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:s3:::name_of_bucket/path"])

        it "can have a list of names":
            val = ["name_of_bucket/path", "name_of_another_bucket"]
            resource = {"s3": val}
            spec = s3_specs(resource, "iam", "blah_and_stuff")
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:s3:::name_of_bucket/path", "arn:aws:s3:::name_of_another_bucket", "arn:aws:s3:::name_of_another_bucket/*"])

describe TestCase, "kms_specs":
    before_each:
        self.environment = mock.Mock(name="environment")
        self.default_location = mock.Mock(name="location")
        self.default_account_id = mock.Mock(name="default_account_id")
        self.meta = Meta({"accounts": {self.environment: self.default_account_id}, "aws_syncr": type("aws_syncr", (object, ), {"environment": self.environment, "location": self.default_location})}, [])

    it "takes in resource, self_type and self_name":
        ensure_setup_from_resource_spec_base(self, kms_specs)

    describe "normalise":
        it "uses __self__ as an alias":
            val = "__self__"
            resource = {"kms": val}
            spec = kms_specs(resource, "key", "yeap")
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:kms:{0}:{1}:alias/yeap".format(self.default_location, self.default_account_id)])

        it "uses __self__ as an alias even if specified as a dictionary":
            spec = kms_specs({}, "key", "yeap")

            val = [{"alias": "__self__"}]
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:kms:{0}:{1}:alias/yeap".format(self.default_location, self.default_account_id)])

            val = [{"key_id": "__self__"}]
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:kms:{0}:{1}:alias/yeap".format(self.default_location, self.default_account_id)])

        it "complains if __self__ is used with a self_type that isn't key":
            val = "__self__"
            resource = {"s3": val}
            spec = kms_specs(resource, "iam", "blah_and_stuff")
            with self.fuzzyAssertRaisesError(BadPolicy, "No __self__ key for this policy", meta=self.meta):
                list(spec.normalise(self.meta, val))

        it "uses val as the alias":
            val = "my_amazing_key"
            resource = {"kms": val}
            spec = kms_specs(resource, "key", "yeap")
            self.assertEqual(list(spec.normalise(self.meta, val)), ["arn:aws:kms:{0}:{1}:alias/my_amazing_key".format(self.default_location, self.default_account_id)])

        it "can have multiple vals":
            val = ["my_amazing_key", "my_other_amazing_key"]
            resource = {"kms": val}
            spec = kms_specs(resource, "key", "yeap")
            self.assertEqual(list(spec.normalise(self.meta, val)), [
                  "arn:aws:kms:{0}:{1}:alias/my_amazing_key".format(self.default_location, self.default_account_id)
                , "arn:aws:kms:{0}:{1}:alias/my_other_amazing_key".format(self.default_location, self.default_account_id)
                ])

        it "can specify val as a dictionary":
            val = [{"alias": "my_amazing_key"}, {"key_id": "my_other_amazing_key"}]
            resource = {"kms": val}
            spec = kms_specs(resource, "key", "yeap")
            self.assertEqual(list(spec.normalise(self.meta, val)), [
                  "arn:aws:kms:{0}:{1}:alias/my_amazing_key".format(self.default_location, self.default_account_id)
                , "arn:aws:kms:{0}:{1}:key/my_other_amazing_key".format(self.default_location, self.default_account_id)
                ])

        it "can get location from the resource":
            val = [{"alias": "my_amazing_key"}, {"key_id": "my_other_amazing_key"}]
            resource = {"kms": val, "location": "somewhere"}
            spec = kms_specs(resource, "key", "yeap")
            self.assertEqual(list(spec.normalise(self.meta, val)), [
                  "arn:aws:kms:somewhere:{0}:alias/my_amazing_key".format(self.default_account_id)
                , "arn:aws:kms:somewhere:{0}:key/my_other_amazing_key".format(self.default_account_id)
                ])

        it "iterates through accounts":
            val = [{"alias": "__self__"}, {"key_id": "my_other_amazing_key"}]
            accounts = ['a1', 'a2', 'a3']
            resource = {"kms": val, "location": "somewhere"}
            spec = kms_specs(resource, "key", "yeap")
            with mock.patch.object(spec, "accounts", lambda m: accounts):
                self.assertEqual(list(spec.normalise(self.meta, val)), [
                      "arn:aws:kms:{0}:a1:alias/yeap".format(self.default_location), "arn:aws:kms:somewhere:a1:key/my_other_amazing_key"
                    , "arn:aws:kms:{0}:a2:alias/yeap".format(self.default_location), "arn:aws:kms:somewhere:a2:key/my_other_amazing_key"
                    , "arn:aws:kms:{0}:a3:alias/yeap".format(self.default_location), "arn:aws:kms:somewhere:a3:key/my_other_amazing_key"
                    ])

describe TestCase, "arn_specs":
    before_each:
        self.environment = mock.Mock(name="environment")
        self.default_location = mock.Mock(name="location")
        self.default_account_id = mock.Mock(name="default_account_id")
        self.meta = Meta({"accounts": {self.environment: self.default_account_id}, "aws_syncr": type("aws_syncr", (object, ), {"environment": self.environment, "location": self.default_location})}, [])

    it "takes in resource, self_type and self_name":
        ensure_setup_from_resource_spec_base(self, arn_specs)

    describe "normalise":
        it "complains if no identity in the resource":
            resource = {}
            spec = arn_specs(resource, "iam", "blah")
            with self.fuzzyAssertRaisesError(BadPolicy, "Generic arn specified without specifying 'identity'", meta=self.meta):
                list(spec.normalise(self.meta, "s3"))

        it "iterates  account and identity with val as the service":
            accounts = ["a1", "a2", "a3"]
            resource = {"location": "loc1", "identity": ["one", "two"]}
            spec = arn_specs(resource, "s3", "blah")
            val = 'sns'

            with mock.patch.object(spec, "accounts", lambda m: accounts):
                self.assertEqual(list(spec.normalise(self.meta, val)), [
                      "arn:aws:sns:loc1:a1:one", "arn:aws:sns:loc1:a1:two"
                    , "arn:aws:sns:loc1:a2:one", "arn:aws:sns:loc1:a2:two"
                    , "arn:aws:sns:loc1:a3:one", "arn:aws:sns:loc1:a3:two"
                    ])

describe TestCase, "resource_spec":
    before_each:
        self.meta = Meta({}, [])

    it "takes in self_type, self_name and only":
        only = mock.Mock(name="only")
        self_type = mock.Mock(name="self_type")
        self_name = mock.Mock(name="self_name")
        spec = resource_spec(self_type, self_name, only=only)
        self.assertIs(spec.only, only)
        self.assertIs(spec.self_type, self_type)
        self.assertIs(spec.self_name, self_name)

    it "yields strings as is":
        val = ["one", "two"]
        spec = resource_spec("s3", "blah")
        self.assertEqual(list(spec.normalise(self.meta, val)), ["one", "two"])

    it "uses the appropriate spec depending on the key in the dictionary to normalise":
        meta = mock.Mock(name="meta")
        indexed_meta = mock.Mock(name="indexed_meta")
        at_meta = mock.Mock(name="at_meta")

        meta.indexed_at.return_value = indexed_meta
        indexed_meta.at.return_value = at_meta

        s3_val = mock.Mock(name="s3_val")
        iam_val = mock.Mock(name="iam_val")
        kms_val = mock.Mock(name="kms_val")
        arn_val = mock.Mock(name="arn_val")
        resource = {"s3": s3_val, "iam": iam_val, "kms": kms_val, "arn": arn_val}

        spec = resource_spec("s3", "blah")

        s3_spec = mock.Mock(name="s3_spec")
        s3_spec.normalise.return_value = ["s3_spec_result"]
        fake_s3_specs = mock.Mock(name="fake_s3_specs", return_value=s3_spec)

        iam_spec = mock.Mock(name="iam_spec")
        iam_spec.normalise.return_value = ["iam_spec_result"]
        fake_iam_specs = mock.Mock(name="fake_iam_specs", return_value=iam_spec)

        kms_spec = mock.Mock(name="kms_spec")
        kms_spec.normalise.return_value = ["kms_spec_result"]
        fake_kms_specs = mock.Mock(name="fake_kms_specs", return_value=kms_spec)

        arn_spec = mock.Mock(name="arn_spec")
        arn_spec.normalise.return_value = ["arn_spec_result"]
        fake_arn_specs = mock.Mock(name="fake_arn_specs", return_value=arn_spec)

        with mock.patch.multiple("aws_syncr.option_spec.resources", iam_specs=fake_iam_specs, s3_specs=fake_s3_specs, kms_specs=fake_kms_specs, arn_specs=fake_arn_specs):
            self.assertEqual(sorted(list(spec.normalise(meta, resource))), sorted(["s3_spec_result", "iam_spec_result", "kms_spec_result", "arn_spec_result"]))

        s3_spec.normalise.assert_called_once_with(at_meta, s3_val)
        iam_spec.normalise.assert_called_once_with(at_meta, iam_val)
        kms_spec.normalise.assert_called_once_with(at_meta, kms_val)
        arn_spec.normalise.assert_called_once_with(at_meta, arn_val)

    it "can complain about not allowed types with only":
        spec = resource_spec("s3", "blah", only=['s3'])
        with self.fuzzyAssertRaisesError(BadPolicy, "Sorry, don't support this resource type here", wanted="iam", available=['s3'], meta=self.meta):
            list(spec.normalise(self.meta, {"iam": "role/bob"}))
