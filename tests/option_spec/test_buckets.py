# coding: spec

from aws_syncr.option_spec.buckets import (
      buckets_spec, logging_statement_spec, website_statement_spec, lifecycle_statement_spec
    , expiration_spec, transition_spec
    , Buckets, Bucket, Document, WebsiteConfig, LoggingConfig, LifeCycleConfig
    , LifecycleExpirationConfig, LifecycleTransitionConfig
    , __register__
    )
from aws_syncr.errors import BadConfiguration, BadPolicy, BadSpecValue
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
import itertools
import uuid
import mock

describe TestCase, "buckets_spec":
    it "overrides the bucket name with the key of the specification":
        spec = MergedOptions.using({"name": "overridden", "location": "ap-southeast-2"})
        everything = {"buckets": {"my_bucket": spec}}
        result = buckets_spec().normalise(Meta(everything, [('buckets', ""), ('my_bucket', "")]), spec)
        self.assertEqual(result.name, "my_bucket")

    it "merges with a template":
        everything = {"templates": {"blah": {"location": "ap-southeast-2"}}}
        result = buckets_spec().normalise(Meta(everything, [('buckets', ""), ("tree", "")]), {"use": "blah"})
        self.assertEqual(result, Bucket(name="tree", location="ap-southeast-2", permission=Document([]), tags={}, website=None, logging=None, lifecycle=None, acl=None))

    it "recognises website":
        result = buckets_spec().normalise(Meta({}, []).at("buckets").at("my_bucket"), MergedOptions.using({"location": "ap-southeast-2", "website": {"index_document": "blah.html"}}))
        self.assertEqual(result, Bucket(name="my_bucket", location="ap-southeast-2", permission=Document([]), tags={}, logging=None, lifecycle=None, acl=None
            , website = WebsiteConfig(index_document={"Suffix": "blah.html"}, error_document=NotSpecified, redirect_all_requests_to=NotSpecified, routing_rules=NotSpecified)
            )
        )

    it "recognises logging":
        prefix = str(uuid.uuid1())
        destination = str(uuid.uuid1())
        result = buckets_spec().normalise(Meta({}, []).at("buckets").at("my_bucket"), MergedOptions.using({"location": "ap-southeast-2", "logging": {"prefix": prefix, "destination": destination}}))
        self.assertEqual(result, Bucket(name="my_bucket", location="ap-southeast-2", permission=Document([]), tags={}, website=None, lifecycle=None, acl=None
            , logging = LoggingConfig(prefix=prefix, destination=destination)
            )
        )

    it "recognises lifecycle":
        prefix = str(uuid.uuid1())
        identity = str(uuid.uuid1())
        noncurrent_version_transition = str(uuid.uuid1())
        noncurrent_version_expiration = str(uuid.uuid1())

        result = buckets_spec().normalise(
              Meta({}, []).at("buckets").at("my_bucket")
            , MergedOptions.using(
                { "location": "ap-southeast-2"
                , "lifecycle":
                  { "id": identity
                  , "prefix": prefix
                  , "transition": {"Days": 6, "storageclass": "GLACIER"}
                  , "expiration": {"Days": 30}
                  , "NoncurrentVersionExpiration": noncurrent_version_expiration
                  , "NoncurrentVersionTransition": noncurrent_version_transition
                  , "abort_incomplete_multipart_upload": 70
                  }
                }
              )
            )

        self.assertEqual(result, Bucket(name="my_bucket", location="ap-southeast-2", permission=Document([]), tags={}, website=None, logging=None, acl=None
            , lifecycle = [
                  LifeCycleConfig(
                      identity
                    , prefix = prefix
                    , enabled = NotSpecified
                    , transition = LifecycleTransitionConfig(date=NotSpecified, days=6, storageclass="GLACIER")
                    , expiration = LifecycleExpirationConfig(date=NotSpecified, days=30, expired_object_delete_marker=NotSpecified)
                    , noncurrent_version_expiration = noncurrent_version_expiration
                    , noncurrent_version_transition = noncurrent_version_transition
                    , abort_incomplete_multipart_upload = {"DaysAfterInitiation": 70}
                    )
                ]
            )
        )

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
        self.assertEqual(result, Bucket(name="stuff", location="ap-southeast-2", permission=Document([]), tags={"lob": "amazing", "application": "bob"}, website=None, logging=None, lifecycle=None, acl=None))

    it "creates an allow_permission when require_mfa_to_delete is True":
        spec = MergedOptions.using({"location": "ap-southeast-2", "require_mfa_to_delete": True})
        everything = MergedOptions.using({"buckets": {"my_bucket": spec}})
        result = buckets_spec().normalise(Meta(everything, []).at("buckets").at("my_bucket"), spec)
        self.assertEqual(
              result
            , Bucket(
                  name="my_bucket", location="ap-southeast-2", tags={}, website=None, logging=None, lifecycle=None, acl=None
                , permission = Document(
                    [ { 'sid': NotSpecified
                      , 'notcondition': NotSpecified
                      , 'notresource': NotSpecified
                      , 'principal': NotSpecified
                      , 'notprincipal': NotSpecified
                      , 'notaction': NotSpecified

                      , 'action': ['s3:DeleteBucket']
                      , 'condition': {'Bool': {'aws:MultiFactorAuthPresent': True}}
                      , 'resource': ["arn:aws:s3:::my_bucket", "arn:aws:s3:::my_bucket/*"]
                      , 'effect': 'Allow'
                      }
                    ]
                ))
            )

    describe "Recognising acl":
        describe "as a string":
            it "converts the acl into grants":
                owner = mock.Mock(name="owner")
                spec = MergedOptions.using({"location": "ap-southeast-2", "acl": "private"})
                everything = MergedOptions.using({"buckets": {"my_bucket": spec}})
                result = buckets_spec().normalise(Meta(everything, []).at("buckets").at("my_bucket"), spec)
                final = result.acl(owner)
                self.assertEqual(final, {"ACL": "private", "AccessControlPolicy": {"Grants": [{"Grantee": owner, "Permission": "FULL_CONTROL"}]}})

            it "works for all the valid acls":
                owner = mock.Mock(name="owner")
                canned_acls = [
                      "private", "public-read", "public-read-write", "aws-exec-read"
                    , "authenticated-read", "log-delivery-write"
                    ]

                for acl in canned_acls:
                    spec = MergedOptions.using({"location": "ap-southeast-2", "acl": acl})
                    everything = MergedOptions.using({"buckets": {"my_bucket": spec}})
                    result = buckets_spec().normalise(Meta(everything, []).at("buckets").at("my_bucket"), spec)
                    final = result.acl(owner)
                    self.assertEqual(final["ACL"], acl)
                    self.assertEqual(sorted(final.keys()), sorted(["ACL", "AccessControlPolicy"]))
                    self.assertEqual(sorted(final["AccessControlPolicy"].keys()), sorted(["Grants"]))

                    for grant in final["AccessControlPolicy"]["Grants"]:
                        self.assertEqual(sorted(grant.keys()), sorted(['Grantee', 'Permission']))
                        assert grant["Permission"] in ["FULL_CONTROL", "READ", "WRITE", "READ_ACP", "WRITE_ACP"]

        describe "as a dictionary":
            it "allows grantee as __owner__":
                owner = mock.Mock(name="owner")
                spec = MergedOptions.using({"location": "ap-southeast-2", "acl": {"grants": {"grantee": "__owner__", "permission": "READ"}}})
                everything = MergedOptions.using({"buckets": {"my_bucket": spec}})
                result = buckets_spec().normalise(Meta(everything, []).at("buckets").at("my_bucket"), spec)
                final = result.acl(owner)
                self.assertEqual(final, {"AccessControlPolicy": {"Grants": [{"Grantee": owner, "Permission": "READ"}]}})

            it "allows grantee as a dictionary":
                owner = mock.Mock(name="owner")
                spec = MergedOptions.using({"location": "ap-southeast-2", "acl": {"grants": {"grantee": {"display_name": "bob", "id": "0389387387038798", "type": "CanonicalUser"}, "permission": "READ"}}})
                everything = MergedOptions.using({"buckets": {"my_bucket": spec}})
                result = buckets_spec().normalise(Meta(everything, []).at("buckets").at("my_bucket"), spec)
                final = result.acl(owner)
                self.assertEqual(final, {"AccessControlPolicy": {"Grants": [{"Grantee": {"DisplayName": "bob", "ID": "0389387387038798", "Type": "CanonicalUser"}, "Permission": "READ"}]}})

