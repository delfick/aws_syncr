# coding: spec

from aws_syncr.option_spec.encryption_keys import EncryptionKey, EncryptionKeys, encryption_keys_spec, __register__
from aws_syncr.option_spec.statements import GrantStatement, ResourcePolicyStatement
from aws_syncr.option_spec.aws_syncr_specs import AwsSyncrSpec
from aws_syncr.option_spec.documents import Document
from aws_syncr.errors import BadSpecValue
from aws_syncr.differ import Differ

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
from option_merge import MergedOptions
from input_algorithms.meta import Meta
from tests.helpers import TestCase
import json
import mock

describe TestCase, "encryption_keys_spec":
    before_each:
        self.accounts = {"dev": "123456789123"}
        self.aws_syncr = AwsSyncrSpec().aws_syncr_spec.normalise(Meta({}, []), {"config_folder": ".", "environment": "dev"})
        self.everything_base = MergedOptions.using({"accounts": self.accounts, "aws_syncr": self.aws_syncr}, dont_prefix=[dictobj])

    it "can use a template":
        everything = self.everything_base.wrapped()
        everything.update({"templates": {"tem": {"description": "for glory!", "location": "antarctica"} } })

        spec = {"use": "tem"}
        result = encryption_keys_spec().normalise(Meta(everything, []).at("encryption_keys").at("key1"), spec)
        for name, val in dict(name="key1", location="antarctica", description="for glory!").items():
            self.assertEqual(result[name], val)

    it "overrides the name":
        spec = {"name": "blah and stuff", "location": "somewhere"}
        result = encryption_keys_spec().normalise(Meta(self.everything_base, []).at("encryption_keys").at("key2"), spec)
        self.assertEqual(result.name, "key2")

    it "requires a location":
        class FakeMeta(dictobj):
            fields = ['path', ('everything', self.everything_base.wrapped())]

            def key_names(self):
                return {"_key_name_0": "asdf"}

            def at(self, path):
                return FakeMeta(path)

            def __eql__(self, other):
                return other.path == self.path
        meta = FakeMeta("")

        with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[BadSpecValue("Expected a value but got none", meta=FakeMeta("location"))]):
            encryption_keys_spec().normalise(meta, {})

    it "sets a default policy":
        result = encryption_keys_spec().normalise(Meta(self.everything_base, []).at("encryption_keys").at("key3"), {"location": "ap-southeast-2"})
        changes = list(Differ.compare_two_documents(
              result.policy.document
            , {"Version": "2012-10-17", "Statement": [{"Sid": "", "Resource": "*", "Action": "kms:*", "Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::123456789123:root"}}]}
            ))

        self.assertEqual(len(changes), 0, '\n'.join(changes))

    it "evaluates grant expressions":
        g1, r1 = mock.Mock(name="grant1"), mock.Mock(name="resolved1")
        g2, r2 = mock.Mock(name="grant2"), mock.Mock(name="resolved2")
        g3, r3 = mock.Mock(name="grant3"), mock.Mock(name="resolved3")
        spec = {"location": "cafe", "grant": [g1, g2, g3]}

        fake_grant_statement_spec = mock.Mock(name="grant_statement_spec")
        fake_grant_statement_spec.normalise.side_effect = lambda m, g: {g1:r1, g2:r2, g3:r3}[g]
        fake_grant_statement_spec_kls = mock.Mock(name="grant_statement_spec_kls", return_value=fake_grant_statement_spec)

        with mock.patch.multiple("aws_syncr.option_spec.encryption_keys", grant_statement_spec=fake_grant_statement_spec_kls):
            result = encryption_keys_spec().normalise(Meta(self.everything_base, []).at("encryption_keys").at("key4"), spec)

        self.assertEqual(result.grant, [r1, r2, r3])

