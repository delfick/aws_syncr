from aws_syncr.option_spec.statements import resource_policy_statement_spec, resource_policy_dict, statement_spec
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.errors import BadTemplate, BadConfiguration
from aws_syncr.option_spec.documents import Document
from aws_syncr.amazon import bucket_acls as Acls

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb
from input_algorithms.spec_base import Spec
from input_algorithms.dictobj import dictobj
from input_algorithms import validators

from six.moves.urllib.parse import urlparse
from option_merge import MergedOptions
import hashlib
import json
import six

class buckets_spec(Spec):
    def normalise(self, meta, val):
        if 'use' in val:
            template = val['use']
            if template not in meta.everything['templates']:
                available = list(meta.everything['templates'].keys())
                raise BadTemplate("Template doesn't exist!", wanted=template, available=available, meta=meta)

            val = MergedOptions.using(meta.everything['templates'][template], val)

        formatted_string = sb.formatted(sb.string_or_int_as_string_spec(), MergedOptionStringFormatter, expected_type=six.string_types)
        bucket_name = meta.key_names()['_key_name_0']

        original_permission = sb.listof(resource_policy_dict()).normalise(meta.at("permission"), NotSpecified if "permission" not in val else val["permission"])
        deny_permission = sb.listof(resource_policy_dict(effect='Deny')).normalise(meta.at("deny_permission"), NotSpecified if "deny_permission" not in val else val["deny_permission"])
        allow_permission = sb.listof(resource_policy_dict(effect='Allow')).normalise(meta.at("allow_permission"), NotSpecified if "allow_permission" not in val else val["allow_permission"])

        # require_mfa_to_delete is an alias for this permission
        if val.get("require_mfa_to_delete") is True:
            delete_policy = {"action": "s3:DeleteBucket", "resource": { "s3": "__self__" }, "Condition": { "Bool": { "aws:MultiFactorAuthPresent": True } } }
            normalised_delete_policy = resource_policy_dict(effect='Allow').normalise(meta.at("require_mfa_to_delete"), delete_policy)
            allow_permission.append(normalised_delete_policy)

        val = val.wrapped()
        val['permission'] = original_permission + deny_permission + allow_permission

        return sb.create_spec(Bucket
            , acl = sb.defaulted(sb.match_spec((six.string_types, canned_acl_spec()), (dict, acl_statement_spec('acl', 'acl'))), None)
            , name = sb.overridden(bucket_name)
            , location = sb.defaulted(formatted_string, None)
            , permission = sb.container_spec(Document, sb.listof(resource_policy_statement_spec('bucket', bucket_name)))
            , tags = sb.dictof(sb.string_spec(), formatted_string)
            , website = sb.defaulted(website_statement_spec("website", "website"), None)
            , logging = sb.defaulted(logging_statement_spec("logging", "logging"), None)
            , lifecycle = sb.defaulted(sb.listof(lifecycle_statement_spec("lifecycle", "lifecycle")), None)
            ).normalise(meta, val)

class acl_grant_spec(statement_spec):
    args = lambda s, self_type, self_name: {
          "grantee": sb.or_spec(sb.string_choice_spec(["__owner__"]), acl_grantee_spec("grantee", "grantee"))
        , "permission": sb.string_choice_spec(["READ", "WRITE", "READ_ACP", "WRITE_ACP", "FULL_CONTROL"])
        }

    required = ["grantee", "permission"]

    def final_kls(self, *args, **kwargs):
        def ret(owner):
            result = {"Grantee": kwargs["grantee"], "Permission": kwargs["permission"]}
            if isinstance(kwargs['grantee'], six.string_types):
                if result["Grantee"] == "__owner__":
                    result["Grantee"] = owner
                else:
                    raise BadOption("Don't know how to deal with this grantee", grantee=kwargs['grantee'])
            return result
        return ret

class acl_grantee_spec(statement_spec):
    formatted_string = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
    args = lambda s, self_type, self_name: {
          (("sep", "_"), ("parts", ("display", "name"))): s.formatted_string
        , "id": s.formatted_string
        , "type": sb.string_choice_spec(["Group", "CanonicalUser"])
        , ("u", "r", "i"): s.formatted_string
        }

    required = ["type"]

    def final_kls(self, *args, **kwargs):
        result = {"ID": kwargs['id'], "DisplayName": kwargs["display_name"], "Type": kwargs["type"], "URI": kwargs["uri"]}
        return dict((key, val) for key, val in result.items() if val is not NotSpecified)

class acl_statement_spec(statement_spec):
    args = lambda s, self_type, self_name: {
          "grants": sb.listof(acl_grant_spec("grant", "grant"))
        }
    required = ["grants"]
    final_kls = lambda s, *args, **kwargs: lambda owner: {"AccessControlPolicy": {"Grants": [g(owner) for g in kwargs["grants"]]}}