describe TestCase, "Buckets":
    describe "Syncing a bucket":
        before_each:
            self.acl = mock.Mock(name="acl")
            self.tags = mock.Mock(name="tags")
            self.name = mock.Mock(name="name")
            self.website = mock.Mock(name="website")
            self.logging = mock.Mock(name="logging")
            self.location = mock.Mock(name="location")
            self.lifecycle = mock.Mock(name="lifecycle")
            self.permission = mock.Mock(name="permission")
            self.bucket = Bucket(name=self.name, location=self.location, permission=self.permission, tags=self.tags, website=self.website, logging=self.logging, lifecycle=self.lifecycle, acl=self.acl)
            self.buckets = Buckets(items={self.name: self.bucket})

            self.amazon = mock.Mock(name="amazon")
            self.aws_syncr = mock.Mock(name="aws_syncr")

        it "can create a bucket that doesn't exist":
            self.permission.statements = []
            s3 = self.amazon.s3 = mock.Mock(name="s3")
            s3.bucket_info.return_value = mock.Mock(name="bucket_info", creation_date=None)
            self.buckets.sync_one(self.aws_syncr, self.amazon, self.bucket)
            s3.bucket_info.assert_called_once_with(self.name)
            s3.create_bucket.assert_called_once_with(self.name, "", self.bucket)

        it "can modify a bucket that does exist":
            bucket_info = mock.Mock(name="bucket_info")
            self.permission.statements = []
            s3 = self.amazon.s3 = mock.Mock(name="s3")
            s3.bucket_info.return_value = bucket_info
            self.buckets.sync_one(self.aws_syncr, self.amazon, self.bucket)
            s3.bucket_info.assert_called_once_with(self.name)
            s3.modify_bucket.assert_called_once_with(bucket_info, self.name, "", self.bucket)

