from aws_syncr.errors import BadPolicy

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb
import six

class iam_specs(sb.Spec):
    def setup(self, resource, self_type, self_name):
        self.resource = resource
        self.self_type = self_type
        self.self_name = self_name

    def normalise(self, meta, val):
        accounts = meta.everything["accounts"]
        default_account_id = accounts[meta.everything["aws_syncr"].environment]

        provided_accounts = sb.listof(sb.string_spec()).normalise(meta.at("account"), self.resource.get("account", ""))
        for provided_account in provided_accounts:
            account_id = default_account_id
            if provided_account:
                if provided_account not in accounts:
                    raise BadPolicy("Unknown account specified", account=provided_account, meta=meta)
                else:
                    account_id = accounts[provided_account]

        users = sb.listof(sb.string_spec()).normalise(meta.at("users"), self.resource.get('users', NotSpecified))
        for name in sb.listof(sb.any_spec()).normalise(meta, val):
            if name == "__self__":
                if self.self_type == 'bucket':
                    raise BadPolicy("Bucket policy has no __self__ iam role", meta=meta)

                account_id = default_account_id
                name = "role/{0}".format(self.self_name)

            service = "sts" if name.startswith("assumed-role") else "iam"
            arn = "arn:aws:{0}::{1}:{2}".format(service, account_id, name)
            if not users:
                yield arn
            else:
                for user in users:
                    yield "{0}/{1}".format(arn, user)

class s3_specs(sb.Spec):
    def setup(self, resource, self_type, self_name):
        self.resource = resource
        self.self_type = self_type
        self.self_name = self_name

    def normalise(self, meta, val):
        bucket_key = val

        if val == "__self__":
            if self.self_type == "role":
                raise BadPolicy("Role policy has no __self__ bucket", meta=meta)
            elif self.self_type == "key":
                raise BadPolicy("Key policy has no __self__ bucket", meta=meta)
            else:
                bucket_key = self.self_name

        yield "arn:aws:s3:::{0}".format(bucket_key)
        if '/' not in bucket_key:
            yield "arn:aws:s3:::{0}/*".format(bucket_key)

class kms_specs(sb.Spec):
    def setup(self, resource, self_type, self_name):
        self.resource = resource
        self.self_type = self_type
        self.self_name = self_name

    def normalise(self, meta, val):
        accounts = meta.everything["accounts"]
        default_location = meta.everything["aws_syncr"].location
        default_account_id = accounts[meta.everything["aws_syncr"].environment]

        for key_id in sb.listof(sb.string_spec()).normalise(meta, val):
            alias = None
            if key_id == "__self__":
                if self.self_type != "key":
                    raise BadPolicy("No __self__ key for this policy", meta=meta)
                else:
                    alias = self.self_name
                    location = default_location

            if not alias:
                if isinstance(key_id, six.string_types):
                    alias = key_id
                    location = sb.defaulted(sb.string_spec(), default_location).normalise(meta.at("location"), self.resource.get("location"))
                else:
                    alias = key_id.get("alias")
                    key_id = key_id.get("key_id")
                    location = sb.defaulted(sb.string_spec(), default_location).normalise(meta.at("location"), self.resource.get("location"))

            provided_accounts = sb.listof(sb.string_spec()).normalise(meta.at("account"), self.resource.get("account", ""))
            for provided_account in provided_accounts:
                account_id = default_account_id
                if provided_account:
                    if provided_account not in accounts:
                        raise BadPolicy("Unknown account specified", account=provided_account, meta=meta)
                    else:
                        account_id = accounts[provided_account]

                if alias:
                    yield "arn:aws:kms:{0}:{1}:alias/{2}".format(location, account_id, alias)
                else:
                    yield "arn:aws:kms:{0}:{1}:key/{2}".format(location, account_id, key_id)

class sns_specs(sb.Spec):
    def setup(self, resource, self_type, self_name):
        self.resource = resource
        self.self_type = self_type
        self.self_name = self_name

    def normalise(self, meta, val):
        accounts = meta.everything["accounts"]
        default_location = meta.everything["aws_syncr"].location
        default_account_id = accounts[meta.everything["aws_syncr"].environment]

        for key_id in sb.listof(sb.string_spec()).normalise(meta, val):
            location = sb.defaulted(sb.string_spec(), default_location).normalise(meta.at("location"), self.resource.get("location"))
            provided_accounts = sb.listof(sb.string_spec()).normalise(meta.at("account"), self.resource.get("account", ""))

            for provided_account in provided_accounts:
                account_id = default_account_id
                if provided_account:
                    if provided_account not in accounts:
                        raise BadPolicy("Unknown account specified", account=provided_account, meta=meta)
                    else:
                        account_id = accounts[provided_account]

                yield "arn:aws:sns:{0}:{1}:{2}".format(location, account_id, key_id)

class resource_spec(sb.Spec):
    def setup(self, self_type, self_name):
        self.self_type = self_type
        self.self_name = self_name

    def normalise(self, meta, val):
        result = []
        for index, item in enumerate(sb.listof(sb.any_spec()).normalise(meta, val)):
            s3_spec = s3_specs(item, self.self_type, self.self_name)
            iam_spec = iam_specs(item, self.self_type, self.self_name)
            kms_spec = kms_specs(item, self.self_type, self.self_name)
            sns_spec = sns_specs(item, self.self_type, self.self_name)

            if isinstance(item, six.string_types):
                result.append(item)
            else:
                types = (("iam", iam_spec), ("kms", kms_spec), ("sns", sns_spec), ("s3", s3_spec))
                for typ, spec in types:
                    if typ in item:
                        for found in spec.normalise(meta.indexed_at(index).at(typ), item[typ]):
                            result.append(found)
        return sorted(result)

