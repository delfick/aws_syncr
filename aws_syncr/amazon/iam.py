from aws_syncr.amazon.common import AmazonMixin
from aws_syncr.differ import Differ

from botocore.exceptions import ClientError
import boto3

import logging
import json
import os

log = logging.getLogger("aws_syncr.amazon.iam")

class Iam(AmazonMixin, object):
    def __init__(self, amazon, environment, accounts, dry_run):
        self.amazon = amazon
        self.dry_run = dry_run

        self.accounts = accounts
        self.account_id = accounts[environment]
        self.environment = environment

        self.client = self.amazon.session.client("iam")
        self.resource = self.amazon.session.resource('iam')

    def role_info(self, role_name):
        role = self.resource.Role(role_name.split('/')[-1])
        with self.ignore_missing():
            role.load()
            return role

    def create_role(self, name, trust_document, policies, attached_policies):
        with self.catch_boto_400("Couldn't Make role", "{0} assume document".format(name), trust_document, role=name):
            for _ in self.change("+", "role", role=name, document=trust_document):
                kwargs = {"RoleName": name, "AssumeRolePolicyDocument": trust_document}
                if '/' in name:
                    kwargs["RoleName"] = name.split('/')[-1]
                    kwargs["Path"] = "/{0}/".format('/'.join(name.split('/')[:-1]))
                self.resource.create_role(**kwargs)

        if policies:
            for policy_name, document in policies.items():
                if document:
                    with self.catch_boto_400("Couldn't add policy", "{0} - {1} Permission document".format(name, policy_name), document, role=name, policy_name=policy_name):
                        for _ in self.change("+", "role_policy", role=name, policy=policy_name, document=document):
                            self.resource.RolePolicy(name.split('/')[-1], policy_name).put(PolicyDocument=document)

        self.modify_attached_policies(name, attached_policies)

    def modify_role(self, role_info, name, trust_document, policies, attached_policies):
        changes = list(Differ.compare_two_documents(json.dumps(role_info.assume_role_policy_document), trust_document))
        if changes:
            with self.catch_boto_400("Couldn't modify trust document", "{0} assume document".format(name), trust_document, role=name):
                for _ in self.change("M", "trust_document", role=name, changes=changes):
                    self.resource.AssumeRolePolicy(name.split('/')[-1]).update(PolicyDocument=trust_document)

        with self.catch_boto_400("Couldn't get policies for a role", role=name):
            current_policies = dict((policy.name, policy) for policy in role_info.policies.all())
        unknown = [key for key in current_policies if key not in policies]

        if unknown:
            log.info("Role has unknown policies that will be disassociated\trole=%s\tunknown=%s", name, unknown)
            for policy in unknown:
                with self.catch_boto_400("Couldn't delete a policy from a role", policy=policy, role=name):
                    for _ in self.change("-", "role_policy", role=name, policy=policy):
                        current_policies[policy].delete()

        for policy, document in policies.items():
            has_statements = document and bool(json.loads(document)["Statement"])
            if not has_statements:
                if policy in current_policies:
                    with self.catch_boto_400("Couldn't delete a policy from a role", policy=policy, role=name):
                        for _ in self.change("-", "policy", role=name, policy=policy):
                            current_policies[policy].delete()
            else:
                needed = False
                changes = None

                if policy in current_policies:
                    changes = list(Differ.compare_two_documents(json.dumps(current_policies.get(policy).policy_document), document))
                    if changes:
                        log.info("Overriding existing policy\trole=%s\tpolicy=%s", name, policy)
                        needed = True
                else:
                    log.info("Adding policy to existing role\trole=%s\tpolicy=%s", name, policy)
                    needed = True

                if needed:
                    with self.catch_boto_400("Couldn't add policy document", "{0} - {1} policy document".format(name, policy), document, role=name, policy=policy):
                        symbol = "M" if changes else "+"
                        for _ in self.change(symbol, "role_policy", role=name, policy=policy, changes=changes, document=document):
                            if policy in current_policies:
                                current_policies[policy].put(PolicyDocument=document)
                            else:
                                self.client.put_role_policy(RoleName=name.split("/")[-1], PolicyName=policy, PolicyDocument=document)

            self.modify_attached_policies(name, attached_policies)

    def make_instance_profile(self, name):
        role_name = name.split('/')[-1]
        existing_roles_in_profile = None
        with self.ignore_missing():
            existing_roles_in_profile = self.resource.InstanceProfile(role_name).roles

        if existing_roles_in_profile is None:
            with self.catch_boto_400("Couldn't create instance profile", instance_profile=name):
                for _ in self.change("+", "instance_profile", profile=role_name):
                    self.client.create_instance_profile(InstanceProfileName=role_name)

        if existing_roles_in_profile and any(rl.name != role_name for rl in existing_roles_in_profile):
            for role in [rl for rl in existing_roles_in_profile if rl.name != role_name]:
                with self.catch_boto_400("Couldn't remove role from an instance profile", profile=role_name, role=role):
                    for _ in self.change("-", "instance_profile_role", profile=role_name, role=role):
                        self.resource.InstanceProfile(role_name).remove_role(RoleName=role)

        if not existing_roles_in_profile or not any(rl.name == role_name for rl in existing_roles_in_profile):
            try:
                with self.catch_boto_400("Couldn't add role to an instance profile", role=name, instance_profile=role_name):
                    for _ in self.change("+", "instance_profile_role", profile=role_name, role=role_name):
                        self.resource.InstanceProfile(role_name).add_role(RoleName=role_name)
            except ClientError as error:
                if error.response["ResponseMetadata"]["HTTPStatusCode"] == 409:
                    # I'd rather ignore this conflict, than list all the instance_profiles
                    # Basically, the instance exists but isn't associated with the role
                    pass
                else:
                    raise

    def modify_attached_policies(self, role_name, new_policies):
        """Make sure this role has just the new policies"""
        parts = role_name.split('/', 1)
        if len(parts) == 2:
            prefix, name = parts
            prefix = "/{0}/".format(prefix)
        else:
            prefix = "/"
            name = parts[0]

        current_attached_policies = []
        with self.ignore_missing():
            current_attached_policies = self.client.list_attached_role_policies(RoleName=name)
            current_attached_policies = [p['PolicyArn'] for p in current_attached_policies["AttachedPolicies"]]

        new_attached_policies = ["arn:aws:iam::aws:policy/{0}".format(p) for p in new_policies]

        changes = list(Differ.compare_two_documents(current_attached_policies, new_attached_policies))
        if changes:
            with self.catch_boto_400("Couldn't modify attached policies", role=role_name):
                for policy in new_attached_policies:
                    if policy not in current_attached_policies:
                        for _ in self.change("+", "attached_policy", role=role_name, policy=policy):
                            self.client.attach_role_policy(RoleName=name, PolicyArn=policy)

                for policy in current_attached_policies:
                    if policy not in new_attached_policies:
                        for _ in self.change("-", "attached_policy", role=role_name, changes=changes, policy=policy):
                            self.client.detach_role_policy(RoleName=name, PolicyArn=policy)

    def assume_role_credentials(self, arn):
        """Return the environment variables for an assumed role"""
        log.info("Assuming role as %s", arn)

        # Clear out empty values
        for name in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SECURITY_TOKEN', 'AWS_SESSION_TOKEN']:
            if name in os.environ and not os.environ[name]:
                del os.environ[name]

        sts = self.amazon.session.client("sts")
        with self.catch_boto_400("Couldn't assume role", arn=arn):
            creds = sts.assume_role(RoleArn=arn, RoleSessionName="aws_syncr")

        return {
              'AWS_ACCESS_KEY_ID': creds["Credentials"]["AccessKeyId"]
            , 'AWS_SECRET_ACCESS_KEY': creds["Credentials"]["SecretAccessKey"]
            , 'AWS_SECURITY_TOKEN': creds["Credentials"]["SessionToken"]
            , 'AWS_SESSION_TOKEN': creds["Credentials"]["SessionToken"]
            }