describe TestCase, "WebsiteConfig":
    describe "Creating a document":
        it "works when there is just index_document":
            config = website_statement_spec("", "").normalise(Meta({}, []), {"index_document": "index.html"})
            self.assertEqual(config.document, {"IndexDocument": {"Suffix": "index.html"}})

            config = website_statement_spec("", "").normalise(Meta({}, []), {"IndexDocument": { "Suffix": "index.html2"}})
            self.assertEqual(config.document, {"IndexDocument": {"Suffix": "index.html2"}})

        it "works when there is just error_document":
            config = website_statement_spec("", "").normalise(Meta({}, []), {"error_document": "index.html"})
            self.assertEqual(config.document, {"ErrorDocument": {"Key": "index.html"}})

            config = website_statement_spec("", "").normalise(Meta({}, []), {"ErrorDocument": { "Key": "index.html"}})
            self.assertEqual(config.document, {"ErrorDocument": {"Key": "index.html"}})

        it "works when there is just error_document and index_document":
            config = website_statement_spec("", "").normalise(Meta({}, []), {"error_document": "error.html", "index_document": "index.html"})
            self.assertEqual(config.document, {"ErrorDocument": {"Key": "error.html"}, "IndexDocument": {"Suffix": "index.html"}})

        it "works with redirect_all_requests_to being without a scheme":
            config = website_statement_spec("", "").normalise(Meta({}, []), {"redirect_all_requests_to": "www.somewhere.com"})
            self.assertEqual(config.document, {"RedirectAllRequestsTo": {"HostName": "www.somewhere.com"}})

            config = website_statement_spec("", "").normalise(Meta({}, []), {"RedirectAllRequestsTo": {"options": "yay"}})
            self.assertEqual(config.document, {"RedirectAllRequestsTo": {"options": "yay"}})

        it "works with redirect_all_requests_to being with a scheme":
            config = website_statement_spec("", "").normalise(Meta({}, []), {"redirect_all_requests_to": "http://www.somewhere.com"})
            self.assertEqual(config.document, {"RedirectAllRequestsTo": {"Protocol": "http", "HostName": "www.somewhere.com"}})

        it "doesn't modify routing_rules":
            config = website_statement_spec("", "").normalise(Meta({}, []), {"routing_rules": {"Hello": "there", "And": "stuff"}})
            self.assertEqual(config.document, {"RoutingRules": [{"Hello": "there", "And": "stuff"}]})

            config = website_statement_spec("", "").normalise(Meta({}, []), {"RoutingRules": {"more": "options"}})
            self.assertEqual(config.document, {"RoutingRules": {"more": "options"}})

        it "works with all options":
            config = website_statement_spec("", "").normalise(Meta({}, []), {"error_document": "error.html", "index_document": "index.html", "routing_rules": {"Hello": "there", "And": "stuff"}, "redirect_all_requests_to": "https://somewhere.nice.com"})
            self.assertEqual(config.document, {"ErrorDocument": {"Key": "error.html"}, "IndexDocument": {"Suffix": "index.html"}, "RedirectAllRequestsTo": {"Protocol": "https", "HostName": "somewhere.nice.com"}, "RoutingRules": [{"Hello": "there", "And": "stuff"}]})

