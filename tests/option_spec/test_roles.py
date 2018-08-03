# coding: spec

from aws_syncr.option_spec.statements import PermissionStatement, TrustStatement
from aws_syncr.option_spec.roles import role_spec, Role, Roles, __register__
from aws_syncr.option_spec.aws_syncr_specs import AwsSyncrSpec
from aws_syncr.option_spec.documents import Document
from aws_syncr.differ import Differ

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
from option_merge import MergedOptions
from input_algorithms.meta import Meta
from tests.helpers import TestCase
from textwrap import dedent
import uuid
import mock

describe TestCase, "role_spec":
    it "overrides the role name with the key of the specification":
        aws_syncr = mock.Mock(name="aws_syncr", environment="dev")
        spec = MergedOptions.using({"name": "overridden", "allow_to_assume_me": {"iam": "root"}})
        everything = {"roles": {"my_role": spec}, "accounts": {"dev": "123"}, "aws_syncr": aws_syncr}
        result = role_spec().normalise(Meta(everything, [('roles', ""), ('my_role', "")]), spec)
        self.assertEqual(result.name, "my_role")

    it "merges with a template":
        aws_syncr = mock.Mock(name="aws_syncr", environment="dev")
        ap1 = str(uuid.uuid1())
        ap2 = str(uuid.uuid1())
        everything = {"templates": {"blah": {"description": "Access to all the things!", "attached_policies": [ap1, ap2], "allow_to_assume_me": {"iam": "root"}}}, "accounts": {"dev": "123"}, "aws_syncr": aws_syncr}
        result = role_spec().normalise(Meta(everything, [('roles', ""), ("tree", "")]), {"use": "blah"})
        trust1 = {'sid': NotSpecified, 'notresource': NotSpecified, 'notcondition': NotSpecified, 'resource': NotSpecified, 'notprincipal': NotSpecified, 'condition': NotSpecified, 'principal': [{'AWS': 'arn:aws:iam::123:root'}], 'effect': NotSpecified, 'notaction': NotSpecified, 'action': NotSpecified}
        self.assertEqual(result, Role(name="tree", description="Access to all the things!", permission=Document([]), trust=Document([trust1]), make_instance_profile=False, attached_policies=[ap1, ap2]))

    it "combines permission, deny_permission and allow_permission":
        # p# = orginal statement
        # d# = permission_dict
        # r# = permission_statement
        p1, d1, r1 = mock.Mock(name="p1", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d1"), mock.Mock(name="r1")
        p2, d2, r2 = mock.Mock(name="p2", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d2"), mock.Mock(name="r2")
        p3, d3, r3 = mock.Mock(name="p3", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d3"), mock.Mock(name="r3")
        p4, d4, r4 = mock.Mock(name="p4", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d4"), mock.Mock(name="r4")
        p5, d5, r5 = mock.Mock(name="p5", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d5"), mock.Mock(name="r5")
        spec = MergedOptions.using({"permission": p1, "deny_permission": [p2, p3], "allow_permission": [p4, p5], "allow_to_assume_me": {"iam": "root"}})

        fake_permission_dict = mock.Mock(name="resource_policy_dict")
        fake_permission_dict.normalise.side_effect = lambda m, p: {p1:d1, p2:d2, p3:d3, p4:d4, p5:d5}[p]
        fake_permission_dict_kls = mock.Mock(name="permission_dict_kls", return_value=fake_permission_dict)

        fake_permission_statement_spec = mock.Mock(name="permission_statement_spec")
        fake_permission_statement_spec.normalise.side_effect = lambda m, p: {d1:r1, d2:r2, d3:r3, d4:r4, d5:r5}[p]
        fake_permission_statement_spec_kls = mock.Mock(name="permission_statement_spec_kls", return_value=fake_permission_statement_spec)

        aws_syncr = mock.Mock(name="aws_syncr", environment="dev")
        everything = {"accounts": {"dev": "123"}, "aws_syncr": aws_syncr}

        with mock.patch.multiple("aws_syncr.option_spec.roles", permission_dict=fake_permission_dict_kls, permission_statement_spec=fake_permission_statement_spec_kls):
            result = role_spec().normalise(Meta(everything, []).at("roles").at("stuff"), spec)
        self.assertEqual(result.permission.statements, [r1, r2, r3, r4, r5])

    it "combines allow_to_assume_me and disallow_to_assume_me to form trust":
        # p# = orginal statement
        # d# = trust_dict
        # r# = trust_statement
        p2, d2, r2 = mock.Mock(name="p2", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d2"), mock.Mock(name="r2")
        p3, d3, r3 = mock.Mock(name="p3", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d3"), mock.Mock(name="r3")
        p4, d4, r4 = mock.Mock(name="p4", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d4"), mock.Mock(name="r4")
        p5, d5, r5 = mock.Mock(name="p5", is_dict=True, spec=["is_dict", "get"]), mock.Mock(name="d5"), mock.Mock(name="r5")
        spec = MergedOptions.using({"disallow_to_assume_me": [p2, p3], "allow_to_assume_me": [p4, p5]})

        fake_trust_dict = mock.Mock(name="resource_policy_dict")
        fake_trust_dict.normalise.side_effect = lambda m, p: {p2:d2, p3:d3, p4:d4, p5:d5}[p]
        fake_trust_dict_kls = mock.Mock(name="trust_dict_kls", return_value=fake_trust_dict)

        fake_trust_statement_spec = mock.Mock(name="trust_statement_spec")
        fake_trust_statement_spec.normalise.side_effect = lambda m, p: {d2:r2, d3:r3, d4:r4, d5:r5}[p]
        fake_trust_statement_spec_kls = mock.Mock(name="trust_statement_spec_kls", return_value=fake_trust_statement_spec)

        with mock.patch.multiple("aws_syncr.option_spec.roles", trust_dict=fake_trust_dict_kls, trust_statement_spec=fake_trust_statement_spec_kls):
            result = role_spec().normalise(Meta({}, []).at("roles").at("stuff"), spec)
        self.assertEqual(result.trust.statements, [r4, r5, r2, r3])

describe TestCase, "Roles":
    describe "Syncing a role":
        before_each:
            self.name = "asldkfjlkajsdf/sdsadfkjl/asdfklj"
            self.description = mock.Mock(name="description")
            self.trust = mock.Mock(name="trust")
            self.permission = mock.Mock(name="permission")
            self.make_instance_profile = mock.Mock(name="make_instance_profile")
            self.attached_policies = mock.Mock(name="attached_policies")
            self.role = Role(name=self.name, description=self.description, trust=self.trust, permission=self.permission, make_instance_profile=self.make_instance_profile, attached_policies=self.attached_policies)
            self.roles = Roles(items={self.name: self.role})

            self.amazon = mock.Mock(name="amazon")
            self.aws_syncr = mock.Mock(name="aws_syncr")

        it "can create a role that doesn't exist":
            trust_document = self.trust.document = mock.Mock(name="trust_document")
            permission_document = self.permission.document = mock.Mock(name="permission_document")
            policy_name = "syncr_policy_{0}".format(self.name.replace('/', '__'))

            iam = self.amazon.iam = mock.Mock(name="iam")
            iam.role_info.return_value = {}
            self.roles.sync_one(self.aws_syncr, self.amazon, self.role)
            iam.role_info.assert_called_once_with(self.name)
            iam.create_role.assert_called_once_with(self.name, trust_document, policies={policy_name: permission_document}, attached_policies=self.attached_policies)

            iam.make_instance_profile.assert_called_once_with(self.name)

        it "does not create an instance profile if make_instance_profile is false":
            iam = self.amazon.iam = mock.Mock(name="iam")
            iam.role_info.return_value = {}
            self.role.make_instance_profile = False
            self.roles.sync_one(self.aws_syncr, self.amazon, self.role)
            self.assertEqual(iam.make_instance_profile.mock_calls, [])

        it "can modify a role that does exist":
            trust_document = self.trust.document = mock.Mock(name="trust_document")
            permission_document = self.permission.document = mock.Mock(name="permission_document")
            policy_name = "syncr_policy_{0}".format(self.name.replace('/', '__'))

            iam = self.amazon.iam = mock.Mock(name="iam")
            iam.role_info.return_value = {"name": self.name}
            self.roles.sync_one(self.aws_syncr, self.amazon, self.role)
            iam.role_info.assert_called_once_with(self.name)
            iam.modify_role.assert_called_once_with({"name": self.name}, self.name, trust_document, policies={policy_name: permission_document}, attached_policies=self.attached_policies)

            iam.make_instance_profile.assert_called_once_with(self.name)

        it "replaces slashes with double underscore for the policy name":
            iam = self.amazon.iam = mock.Mock(name="iam")
            iam.role_info.return_value = {}

            self.role.name = "role/somewhere/nice"
            self.role.make_instance_profile = False

            self.roles.sync_one(self.aws_syncr, self.amazon, self.role)
            self.assertEqual(iam.make_instance_profile.mock_calls, [])
            self.assertEqual(list(iam.create_role.mock_calls[0][2]['policies'].keys()), ["syncr_policy_role__somewhere__nice"])

describe TestCase, "__register__":
    before_each:
        # Need a valid folder to make aws_syncr
        with self.a_directory() as config_folder:
            self.aws_syncr = AwsSyncrSpec().aws_syncr_spec.normalise(Meta({}, []), {"environment": "dev", "config_folder": config_folder})

        self.u1 = {"iam": "role/bamboo/agent", "account": "stg"}
        self.u2 = {"iam": "assumed-role/Administrator", "users": "smoore"}
        self.u3 = {"iam": "assumed-role/NormalUser", "users": ["jon", "bob"]}

        self.p1 = {"Effect": "Allow", "Resource": "*", "Action": "s3:*"}
        self.p2 = {"effect": "Allow", "resource": {"iam": "role/everything" }, "action": "iam:Describe*"}
        self.p3 = {"resource": { "s3": "blah" }, "action": "s3:Head*"}

        self.p4 = {"resource": { "s3": "blah/path" }, "action": "s3:*"}
        self.p5 = {"resource": { "iam": "__self__" }, "action": "iam:*" }

        self.ap1 = str(uuid.uuid1())
        self.ap2 = str(uuid.uuid1())

        self.stuff_spec = {"description": "stuff!", "disallow_to_assume_me": self.u1, "permission": [self.p1, self.p2], "allow_permission": self.p3, "make_instance_profile": True, 'attached_policies': [self.ap1]}
        self.blah_spec = {"description": "blah!", "allow_to_assume_me": [self.u2, self.u3], "allow_permission": self.p4, "deny_permission": self.p5, "attached_policies": [self.ap2]}
        self.spec = {"stuff_role": self.stuff_spec, "blah_role": self.blah_spec}
        self.everything = MergedOptions.using({"roles": self.spec, "accounts": {"dev": "123456789123", "stg": "445829383783"}, "aws_syncr": self.aws_syncr}, dont_prefix=[dictobj])

    it "works":
        result = __register__()[(21, "roles")].normalise(Meta(self.everything, []).at("roles"), MergedOptions.using(self.spec))

        stuff_trust = [
              TrustStatement(sid=NotSpecified, effect=NotSpecified, action=NotSpecified, notaction=NotSpecified, resource=NotSpecified, notresource=NotSpecified, notprincipal=[{"AWS":"arn:aws:iam::445829383783:role/bamboo/agent"}], principal=NotSpecified, condition=NotSpecified, notcondition=NotSpecified)
            ]
        stuff_permission = [
              PermissionStatement(sid=NotSpecified, effect="Allow", action="s3:*", notaction=NotSpecified, resource="*", notresource=NotSpecified, condition=NotSpecified, notcondition=NotSpecified)
            , PermissionStatement(sid=NotSpecified, effect="Allow", action=["iam:Describe*"], notaction=NotSpecified, resource=["arn:aws:iam::123456789123:role/everything"], notresource=NotSpecified, condition=NotSpecified, notcondition=NotSpecified)
            , PermissionStatement(sid=NotSpecified, effect="Allow", action=["s3:Head*"], notaction=NotSpecified, resource=["arn:aws:s3:::blah", "arn:aws:s3:::blah/*"], notresource=NotSpecified, condition=NotSpecified, notcondition=NotSpecified)
            ]

        blah_trust = [
              TrustStatement(sid=NotSpecified, effect=NotSpecified, action=NotSpecified, notaction=NotSpecified, resource=NotSpecified, notresource=NotSpecified, principal=[{'AWS': "arn:aws:sts::123456789123:assumed-role/Administrator/smoore"}], notprincipal=NotSpecified, condition=NotSpecified, notcondition=NotSpecified)
            , TrustStatement(sid=NotSpecified, effect=NotSpecified, action=NotSpecified, notaction=NotSpecified, resource=NotSpecified, notresource=NotSpecified, principal=[{'AWS': ["arn:aws:sts::123456789123:assumed-role/NormalUser/bob", "arn:aws:sts::123456789123:assumed-role/NormalUser/jon"]}], notprincipal=NotSpecified, condition=NotSpecified, notcondition=NotSpecified)
            ]
        blah_permission = [
              PermissionStatement(sid=NotSpecified, effect="Deny", action=["iam:*"], notaction=NotSpecified, resource=["arn:aws:iam::123456789123:role/blah_role"], notresource=NotSpecified, condition=NotSpecified, notcondition=NotSpecified)
            , PermissionStatement(sid=NotSpecified, effect="Allow", action=["s3:*"], notaction=NotSpecified, resource=["arn:aws:s3:::blah/path"], notresource=NotSpecified, condition=NotSpecified, notcondition=NotSpecified)
            ]

        stuff_role = Role(name="stuff_role", description="stuff!", permission=Document(stuff_permission), trust=Document(stuff_trust), make_instance_profile=True, attached_policies=[self.ap1])
        blah_role = Role(name="blah_role", description="blah!", permission=Document(blah_permission), trust=Document(blah_trust), make_instance_profile=False, attached_policies=[self.ap2])

        roles = Roles(items={"stuff_role": stuff_role, "blah_role": blah_role})
        for name, role in roles.items.items():
            result_role = result.items[name]
            print("=== Role {0} ===".format(name))
            for statement1, statement2 in zip(result_role.permission.statements, role.permission.statements):
                for change in Differ.compare_two_documents(dict(statement1), dict(statement2)):
                    print(change)

            for statement1, statement2 in zip(result_role.trust.statements, role.trust.statements):
                for change in Differ.compare_two_documents(dict(statement1), dict(statement2)):
                    print(change)
        self.assertEqual(result, roles)

    it "can be used to get trust statements":
        meta = Meta(self.everything, []).at("roles")
        result = __register__()[(21, "roles")].normalise(meta, MergedOptions.using(self.spec))

        stuff_statement = dedent("""
            {
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Sid": "",
                  "Action": "sts:AssumeRole",
                  "Effect": "Allow",
                  "NotPrincipal": {
                    "AWS": "arn:aws:iam::445829383783:role/bamboo/agent"
                  }
                }
              ]
            }
        """)

        blah_statement = """
          {
            "Version": "2012-10-17",
            "Statement": [
              {
                "Sid": "",
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                  "AWS": "arn:aws:sts::123456789123:assumed-role/Administrator/smoore"
                }
              },
              {
                "Sid": "",
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                  "AWS": ["arn:aws:sts::123456789123:assumed-role/NormalUser/bob", "arn:aws:sts::123456789123:assumed-role/NormalUser/jon"]
                }
              }
            ]
          }
        """

        for name, generated, expected in (('stuff', result.items['stuff_role'].trust.document, stuff_statement), ('blah', result.items['blah_role'].trust.document, blah_statement)):
            print("=== Role {0} ===".format(name))
            changes = list(Differ.compare_two_documents(expected, generated))
            assert changes is not None
            self.assertEqual(len(changes), 0, '\n'.join(changes))

    it "can be used to get permission statements":
        meta = Meta(self.everything, []).at("roles")
        result = __register__()[(21, "roles")].normalise(meta, MergedOptions.using(self.spec))

        stuff_statement = dedent("""
            {
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Resource": "*",
                  "Action": "s3:*",
                  "Effect": "Allow"
                },
                {
                  "Resource": "arn:aws:iam::123456789123:role/everything",
                  "Action": "iam:Describe*",
                  "Effect": "Allow"
                },
                {
                  "Resource": ["arn:aws:s3:::blah", "arn:aws:s3:::blah/*"],
                  "Action": "s3:Head*",
                  "Effect": "Allow"
                }
              ]
            }
        """)

        blah_statement = """
          {
            "Version": "2012-10-17",
            "Statement": [
              {
                "Resource": "arn:aws:iam::123456789123:role/blah_role",
                "Action": "iam:*",
                "Effect": "Deny"
              },
              {
                "Resource": "arn:aws:s3:::blah/path",
                "Action": "s3:*",
                "Effect": "Allow"
              }
            ]
          }
        """

        for name, generated, expected in (('stuff', result.items['stuff_role'].permission.document, stuff_statement), ('blah', result.items['blah_role'].permission.document, blah_statement)):
            print("=== Role {0} ===".format(name))
            changes = list(Differ.compare_two_documents(expected, generated))
            assert changes is not None
            self.assertEqual(len(changes), 0, '\n'.join(changes))
