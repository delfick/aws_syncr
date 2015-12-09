from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.errors import BadPolicy

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb
import six

class resource_spec_base(sb.Spec):
    def setup(self, resource, self_type, self_name):
        self.resource = resource
        self.self_type = self_type
        self.self_name = self_name

    def default_account_id(self, meta):
        accounts = meta.everything["accounts"]
        return accounts[meta.everything["aws_syncr"].environment]

    def accounts(self, meta):
        accounts = meta.everything["accounts"]
        default_account_id = self.default_account_id(meta)

        provided_accounts = sb.listof(sb.string_spec()).normalise(meta.at("account"), self.resource.get("account", []))
        if not provided_accounts:
            yield default_account_id

        for provided_account in provided_accounts:
            if not provided_account:
                yield ""
            else:
                if provided_account not in accounts:
                    raise BadPolicy("Unknown account specified", account=provided_account, meta=meta)
                else:
                    account_id = accounts[provided_account]

                yield account_id

    def default_location(self, meta):
        return meta.everything["aws_syncr"].location

    def location(self, meta):
        return sb.defaulted(sb.string_spec(), self.default_location(meta)).normalise(meta.at("location"), self.resource.get("location", NotSpecified))

class iam_specs(resource_spec_base):
    def normalise(self, meta, val):
        pairs = []
        has_self = False
        for account_id in self.accounts(meta):
            users = sb.listof(sb.string_spec()).normalise(meta.at("users"), self.resource.get('users', NotSpecified))
            for index, name in enumerate(sb.listof(sb.any_spec()).normalise(meta, val)):
                if name == "__self__":
                    if self.self_type != 'role':
                        raise BadPolicy("No __self__ iam role for this policy", meta=meta)
                    else:
                        has_self = True
                else:
                    if isinstance(name, six.string_types):
                        name = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter).normalise(meta.indexed_at(index), name)
                    pairs.append((name, account_id))

        if has_self:
            pairs.append(("role/{0}".format(self.self_name), self.default_account_id(meta)))

        for name, account_id in pairs:
            service = "sts" if name.startswith("assumed-role") else "iam"
            arn = "arn:aws:{0}::{1}:{2}".format(service, account_id, name)
            if not users:
                yield arn
            else:
                for user in users:
                    yield "{0}/{1}".format(arn, user)

class s3_specs(resource_spec_base):
    def normalise(self, meta, val):
        for bucket_key in sb.listof(sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)).normalise(meta, val):
            if bucket_key == "__self__" or bucket_key.startswith("__self__"):
                if self.self_type != "bucket":
                    raise BadPolicy("No __self__ bucket for this policy", meta=meta)
                else:
                    path = ""
                    if "/" in bucket_key:
                        path = bucket_key[bucket_key.find('/'):]
                    bucket_key = "{0}{1}".format(self.self_name, path)

            yield "arn:aws:s3:::{0}".format(bucket_key)
            if '/' not in bucket_key:
                yield "arn:aws:s3:::{0}/*".format(bucket_key)

class kms_specs(resource_spec_base):
    def normalise(self, meta, val):
        accounts = list(self.accounts(meta))
        if not accounts:
            accounts = [self.default_account_id(meta)]

        for account_id in accounts:
            string_or_dict = sb.or_spec(sb.string_spec(), sb.dictof(sb.string_choice_spec(["key_id", "alias"]), sb.string_spec()))
            for key_id in sb.listof(string_or_dict).normalise(meta, val):
                alias = None
                if key_id == "__self__" or (isinstance(key_id, dict) and (key_id.get("alias") == "__self__" or key_id.get("key_id") == "__self__")):
                    if self.self_type != "key":
                        raise BadPolicy("No __self__ key for this policy", meta=meta)
                    else:
                        alias = self.self_name
                        location = self.default_location(meta)
                else:
                    location = self.location(meta)

                if not alias:
                    if isinstance(key_id, six.string_types):
                        alias = key_id
                    else:
                        alias = key_id.get("alias")
                        key_id = key_id.get("key_id")

                if alias:
                    yield "arn:aws:kms:{0}:{1}:alias/{2}".format(location, account_id, alias)
                else:
                    yield "arn:aws:kms:{0}:{1}:key/{2}".format(location, account_id, key_id)

class arn_specs(resource_spec_base):
    def normalise(self, meta, val):
        default_location = ""

        if "identity" not in self.resource:
            raise BadPolicy("Generic arn specified without specifying 'identity'", meta=meta)

        location = self.location(meta)
        identities = sb.listof(sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)).normalise(meta.at("identity"), self.resource.get("identity"))

        for account_id in self.accounts(meta):
            for identity in identities:
                yield "arn:aws:{0}:{1}:{2}:{3}".format(val, location, account_id, identity)

class resource_spec(sb.Spec):
    def setup(self, self_type, self_name, only=None):
        self.only = only
        self.self_type = self_type
        self.self_name = self_name

    def normalise(self, meta, val):
        result = []
        for index, item in enumerate(sb.listof(sb.any_spec()).normalise(meta, val)):
            s3_spec = s3_specs(item, self.self_type, self.self_name)
            iam_spec = iam_specs(item, self.self_type, self.self_name)
            kms_spec = kms_specs(item, self.self_type, self.self_name)
            arn_spec = arn_specs(item, self.self_type, self.self_name)

            if isinstance(item, six.string_types):
                result.append(item)
            else:
                types = (("iam", iam_spec), ("kms", kms_spec), ("s3", s3_spec), ("arn", arn_spec))
                for typ, spec in types:
                    if typ in item:
                        if self.only and typ not in self.only:
                            raise BadPolicy("Sorry, don't support this resource type here", wanted=typ, available=self.only, meta=meta)

                        for found in spec.normalise(meta.indexed_at(index).at(typ), item[typ]):
                            result.append(found)
        return sorted(result)