describe TestCase, "LoggingConfig":
    describe "Creating a document":
        it "includes prefix and description":
            prefix = str(uuid.uuid1())
            destination = str(uuid.uuid1())
            config = logging_statement_spec("", "").normalise(Meta({}, []), {"prefix": prefix, "destination": destination})
            self.assertEqual(config.document, {"LoggingEnabled": { "TargetBucket": destination , "TargetPrefix": prefix } })

describe TestCase, "LifecycleConfig":
    describe "Creating a rule":
        before_each:
            self.meta = Meta({}, []).at("buckets").at("my_bucket").at("lifecycle")
            self.id = str(uuid.uuid1())

        it "turns expiration from an integer into a dictionary":
            item = {"id": self.id, "expiration": 30}
            result = lifecycle_statement_spec(None, None).normalise(self.meta, item).rule
            self.assertEqual(result, {"Expiration": {"Days": 30}, "ID": self.id, "Prefix": "", "Status": "Enabled"})

        it "defaults prefix to an empty string":
            item = {"id": self.id}
            result = lifecycle_statement_spec(None, None).normalise(self.meta, item).rule
            self.assertEqual(result["Prefix"], "")

        it "defaults status to Enabled":
            item = {"id": self.id}
            result = lifecycle_statement_spec(None, None).normalise(self.meta, item).rule
            self.assertEqual(result["Status"], "Enabled")

        it "sets status to Disabled if enabled is false":
            item = {"id": self.id, "enabled": False}
            result = lifecycle_statement_spec(None, None).normalise(self.meta, item).rule
            self.assertEqual(result["Status"], "Disabled")

        it "gets expiration and transition as_dict results":
            transition_res = mock.Mock(name="transition_res")
            transition_data = mock.Mock(name="expiration_data")
            expiration_res = mock.Mock(name="expiration_res")
            expiration_data = mock.Mock(name="expiration_data")

            transition = mock.Mock(name="transition")
            transition.as_dict.return_value = transition_res
            transition.is_dict.return_value = True

            expiration = mock.Mock(name="expiration")
            expiration.as_dict.return_value = expiration_res
            expiration.is_dict.return_value = True

            fake_expiration_spec = mock.Mock(name="expiration_spec")
            fake_expiration_spec.normalise.return_value = expiration

            fake_transition_spec = mock.Mock(name="transition_spec")
            fake_transition_spec.normalise.return_value = transition

            item = {"id": self.id, "transition": transition_data, "expiration": expiration_data}

            with mock.patch("aws_syncr.option_spec.buckets.expiration_spec", lambda *args: fake_expiration_spec):
                with mock.patch("aws_syncr.option_spec.buckets.transition_spec", lambda *args: fake_transition_spec):
                    result = lifecycle_statement_spec(None, None).normalise(self.meta, item).rule

            self.assertEqual(result["Transition"], transition_res)
            self.assertEqual(result["Expiration"], expiration_res)

            fake_expiration_spec.normalise.assert_called_once_with(self.meta.at("expiration"), expiration_data)
            fake_transition_spec.normalise.assert_called_once_with(self.meta.at("transition"), transition_data)

        it "generates an ID based on the rest of the options":
            item = {"enabled": False, "expiration" : 4}
            result = lifecycle_statement_spec(None, None).normalise(self.meta, item).rule
            result2 = lifecycle_statement_spec(None, None).normalise(self.meta, item).rule
            self.assertEqual(result["ID"], result2["ID"])

            item["expiration"] = 31
            result3 = lifecycle_statement_spec(None, None).normalise(self.meta, item).rule
            self.assertNotEqual(result["ID"], result3["ID"])

describe TestCase, "LifecycleTransitionConfig":
    describe "as_dict":
        it "creates a dictionary with just the specified value":
            ltc = LifecycleTransitionConfig(days=1, date=NotSpecified, storageclass="GLACIER")
            self.assertEqual(ltc.as_dict(), {"Days": 1, "StorageClass": "GLACIER"})

            ltc = LifecycleTransitionConfig(days=NotSpecified, date="astring", storageclass="STANDARD_IA")
            self.assertEqual(ltc.as_dict(), {"Date": "astring", "StorageClass": "STANDARD_IA"})

