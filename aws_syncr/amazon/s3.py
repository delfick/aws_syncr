from aws_syncr.amazon.common import AmazonMixin
from aws_syncr.errors import AwsSyncrError
from aws_syncr.differ import Differ

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

        self.client = self.amazon.session.client("s3")
        self.resource = self.amazon.session.resource('s3')

    def bucket_info(self, bucket_name):
        bucket = self.resource.Bucket(bucket_name.split('/')[-1])
        with self.ignore_missing():
            bucket.load()
            return bucket

    def create_bucket(self, name, permission_document, location, tags):
        with self.catch_boto_400("Couldn't Make bucket", bucket=name):
            for _ in self.change("+", "bucket", bucket=name):
                self.resource.create_bucket(Bucket=name, CreateBucketConfiguration={"LocationConstraint": location})

        if permission_document:
            with self.catch_boto_400("Couldn't add policy", "{0} Permission document".format(name), permission_document, bucket=name):
                for _ in self.change("+", "bucket_policy", bucket=name, document=permission_document):
                    self.resource.Bucket(name).Policy().put(Policy=permission_document)

        if tags:
            with self.catch_boto_400("Couldn't add tags", bucket=name):
                tag_set = [{"Value": val, "Key": key} for key, val in tags.items()]
                changes = list(Differ.compare_two_documents("[]", json.dumps(tag_set)))
                for _ in self.change("+", "bucket_tags", bucket=name, tags=tags, changes=changes):
                    self.resource.Bucket(name).Tagging().put(Tagging={"TagSet": tag_set})

    def modify_bucket(self, bucket_info, name, permission_document, location, tags):
        current_location = self.client.get_bucket_location(Bucket=name)['LocationConstraint']
        if current_location != location:
            raise AwsSyncrError("Sorry, can't change the location of a bucket!", wanted=location, currently=current_location, bucket=name)

        # Make sure we use the correct endpoint to get info from the bucket
        # So that website buckets don't complain
        bucket_info.meta.client = self.amazon.session.client("s3", location)

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
        tag_set = []
        with self.ignore_missing():
            current_tags.load()
            tag_set = current_tags.tag_set
        current_vals = dict((tag["Key"], tag["Value"]) for tag in tag_set)

        changes = list(Differ.compare_two_documents(json.dumps(current_vals), json.dumps(tags)))
        if changes:
            new_tag_set = [{"Value": val, "Key": key} for key, val in tags.items()]
            with self.catch_boto_400("Couldn't modify tags", bucket=name):
                symbol = "+" if new_tag_set else "-"
                symbol = "M" if new_tag_set and current_vals else symbol
                for _ in self.change(symbol, "bucket_tags", bucket=name, changes=changes):
                    if not new_tag_set:
                        bucket_info.Tagging().delete()
                    else:
                        bucket_info.Tagging().put(Tagging={"TagSet": new_tag_set})

