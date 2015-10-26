# coding: spec

from aws_syncr.option_spec.buckets import buckets_spec, Buckets, Bucket, __register__, Document
from aws_syncr.option_spec.aws_syncr_specs import AwsSyncrSpec
from aws_syncr.differ import Differ

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.spec_base import NotSpecified
from input_algorithms.spec_base import BadSpecValue
from input_algorithms.dictobj import dictobj
from option_merge import MergedOptions
from input_algorithms.meta import Meta
from tests.helpers import TestCase
from textwrap import dedent
import mock

describe TestCase, "buckets_spec":
    it "overrides the bucket name with the key of the specification":
        spec = MergedOptions.using({"name": "overridden", "location": "ap-southeast-2"})
        everything = {"buckets": {"my_bucket": spec}}
        result = buckets_spec().normalise(Meta(everything, [('buckets', ""), ('my_bucket', "")]), spec)
        self.assertEqual(result.name, "my_bucket")

    it "requires a location":
        meta = mock.Mock(name="meta")
        meta.everything = {}
        meta.key_names.return_value = {"_key_name_0": "asdf"}
        at_location = mock.Mock(name="location")
        def meta_at(path):
            return {"path": path}
        meta.at.side_effect = meta_at
        with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[BadSpecValue("Expected a value but got none", meta={"path": "location"})]):
            buckets_spec().normalise(meta, MergedOptions.using({}))

    it "merges with a template":
        everything = {"templates": {"blah": {"location": "ap-southeast-2"}}}
        result = buckets_spec().normalise(Meta(everything, [('buckets', ""), ("tree", "")]), {"use": "blah"})
        self.assertEqual(result, Bucket(name="tree", location="ap-southeast-2", permission=Document([]), tags={}))

    it "combines permission, deny_permission and allow_permission":
        # p# = orginal statement
        # d# = resource_policy_dict
        # r# = resource_policy_statement
        p1, d1, r1 = mock.Mock(name="p1", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d1"), mock.Mock(name="r1")
        p2, d2, r2 = mock.Mock(name="p2", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d2"), mock.Mock(name="r2")
        p3, d3, r3 = mock.Mock(name="p3", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d3"), mock.Mock(name="r3")
        p4, d4, r4 = mock.Mock(name="p4", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d4"), mock.Mock(name="r4")
        p5, d5, r5 = mock.Mock(name="p5", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d5"), mock.Mock(name="r5")
        spec = MergedOptions.using({"location": "ap-southeast-2", "permission": p1, "deny_permission": [p2, p3], "allow_permission": [p4, p5]})

        fake_resource_policy_dict = mock.Mock(name="resource_policy_dict")
        fake_resource_policy_dict.normalise.side_effect = lambda m, p: {p1:d1, p2:d2, p3:d3, p4:d4, p5:d5}[p]
        fake_resource_policy_dict_kls = mock.Mock(name="resource_policy_dict_kls", return_value=fake_resource_policy_dict)

        fake_resource_statement_spec = mock.Mock(name="resource_statement_spec")
        fake_resource_statement_spec.normalise.side_effect = lambda m, p: {d1:r1, d2:r2, d3:r3, d4:r4, d5:r5}[p]
        fake_resource_statement_spec_kls = mock.Mock(name="resource_statement_spec_kls", return_value=fake_resource_statement_spec)

        with mock.patch.multiple("aws_syncr.option_spec.buckets", resource_policy_dict=fake_resource_policy_dict_kls, resource_policy_statement_spec=fake_resource_statement_spec_kls):
            result = buckets_spec().normalise(Meta({}, []).at("buckets").at("stuff"), spec)
        self.assertEqual(result.permission.statements, [r1, r2, r3, r4, r5])

    it "takes in tags of string to formatted string":
        spec = MergedOptions.using({"location": "ap-southeast-2", "tags": {"lob": "{vars.lob}", "application": "{vars.application}"}})
        everything = MergedOptions.using({"vars": {"application": "bob", "lob": "amazing"}, "buckets": spec})
        result = buckets_spec().normalise(Meta(everything, []).at("buckets").at("stuff"), spec)
        self.assertEqual(result, Bucket(name="stuff", location="ap-southeast-2", permission=Document([]), tags={"lob": "amazing", "application": "bob"}))

describe TestCase, "Buckets":
    describe "Syncing a bucket":
        before_each:
            self.tags = mock.Mock(name="tags")
            self.name = mock.Mock(name="name")
            self.location = mock.Mock(name="location")
            self.permission = mock.Mock(name="permission")
            self.bucket = Bucket(name=self.name, location=self.location, permission=self.permission, tags=self.tags)
            self.buckets = Buckets(items={self.name: self.bucket})

            self.amazon = mock.Mock(name="amazon")
            self.aws_syncr = mock.Mock(name="aws_syncr")

        it "can create a bucket that doesn't exist":
            self.permission.statements = []
            s3 = self.amazon.s3 = mock.Mock(name="s3")
            s3.bucket_info.return_value = {}
            self.buckets.sync_one(self.aws_syncr, self.amazon, self.bucket)
            s3.bucket_info.assert_called_once_with(self.name)
            s3.create_bucket.assert_called_once_with(self.name, "", self.location, self.tags)

        it "can modify a bucket that does exist":
            bucket_info = mock.Mock(name="bucket_info")
            self.permission.statements = []
            s3 = self.amazon.s3 = mock.Mock(name="s3")
            s3.bucket_info.return_value = bucket_info
            self.buckets.sync_one(self.aws_syncr, self.amazon, self.bucket)
            s3.bucket_info.assert_called_once_with(self.name)
            s3.modify_bucket.assert_called_once_with(bucket_info, self.name, "", self.location, self.tags)

describe TestCase, "Registering buckets":
    before_each:
        # Need a valid folder to make aws_syncr
        with self.a_directory() as config_folder:
            self.aws_syncr = AwsSyncrSpec().aws_syncr_spec.normalise(Meta({}, []), {"environment": "dev", "config_folder": config_folder})

        self.p1 = {"Effect": "Allow", "Resource": "*", "Action": "s3:*", "Principal": {"AWS": "arn:aws:iam::123456789123:role/hi"}}
        self.p2 = {"effect": "Allow", "resource": {"s3": "__self__" }, "action": "s3:Get*", "principal": { "iam": "role/blah" }}
        self.p3 = {"resource": { "s3": "blah" }, "action": "s3:Head*", "principal": { "iam": "assumed-role/yeap", "account": ["dev", "stg"]}}

        self.p4 = {"resource": { "s3": "blah/path" }, "action": "s3:*", "principal": { "iam": "role", "users": ["bob", "sarah"] }}
        self.p5 = {"resource": { "s3": "__self__" }, "action": "s3:*", "principal": { "iam": "root" } }

        self.stuff_spec = {"location": "ap-southeast-2", "tags": {"one": "1", "two": "2"}, "permission": [self.p1, self.p2], "allow_permission": self.p3}
        self.blah_spec = {"location": "us-east-1", "tags": {"three": "3", "four": "4"}, "allow_permission": self.p4, "deny_permission": self.p5}
        self.spec = {"stuff": self.stuff_spec, "blah": self.blah_spec}
        self.everything = MergedOptions.using({"buckets": self.spec, "accounts": {"dev": "123456789123", "stg": "445829383783"}, "aws_syncr": self.aws_syncr}, dont_prefix=[dictobj])

    it "works":
        meta = Meta(self.everything, []).at("buckets")
        result = __register__()["buckets"].normalise(meta, MergedOptions.using(self.spec))
        stuff_permissions = Document([
              {'notresource': NotSpecified, 'resource': '*', 'notaction': NotSpecified, 'effect': 'Allow', 'notprincipal': NotSpecified, 'sid': NotSpecified, 'action': 's3:*', 'notcondition': NotSpecified, 'condition': NotSpecified, 'principal': {"AWS": 'arn:aws:iam::123456789123:role/hi'}}
            , {'notresource': NotSpecified, 'resource': ['arn:aws:s3:::stuff', 'arn:aws:s3:::stuff/*'], 'notaction': NotSpecified, 'effect': 'Allow', 'notprincipal': NotSpecified, 'sid': NotSpecified, 'action': ['s3:Get*'], 'notcondition': NotSpecified, 'condition': NotSpecified, 'principal': [{'AWS': 'arn:aws:iam::123456789123:role/blah'}]}
            , {'notresource': NotSpecified, 'resource': ['arn:aws:s3:::blah', 'arn:aws:s3:::blah/*'], 'notaction': NotSpecified, 'effect': 'Allow', 'notprincipal': NotSpecified, 'sid': NotSpecified, 'action': ['s3:Head*'], 'notcondition': NotSpecified, 'condition': NotSpecified, 'principal': [{'AWS': ['arn:aws:sts::123456789123:assumed-role/yeap', 'arn:aws:sts::445829383783:assumed-role/yeap']}]}
            ])
        blah_permissions = Document([
              {'notresource': NotSpecified, 'resource': ['arn:aws:s3:::blah', 'arn:aws:s3:::blah/*'], 'notaction': NotSpecified, 'effect': 'Deny', 'notprincipal': NotSpecified, 'sid': NotSpecified, 'action': ["s3:*"], 'notcondition': NotSpecified, 'condition': NotSpecified, 'principal': [{'AWS': 'arn:aws:iam::123456789123:root'}]}
            , {'notresource': NotSpecified, 'resource': ['arn:aws:s3:::blah/path'], 'notaction': NotSpecified, 'effect': 'Allow', 'notprincipal': NotSpecified, 'sid': NotSpecified, 'action': ['s3:*'], 'notcondition': NotSpecified, 'condition': NotSpecified, 'principal': [{'AWS': ['arn:aws:iam::123456789123:role/bob', 'arn:aws:iam::123456789123:role/sarah']}]}
            ])
        bucket1 = Bucket(name="stuff", location="ap-southeast-2", permission=stuff_permissions, tags={"one": "1", "two": "2"})
        bucket2 = Bucket(name="blah", location="us-east-1", permission=blah_permissions, tags={"three": "3", "four": "4"})

        buckets = Buckets(items={"stuff": bucket1, "blah": bucket2})
        for name, bucket in buckets.items.items():
            result_bucket = result.items[name]
            print("=== Bucket {0} ===".format(name))
            for statement1, statement2 in zip(result_bucket.permission.statements, bucket.permission.statements):
                for change in Differ.compare_two_documents(dict(statement1), dict(statement2)):
                    print(change)
        self.assertEqual(result, buckets)

    it "can be used to get policy documents":
        meta = Meta(self.everything, []).at("buckets")
        result = __register__()["buckets"].normalise(meta, MergedOptions.using(self.spec))

        stuff_statement = dedent("""
            {
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Resource": "*",
                  "Sid": "",
                  "Action": "s3:*",
                  "Effect": "Allow",
                  "Principal": {
                    "AWS": "arn:aws:iam::123456789123:role/hi"
                  }
                },
                {
                  "Resource": [
                    "arn:aws:s3:::stuff",
                    "arn:aws:s3:::stuff/*"
                  ],
                  "Sid": "",
                  "Action": "s3:Get*",
                  "Effect": "Allow",
                  "Principal": {
                    "AWS": "arn:aws:iam::123456789123:role/blah"
                  }
                },
                {
                  "Resource": [
                    "arn:aws:s3:::blah",
                    "arn:aws:s3:::blah/*"
                  ],
                  "Sid": "",
                  "Action": "s3:Head*",
                  "Effect": "Allow",
                  "Principal": {
                    "AWS": [
                      "arn:aws:sts::123456789123:assumed-role/yeap",
                      "arn:aws:sts::445829383783:assumed-role/yeap"
                    ]
                  }
                }
              ]
            }
        """)

        blah_statement = """
          {
            "Version": "2012-10-17",
            "Statement": [
              {"Action": "s3:*", "Principal": {"AWS": "arn:aws:iam::123456789123:root"}, "Resource": ["arn:aws:s3:::blah", "arn:aws:s3:::blah/*"], "Effect": "Deny", "Sid": ""},
              {"Action": "s3:*", "Principal": {"AWS": ["arn:aws:iam::123456789123:role/bob", "arn:aws:iam::123456789123:role/sarah"]}, "Resource": "arn:aws:s3:::blah/path", "Effect": "Allow", "Sid": ""}
            ]
          }
        """

        for name, generated, expected in (('stuff', result.items['stuff'].permission.document, stuff_statement), ('blah', result.items['blah'].permission.document, blah_statement)):
            print("=== Bucket {0} ===".format(name))
            changes = list(Differ.compare_two_documents(expected, generated))
            self.assertEqual(len(changes), 0, '\n'.join(changes))

