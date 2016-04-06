from aws_syncr.option_spec.statements import resource_policy_statement_spec, resource_policy_dict, statement_spec
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.documents import Document
from aws_syncr.errors import BadTemplate

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb
from input_algorithms.spec_base import Spec
from input_algorithms.dictobj import dictobj

from six.moves.urllib.parse import urlparse
from option_merge import MergedOptions
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
            , name = sb.overridden(bucket_name)
            , location = sb.defaulted(formatted_string, None)
            , permission = sb.container_spec(Document, sb.listof(resource_policy_statement_spec('bucket', bucket_name)))
            , tags = sb.dictof(sb.string_spec(), formatted_string)
            , website = sb.optional_spec(website_statement_spec("website", "website"))
            ).normalise(meta, val)

class website_statement_spec(statement_spec):
    args = lambda s, self_type, self_name: {
          (("sep", "_"), ("parts", ("index", "document"))): sb.required(sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter))
        , (("sep", "_"), ("parts", ("error", "document"))): sb.required(sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter))
        , (("sep", "_"), ("parts", ("redirect", "all", "requests", "to"))): sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
        , (("sep", "_"), ("parts", ("routing", "rules"))): sb.dictionary_spec()
        }
    final_kls = lambda s, *args, **kwargs: WebsiteConfig(*args, **kwargs)

class WebsiteConfig(dictobj):
    fields = ['index_document', 'error_document', 'redirect_all_requests_to', 'routing_rules']

    @property
    def document(self):
        rart = None
        routing_rules = None
        if self.routing_rules is not NotSpecified:
            routing_rules = self.routing_rules
        if self.redirect_all_requests_to is not NotSpecified and self.redirect_all_requests_to:
            parsed = urlparse(self.redirect_all_requests_to)
            if not parsed.scheme:
                rart = {"HostName": parsed.path}
            else:
                rart = {"HostName": parsed.netloc, "Protocol": parsed.scheme}

        result = {
              "IndexDocument": None if self.index_document is NotSpecified else {"Suffix": self.index_document}
            , "ErrorDocument": None if self.error_document is NotSpecified else {"Key": self.error_document}
            , "RedirectAllRequestsTo": rart
            , "RoutingRules": routing_rules
            }

        return dict((key, val) for key, val in result.items() if val is not None)

class Buckets(dictobj):
    fields = ['items']

    def sync_one(self, aws_syncr, amazon, bucket):
        """Make sure this bucket exists and has only attributes we want it to have"""
        if bucket.permission.statements:
            permission_document = bucket.permission.document
        else:
            permission_document = ""

        if bucket.website is NotSpecified:
            bucket.website = None

        bucket_info = amazon.s3.bucket_info(bucket.name)
        if not bucket_info:
            amazon.s3.create_bucket(bucket.name, permission_document, bucket.location, bucket.tags, bucket.website)
        else:
            amazon.s3.modify_bucket(bucket_info, bucket.name, permission_document, bucket.location, bucket.tags, bucket.website)

class Bucket(dictobj):
    fields = {
          'name': "Name of the bucket"
        , 'location': "The region the bucket exists in"
        , 'permission': "The permission statements to attach to the bucket"
        , 'tags': "The tags to associate with the bucket"
        , 'website': "Any website configuration associated with the bucket"
        }

def __register__():
    return {(80, "buckets"): sb.container_spec(Buckets, sb.dictof(sb.string_spec(), buckets_spec()))}

