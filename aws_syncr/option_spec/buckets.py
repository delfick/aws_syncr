from aws_syncr.option_spec.statements import resource_policy_statement_spec, resource_policy_dict
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.documents import Document

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb
from input_algorithms.spec_base import Spec
from input_algorithms.dictobj import dictobj

import six

class buckets_spec(Spec):
    def normalise(self, meta, val):
        if 'use' in val:
            template = val['use']
            if template not in meta.everything['templates']:
                available = list(meta.everything['templates'].keys())
                raise BadTemplate("Template doesn't exist!", wanted=template, available=available, meta=meta)

            val = MergedOptions.using(meta.everything['templates'][template], val)

        formatted_string = sb.formatted(sb.string_spec(), MergedOptionStringFormatter, expected_type=six.string_types)
        bucket_name = meta.key_names()['_key_name_0']

        original_permission = sb.listof(resource_policy_dict()).normalise(meta.at("permission"), val.get("permission", NotSpecified))
        deny_permission = sb.listof(resource_policy_dict(effect='Deny')).normalise(meta.at("deny_permission"), val.get("deny_permission", NotSpecified))
        allow_permission = sb.listof(resource_policy_dict(effect='Allow')).normalise(meta.at("allow_permission"), val.get("allow_permission", NotSpecified))

        val['permission'] = original_permission + deny_permission + allow_permission
        return sb.create_spec(Bucket
            , name = sb.overridden(bucket_name)
            , location = sb.required(formatted_string)
            , permission = sb.container_spec(Document, sb.listof(resource_policy_statement_spec('bucket', bucket_name)))
            , tags = sb.dictof(sb.string_spec(), formatted_string)
            ).normalise(meta, val)

class Buckets(dictobj):
    fields = ['buckets']

class Bucket(dictobj):
    fields = {
          'name': "Name of the bucket"
        , 'location': "The region the bucket exists in"
        , 'permission': "The permission statements to attach to the bucket"
        , 'tags': "The tags to associate with the bucket"
        }

