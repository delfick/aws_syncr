from aws_syncr.amazon.common import AmazonMixin
from aws_syncr.operations.differ import Differ

import logging
import json

log = logging.getLogger("aws_syncr.amazon.s3")

class S3(AmazonMixin, object):
    def __init__(self, amazon, environment, accounts, dry_run):
        self.amazon = amazon
        self.dry_run = dry_run

        self.accounts = accounts
        self.account_id = accounts[environment]
        self.environment = environment

        self.resource = self.amazon.session.resource('s3')

    def bucket_info(self, bucket_name):
        bucket = self.resource.Bucket(bucket_name.split('/')[-1])
        with self.ignore_missing():
            bucket.load()
            return bucket

    def create_bucket(self, name, permission_document, location, tags):
        with self.catch_boto_400("Couldn't Make bucket", bucket=name):
            for _ in self.change("+", "bucket", bucket=name, document=permission_document):
                self.resource.create_bucket(Bucket=name, CreateBucketConfiguration={"LocationConstraint": location})

        if permission_document:
            with self.catch_boto_400("Couldn't add policy", "{0} Permission document".format(name), permission_document, bucket=name):
                for _ in self.change("+", "bucket_policy", bucket=name, document=permission_document):
                    self.resource.Bucket(name).Policy().put(Policy=permission_document)

        if tags:
            with self.catch_boto_400("Couldn't add tags", bucket=name):
                tag_set = self.make_tag_set(tags)
                changes = list(Differ.compare_two_documents("{}", json.dumps(tag_set)))
                for _ in self.change("+", "bucket_tags", bucket=name, tags=tags, changes=changes):
                    self.resource.Bucket(name).Tagging().put(Tagging={"TagSet": tag_set})

    def modify_bucket(self, bucket_info, name, permission_document, location, tags):
        bucket_document = ""
        with self.ignore_missing():
            bucket_document = bucket_info.Policy().policy

        if bucket_document or permission_document:
            if permission_document and not bucket_document:
                with self.catch_boto_400("Couldn't add policy", "Bucket {0} policy".format(name), permission_document, bucket=name):
                    for _ in self.change("+", "bucket_policy", bucket=name, changes=list(Differ.compare_two_documents("{}", permission_document))):
                        bucket_info.Policy().put(Policy=permission_document)

            elif bucket_document and not permission_document:
                with self.catch_boto_400("Couldn't remove policy", "Bucket {0} policy".format(name), permission_document, bucket=name):
                    for _ in self.change("-", "bucket_policy", bucket=name, changes=list(Differ.compare_two_documents(bucket_document, "{}"))):
                        bucket_info.Policy().delete()

            else:
                changes = list(Differ.compare_two_documents(bucket_document, permission_document))
                if changes:
                    with self.catch_boto_400("Couldn't modify policy", "Bucket {0} policy".format(name), permission_document, bucket=name):
                        for _ in self.change("M", "bucket_policy", bucket=name, changes=changes):
                            bucket_info.Policy().put(Policy=permission_document)

        self.modify_tags(bucket_info, name, tags)

    def modify_tags(self, bucket_info, name, tags):
        current_tags = bucket_info.Tagging()
        current_tags.load()
        current_vals = {}
        for tag in current_tags.tag_set:
            key = tag["Key"]
            val = tag["Value"]
            if key not in current_vals:
                current_vals[key] = []
            current_vals[key].append(val)

        changes = list(Differ.compare_two_documents(json.dumps(current_vals), json.dumps(tags)))
        if changes:
            new_tag_set = self.make_tag_set(tags)
            with self.catch_boto_400("Couldn't modify tags", bucket=name):
                symbol = "+" if new_tag_set else "-"
                symbol = "M" if new_tag_set and current_vals else symbol
                for _ in self.change(symbol, "bucket_tags", bucket=name, changes=changes):
                    bucket_info.Tagging().put(Tagging={"TagSet": new_tag_set})

    def make_tag_set(self, tags):
        new_tag_set = []
        for key, val in tags.items():
            if not isinstance(val, list):
                val = [val]

            for v in val:
                new_tag_set.append({"Value": v, "Key": key})
        return new_tag_set