describe TestCase, "LifecycleExpirationConfig":
    describe "as_dict":
        it "creates a dictionary with just the specified value":
            lec = LifecycleExpirationConfig(days=1, date=NotSpecified, expired_object_delete_marker=NotSpecified)
            self.assertEqual(lec.as_dict(), {"Days": 1})

            lec = LifecycleExpirationConfig(days=NotSpecified, date="astring", expired_object_delete_marker=NotSpecified)
            self.assertEqual(lec.as_dict(), {"Date": "astring"})

            lec = LifecycleExpirationConfig(days=NotSpecified, date=NotSpecified, expired_object_delete_marker=True)
            self.assertEqual(lec.as_dict(), {"ExpiredObjectDeleteMarker": True})

describe TestCase, "expiration_spec":
    before_each:
        self.meta = Meta({}, []).at("buckets").at("my_bucket").at("expiration")

    it "only allows capitalized Date":
        with self.fuzzyAssertRaisesError(BadConfiguration, "Don't support lower case variant of key, use capitialized variant", key="date"):
            expiration_spec(None, None).normalise(self.meta, {"date": "sfdasf"})

    it "only allows one of days, date and ExpiredObjectDeleteMarker":
        for combination in itertools.combinations(("days", "Date", "expired_object_delete_marker"), 2):
            with self.fuzzyAssertRaisesError(BadPolicy, "Statement has conflicting keys, please only choose one"):
                expiration_spec(None, None).normalise(self.meta, dict((key, 1 if key[0].lower() == "d" else True) for key in combination))

        with self.fuzzyAssertRaisesError(BadPolicy, "Statement has conflicting keys, please only choose one"):
            expiration_spec(None, None).normalise(self.meta, {"days": 1, "Date": "adsf", "expired_object_delete_marker": True})

    it "complains if not specifying one of the available options":
        try:
            expiration_spec(None, None).normalise(self.meta, {})
        except BadSpecValue as error:
            self.assertEqual(type(error.errors[0]), BadSpecValue)
            self.assertEqual(error.errors[0].message, "Need to specify atleast one of the required keys")

    it "creates a LifecyleExpirationConfig":
        result = expiration_spec(None, None).normalise(self.meta, {"days": 1})
        self.assertEqual(result, LifecycleExpirationConfig(days=1, date=NotSpecified, expired_object_delete_marker=NotSpecified))

        result = expiration_spec(None, None).normalise(self.meta, {"Date": 1})
        self.assertEqual(result, LifecycleExpirationConfig(days=NotSpecified, date=1, expired_object_delete_marker=NotSpecified))

        result = expiration_spec(None, None).normalise(self.meta, {"expired_object_delete_marker": True})
        self.assertEqual(result, LifecycleExpirationConfig(days=NotSpecified, date=NotSpecified, expired_object_delete_marker=True))