class canned_acl_spec(sb.Spec):
    def normalise(self, meta, val):
        canned_acls = [
              "private", "public-read", "public-read-write", "aws-exec-read"
            , "authenticated-read", "log-delivery-write"
            ]

        acl = sb.defaulted(
              sb.formatted(sb.string_choice_spec(canned_acls), formatter=MergedOptionStringFormatter)
            , "private"
            ).normalise(meta, val)

        def ret(owner):
            """http://docs.aws.amazon.com/AmazonS3/latest/dev/acl-overview.html#canned-acl"""
            if acl == "private":
                new_grants = [Acls.FullControl(owner)]

            elif acl == "public-read":
                new_grants = [Acls.FullControl(owner), Acls.Read(Acls.AllUsersGroup)]

            elif acl == "public-read-write":
                new_grants = [Acls.FullControl(owner), Acls.Read(Acls.AllUsersGroup), Acls.Write(Acls.AllUsersGroup)]

            elif acl == "aws-exec-read":
                new_grants = [Acls.FullControl(owner), Acls.Read(Acls.EC2Group)]

            elif acl == "authenticated-read":
                new_grants = [Acls.FullControl(owner), Acls.Read(Acls.AuthenticatedUsersGroup)]

            elif acl == "log-delivery-write":
                new_grants = [Acls.FullControl(owner), Acls.Write(Acls.LogDeliveryGroup), Acls.ReadACP(Acls.LogDeliveryGroup)]

            return {"ACL": acl, "AccessControlPolicy": {"Grants": new_grants}}

        return ret

class lifecycle_statement_spec(statement_spec):
    formatted_string = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
    args = lambda s, self_type, self_name: {
          "id" : s.formatted_string
        , "enabled": sb.boolean()
        , "prefix" : s.formatted_string
        , "transition" : transition_spec("transition", "transition")
        , "expiration" : sb.or_spec(sb.integer_spec(), expiration_spec("expiration", "expiration"))
        , (("sep", "_"), ("parts", ("abort", "incomplete", "multipart", "upload"))): made_up_dict(sb.integer_spec(), ("DaysAfterInitiation", ))
        , (("sep", "_"), ("parts", ("noncurrent", "version", "transition"))): capitalized_only_spec()
        , (("sep", "_"), ("parts", ("noncurrent", "version", "expiration"))): capitalized_only_spec()
        }
    final_kls = lambda s, *args, **kwargs: LifeCycleConfig(*args, **kwargs)

class capitalized_only_spec(sb.Spec):
    def normalise_filled(self, meta, val):
        key = meta.key_names()["_key_name_0"]
        raise BadConfiguration("Don't support lower case variant of key, use capitialized variant", key=key, meta=meta)

class lower_only_spec(sb.Spec):
    def normalise_filled(self, meta, val):
        key = meta.key_names()["_key_name_0"]
        raise BadConfiguration("Don't support upper case variant of key, use lowercase variant", key=key, meta=meta)

class transition_spec(statement_spec):
    args = lambda s, self_type, self_name: {
          "days": sb.optional_spec(sb.integer_spec())
        , "date": capitalized_only_spec()
        , ("storage", "class"): sb.string_choice_spec(["GLACIER", "STANDARD_IA"])
        }
    required = ["storageclass"]
    conflicting = [('days', 'date')]
    validators = [validators.has_either(["days", "Days", "date", "Date"])]
    final_kls = lambda s, *args, **kwargs: LifecycleTransitionConfig(*args, **kwargs)

class expiration_spec(statement_spec):
    args = lambda s, self_type, self_name: {
          "days": sb.optional_spec(sb.integer_spec())
        , "date": capitalized_only_spec()
        , (("sep", "_"), ("parts", ("expired", "object", "delete", "marker"))): sb.optional_spec(sb.boolean())
        }
    conflicting = [('days', 'date', 'expired_object_delete_marker')]
    validators = [validators.has_either(["days", "Days", "date", "Date", "expired_object_delete_marker", "ExpiredObjectDeleteMarker"])]
    final_kls = lambda s, *args, **kwargs: LifecycleExpirationConfig(*args, **kwargs)

class logging_statement_spec(statement_spec):
    args = lambda s, self_type, self_name: {
          "prefix" : sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
        , "destination" : sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
        }
    required = ["prefix", "destination"]
    final_kls = lambda s, *args, **kwargs: LoggingConfig(*args, **kwargs)

class made_up_dict(sb.Spec):
    def setup(self, spec, path):
        self.spec = spec
        self.path = path

    def normalise(self, meta, val):
        val = self.spec.normalise(meta, val)

        start = result = {}
        for part in self.path[:-1]:
            result = result[part] = {}
        result[self.path[-1]] = val

        return start