describe TestCase, "EncryptionKeys":
    describe "syncing an encryption key":
        before_each:
            self.name = mock.Mock(name="name")
            self.grant = mock.Mock(name="grant")
            self.policy = mock.Mock(name="policy")
            self.location = mock.Mock(name="location")
            self.description = mock.Mock(name="description")

            self.kms = mock.Mock(name="kms")
            self.amazon = mock.Mock(name="amazon")
            self.amazon.kms = self.kms
            self.aws_syncr = mock.Mock("aws_syncr")

            self.key = EncryptionKey(name=self.name, location=self.location, description=self.description, grant=self.grant)
            self.key.policy = self.policy
            self.keys = EncryptionKeys(items=[self.key])

        it "creates a new one if one doesn't already exist":
            self.kms.key_info.return_value = None
            self.keys.sync_one(self.aws_syncr, self.amazon, self.key)
            self.kms.key_info.assert_called_once_with(self.name, self.location)
            self.kms.create_key.assert_called_once_with(self.name, self.description, self.location, self.grant, self.policy.document)

        it "modifies an existing one if it already exists":
            key_info = mock.Mock(name="key_info")
            self.kms.key_info.return_value = key_info
            self.keys.sync_one(self.aws_syncr, self.amazon, self.key)
            self.kms.key_info.assert_called_once_with(self.name, self.location)
            self.kms.modify_key.assert_called_once_with(key_info, self.name, self.description, self.location, self.grant, self.policy.document)

describe TestCase, "__register__":
    before_each:
        self.accounts = {"dev": "123456789123"}
        self.aws_syncr = AwsSyncrSpec().aws_syncr_spec.normalise(Meta({}, []), {"config_folder": ".", "environment": "dev"})
        self.everything_base = MergedOptions.using({"accounts": self.accounts, "aws_syncr": self.aws_syncr}, dont_prefix=[dictobj])

    it "works":
        everything = self.everything_base.wrapped()
        key1_spec = {"location": "ap-southeast-2", "grant": {"grantee": {"iam": "role/bob"}, "operations": ["Decrypt"]}}
        key2_spec = {"location": "us-east-1", "grant": [{"grantee": {"iam": "assumed-role/tim"}, "operations": ["Encrypt", "GenerateDataKey"]}]}
        spec = {"key1": key1_spec, "key2": key2_spec}
        result = __register__()["encryption_keys"].normalise(Meta(everything, []).at("encryption_keys"), spec)

        key1_expected = EncryptionKey(name="key1", location="ap-southeast-2", description=""
            , grant=[GrantStatement(grantee=["arn:aws:iam::123456789123:role/bob"], operations=["Decrypt"], retiree=NotSpecified, constraints=NotSpecified, grant_tokens=NotSpecified)]
            )
        key1_expected.policy = Document(statements=[
            ResourcePolicyStatement(sid="", effect=NotSpecified, action=["kms:*"], notaction=NotSpecified, resource=["*"], notresource=NotSpecified, principal=[{"AWS": "arn:aws:iam::123456789123:root", "Federated": [], "Service": []}], notprincipal=NotSpecified, condition=NotSpecified, notcondition=NotSpecified)
            ])

        key2_expected = EncryptionKey(name="key2", location="us-east-1", description=""
            , grant=[GrantStatement(grantee=["arn:aws:sts::123456789123:assumed-role/tim"], operations=["Encrypt", "GenerateDataKey"], retiree=NotSpecified, constraints=NotSpecified, grant_tokens=NotSpecified)]
            )
        key2_expected.policy = Document(statements=[
            ResourcePolicyStatement(sid="", effect=NotSpecified, action=["kms:*"], notaction=NotSpecified, resource=["*"], notresource=NotSpecified, principal=[{"AWS": "arn:aws:iam::123456789123:root", "Federated": [], "Service": []}], notprincipal=NotSpecified, condition=NotSpecified, notcondition=NotSpecified)
            ])

        keys = EncryptionKeys(items={"key1": key1_expected, "key2": key2_expected})
        self.assertEqual(result, keys)