describe TestCase, "transition_spec":
    before_each:
        self.meta = Meta({}, []).at("buckets").at("my_bucket").at("transition")

    it "only allows capitalized Date":
        with self.fuzzyAssertRaisesError(BadConfiguration, "Don't support lower case variant of key, use capitialized variant", key="date"):
            transition_spec(None, None).normalise(self.meta, {"date": "sfdasf"})

    it "only allows one of days and date":
        with self.fuzzyAssertRaisesError(BadPolicy, "Statement has conflicting keys, please only choose one"):
            transition_spec(None, None).normalise(self.meta, {"days": 1, "Date": "asdf", "storageclass": "GLACIER"})

    it "complains if not specifying one of the available options":
        try:
            transition_spec(None, None).normalise(self.meta, {"storageclass": "GLACIER"})
        except BadSpecValue as error:
            self.assertEqual(type(error.errors[0]), BadSpecValue)
            self.assertEqual(error.errors[0].message, "Need to specify atleast one of the required keys")

    it "creates an LifecyleTransitionConfig":
        result = transition_spec(None, None).normalise(self.meta, {"days": 1, "StorageClass": "GLACIER"})
        self.assertEqual(result, LifecycleTransitionConfig(days=1, date=NotSpecified, storageclass="GLACIER"))

        result = transition_spec(None, None).normalise(self.meta, {"Date": 1, "storageclass": "STANDARD_IA"})
        self.assertEqual(result, LifecycleTransitionConfig(days=NotSpecified, date=1, storageclass="STANDARD_IA"))

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

        self.stuff_spec = {"location": "ap-southeast-2", "tags": {"one": "1", "two": "2"}, "permission": [self.p1, self.p2], "allow_permission": self.p3, "require_mfa_to_delete": True}
        self.blah_spec = {"location": "us-east-1", "tags": {"three": "3", "four": "4"}, "allow_permission": self.p4, "deny_permission": self.p5}
        self.spec = {"stuff": self.stuff_spec, "blah": self.blah_spec}
        self.everything = MergedOptions.using({"buckets": self.spec, "accounts": {"dev": "123456789123", "stg": "445829383783"}, "aws_syncr": self.aws_syncr}, dont_prefix=[dictobj])

    it "works":
        meta = Meta(self.everything, []).at("buckets")
        result = __register__()[(80, "buckets")].normalise(meta, MergedOptions.using(self.spec))
        stuff_permissions = Document([
              {'notresource': NotSpecified, 'resource': '*', 'notaction': NotSpecified, 'effect': 'Allow', 'notprincipal': NotSpecified, 'sid': NotSpecified, 'action': 's3:*', 'notcondition': NotSpecified, 'condition': NotSpecified, 'principal': {"AWS": 'arn:aws:iam::123456789123:role/hi'}}
            , {'notresource': NotSpecified, 'resource': ['arn:aws:s3:::stuff', 'arn:aws:s3:::stuff/*'], 'notaction': NotSpecified, 'effect': 'Allow', 'notprincipal': NotSpecified, 'sid': NotSpecified, 'action': ['s3:Get*'], 'notcondition': NotSpecified, 'condition': NotSpecified, 'principal': [{'AWS': 'arn:aws:iam::123456789123:role/blah'}]}
            , {'notresource': NotSpecified, 'resource': ['arn:aws:s3:::blah', 'arn:aws:s3:::blah/*'], 'notaction': NotSpecified, 'effect': 'Allow', 'notprincipal': NotSpecified, 'sid': NotSpecified, 'action': ['s3:Head*'], 'notcondition': NotSpecified, 'condition': NotSpecified, 'principal': [{'AWS': ['arn:aws:sts::123456789123:assumed-role/yeap', 'arn:aws:sts::445829383783:assumed-role/yeap']}]}
            , {'notresource': NotSpecified, 'resource': ['arn:aws:s3:::stuff', 'arn:aws:s3:::stuff/*'], 'notaction': NotSpecified, 'effect': 'Allow', 'notprincipal': NotSpecified, 'sid': NotSpecified, 'action': ['s3:DeleteBucket'], 'notcondition': NotSpecified, 'condition': {"Bool": { "aws:MultiFactorAuthPresent": True } }, 'principal': NotSpecified }
            ])
        blah_permissions = Document([
              {'notresource': NotSpecified, 'resource': ['arn:aws:s3:::blah', 'arn:aws:s3:::blah/*'], 'notaction': NotSpecified, 'effect': 'Deny', 'notprincipal': NotSpecified, 'sid': NotSpecified, 'action': ["s3:*"], 'notcondition': NotSpecified, 'condition': NotSpecified, 'principal': [{'AWS': 'arn:aws:iam::123456789123:root'}]}
            , {'notresource': NotSpecified, 'resource': ['arn:aws:s3:::blah/path'], 'notaction': NotSpecified, 'effect': 'Allow', 'notprincipal': NotSpecified, 'sid': NotSpecified, 'action': ['s3:*'], 'notcondition': NotSpecified, 'condition': NotSpecified, 'principal': [{'AWS': ['arn:aws:iam::123456789123:role/bob', 'arn:aws:iam::123456789123:role/sarah']}]}
            ])
        bucket1 = Bucket(name="stuff", location="ap-southeast-2", permission=stuff_permissions, tags={"one": "1", "two": "2"}, website=None, logging=None, lifecycle=None, acl=None)
        bucket2 = Bucket(name="blah", location="us-east-1", permission=blah_permissions, tags={"three": "3", "four": "4"}, website=None, logging=None, lifecycle=None, acl=None)

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
        result = __register__()[(80, "buckets")].normalise(meta, MergedOptions.using(self.spec))

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
                },
                {
                  "Resource": [
                    "arn:aws:s3:::stuff",
                    "arn:aws:s3:::stuff/*"
                  ],
                  "Sid": "",
                  "Action": "s3:DeleteBucket",
                  "Effect": "Allow",
                  "Condition": {
                    "Bool": {
                      "aws:MultiFactorAuthPresent": true
                    }
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