class website_statement_spec(statement_spec):
    formatted_string = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
    args = lambda s, self_type, self_name: {
          (("sep", "_"), ("parts", ("index", "document"))): made_up_dict(s.formatted_string, ("Suffix", ))
        , (("sep", "_"), ("parts", ("error", "document"))): made_up_dict(s.formatted_string, ("Key", ))
        , (("sep", "_"), ("parts", ("redirect", "all", "requests", "to"))): redirect_all_requests_to_spec(s.formatted_string)
        , (("sep", "_"), ("parts", ("routing", "rules"))): sb.listof(sb.dictionary_spec())
        }
    final_kls = lambda s, *args, **kwargs: WebsiteConfig(*args, **kwargs)

class redirect_all_requests_to_spec(sb.Spec):
    def setup(self, spec):
        self.spec = spec

    def normalise_filled(self, meta, val):
        val = self.spec.normalise(meta, val)
        parsed = urlparse(val)
        if not parsed.scheme:
            return {"HostName": parsed.path}
        else:
            return {"HostName": parsed.netloc, "Protocol": parsed.scheme}

class LifecycleTransitionConfig(dictobj):
    fields = ["days", "date", "storageclass"]

    def as_dict(self):
        if self.days is not NotSpecified:
            return {"Days": self.days, "StorageClass": self.storageclass}
        elif self.date is not NotSpecified:
            return {"Date": self.date, "StorageClass": self.storageclass}

class LifecycleExpirationConfig(dictobj):
    fields = ["days", "date", "expired_object_delete_marker"]

    def as_dict(self):
        if self.days is not NotSpecified:
            return {"Days": self.days}
        elif self.date is not NotSpecified:
            return {"Date": self.date}
        else:
            return {"ExpiredObjectDeleteMarker": self.expired_object_delete_marker}

class LoggingConfig(dictobj):
    fields = ["prefix", "destination"]

    @property
    def document(self):
        return {
              "LoggingEnabled":
              { "TargetBucket": self.destination
              , "TargetPrefix": self.prefix
              }
            }

class WebsiteConfig(dictobj):
    fields = ['index_document', 'error_document', 'redirect_all_requests_to', 'routing_rules']

    @property
    def document(self):
        result = {
              "IndexDocument": self.index_document
            , "ErrorDocument": self.error_document
            , "RedirectAllRequestsTo": self.redirect_all_requests_to
            , "RoutingRules": self.routing_rules
            }

        return dict((key, val) for key, val in result.items() if val not in (None, NotSpecified))

class LifeCycleConfig(dictobj):
    fields = ['id', 'enabled', 'prefix', 'transition', 'expiration', 'noncurrent_version_transition', 'noncurrent_version_expiration', 'abort_incomplete_multipart_upload']

    @property
    def rule(self):

        # Expiration can be specified as just a number
        # Or as a dict
        # or not at all
        if type(self.expiration) is int:
            expiration_dict = {"Days": self.expiration}
        elif self.expiration is NotSpecified:
            expiration_dict = None
        else:
            expiration_dict = self.expiration.as_dict()

        enabled = True
        if self.enabled is not NotSpecified:
            enabled = self.enabled

        result = {
              "ID": self.id
            , "Status": "Enabled" if enabled else "Disabled"
            , "Prefix": self.prefix if self.prefix is not NotSpecified else ""
            , "Transition": self.transition.as_dict() if self.transition is not NotSpecified else None
            , "Expiration": expiration_dict
            , "NoncurrentVersionTransition": self.noncurrent_version_transition
            , "NoncurrentVersionExpiration": self.noncurrent_version_expiration
            , "AbortIncompleteMultipartUpload": self.abort_incomplete_multipart_upload
            }

        # Remove empty values
        result = dict((key, val) for key, val in result.items() if val not in (NotSpecified, None, {}))

        # Generate an ID so that we don't end up with a random aws ID
        # So that dry-run shows no changes where there are indeed no changes!
        if "ID" not in result:
            result["ID"] = hashlib.md5(json.dumps(sorted(result.items())).encode('utf-8')).hexdigest()

        return result

class Buckets(dictobj):
    fields = ['items']

    def sync_one(self, aws_syncr, amazon, bucket):
        """Make sure this bucket exists and has only attributes we want it to have"""
        if bucket.permission.statements:
            permission_document = bucket.permission.document
        else:
            permission_document = ""

        bucket_info = amazon.s3.bucket_info(bucket.name)
        if not bucket_info:
            amazon.s3.create_bucket(bucket.name, permission_document, bucket)
        else:
            amazon.s3.modify_bucket(bucket_info, bucket.name, permission_document, bucket)

class Bucket(dictobj):
    fields = {
          'name': "Name of the bucket"
        , 'acl': "The canned acl to give to this bucket"
        , 'location': "The region the bucket exists in"
        , 'permission': "The permission statements to attach to the bucket"
        , 'tags': "The tags to associate with the bucket"
        , 'website': "Any website configuration associated with the bucket"
        , 'logging': "Bucket logging configuration"
        , 'lifecycle': "Bucket lifecycle configuration"
        }

def __register__():
    return {(80, "buckets"): sb.container_spec(Buckets, sb.dictof(sb.string_spec(), buckets_spec()))}

