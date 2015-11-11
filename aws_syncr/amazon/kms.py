from aws_syncr.amazon.common import AmazonMixin
from aws_syncr.differ import Differ

import logging
import base64

log = logging.getLogger("aws_syncr.amazon.kms")

class Kms(AmazonMixin, object):
    def __init__(self, amazon, environment, accounts, dry_run):
        self.amazon = amazon
        self.dry_run = dry_run

        self.accounts = accounts
        self.account_id = accounts[environment]
        self.environment = environment

        self.clients = {}

    def get_client(self, location):
        if location not in self.clients:
            self.clients[location] = self.amazon.session.client('kms', location)
        return self.clients[location]

    def decrypt(self, location, secret):
        return self.get_client(location).decrypt(CiphertextBlob=base64.b64decode(secret))['Plaintext']

    def generate_data_key(self, location, key_id):
        return self.get_client(location).generate_data_key(KeyId=key_id, KeySpec="AES_256")

    def key_info(self, name, location):
        client = self.get_client(location)
        response = None
        with self.ignore_missing():
            response = client.describe_key(KeyId="alias/{0}".format(name))

        if response is None:
            return {}

        info = {"KeyId": response["KeyMetadata"]["KeyId"], "Description": response["KeyMetadata"]["Description"]}
        info['Policy'] = client.get_key_policy(KeyId=info["KeyId"], PolicyName="default")["Policy"]
        info['Grants'] = client.list_grants(KeyId=info["KeyId"])["Grants"]

        return info

    def create_key(self, name, description, location, grant, policy):
        client = self.get_client(location)
        with self.catch_boto_400("Couldn't create key", "{0} Policy".format(name), policy, alias=name):
            for _ in self.change("+", "kms_key", alias=name, document=policy):
                keyid = client.create_key(Description=description, Policy=policy)["KeyMetadata"]["KeyId"]

                with self.catch_boto_400("Couldn't create alias", alias=name, keyid=keyid):
                    client.create_alias(AliasName="alias/{0}".format(name), TargetKeyId=keyid)

                self.handle_grants(client, keyid, [], name, [g.statement for g in grant])

    def modify_key(self, key_info, name, description, location, grant, policy):
        client = self.get_client(location)
        if key_info["Description"] != description:
            with self.catch_boto_400("Couldn't change the description", alias=name):
                for _ in self.change("M", "kms_description", alias=name):
                    client.update_key_description(KeyId=key_info["KeyId"], Description=description)

        changes = list(Differ.compare_two_documents(key_info["Policy"], policy))
        if changes:
            with self.catch_boto_400("Couldn't modify policy", "Key {0} policy".format(name), policy, bucket=name):
                for _ in self.change("M", "key_policy", alias=name, changes=changes):
                    client.put_key_policy(KeyId=key_info["KeyId"], Policy=policy, PolicyName="default")

        self.handle_grants(client, key_info["KeyId"], key_info["Grants"], name, [g.statement for g in grant])

    def handle_grants(self, client, keyid, current_grants, name, new_grants):
        new = []
        revokable = []
        NotFound = type("NotFound", (object, ), {})

        def match(lst, grant):
            for l in lst:
                match = True
                for k, v in grant.items():
                    if k not in ("GrantId", "IssuingAccount"):
                        if type(v) is list:
                            if sorted(v) != sorted(l.get(k, [NotFound])):
                                match = False
                        elif k in l and l.get(k) != v:
                            match = False
                if match:
                    return True

        for grant in new_grants:
            if not match(current_grants, grant):
                new.append(grant)

        for grant in current_grants:
            if not match(new_grants, grant):
                revokable.append(grant)

        for grant in new:
            with self.catch_boto_400("Couldn't create grant", key=name):
                for _ in self.change("+", "key_grant", grantee=grant.get("GranteePrincipal"), retiree=grant.get("RetireePrincipal"), key=name):
                    client.create_grant(KeyId=keyid, **grant)

        for grant in revokable:
            with self.catch_boto_400("Couldn't revoke grant", key=name, grant=grant["GrantId"]):
                for _ in self.change("-", "key_grant", grantee=grant.get("GranteePrincipal"), retiree=grant.get("RetireePrincipal"), key=name, grant=grant["GrantId"]):
                    client.revoke_grant(KeyId=keyid, GrantId=grant["GrantId"])
