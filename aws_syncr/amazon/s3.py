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

    def create_bucket(self, name, permission_document, bucket):
        location = bucket.location
        acl = bucket.acl
        tags = bucket.tags
        website = bucket.website
        logging = bucket.logging
        lifecycle = bucket.lifecycle

        bucket = None
        with self.catch_boto_400("Couldn't Make bucket", bucket=name):
            for _ in self.change("+", "bucket", bucket=name):
                bucket = self.resource.create_bucket(Bucket=name, CreateBucketConfiguration={"LocationConstraint": location})

        if permission_document:
            with self.catch_boto_400("Couldn't add policy", "{0} Permission document".format(name), permission_document, bucket=name):
                for _ in self.change("+", "bucket_policy", bucket=name, document=permission_document):
                    self.resource.Bucket(name).Policy().put(Policy=permission_document)

        owner = "__owner__"
        if bucket:
            owner = bucket.Acl().owner
            if "ID" or "EmailAddress" in owner:
                owner["Type"] = "CanonicalUser"
            else:
                owner["Type"] = "Group"

        acl_options = acl(owner)
        if "ACL" in acl_options:
            if acl_options["ACL"] != "private":
                with self.catch_boto_400("Couldn't configure acl", bucket=name, canned_acl=acl):
                    for _ in self.change("+", "acl", bucket=name, acl=acl):
                        self.resource.Bucket(name).BucketAcl().put(ACL=acl)
        else:
            with self.catch_boto_400("Couldn't configure acl", bucket=name):
                for _ in self.change("+", "acl", bucket=name):
                    self.resource.Bucket(name).BucketAcl().put(**acl_options)

        if website:
            with self.catch_boto_400("Couldn't add website configuration", bucket=name):
                for _ in self.change("+", "website_configuration", bucket=name):
                    self.resource.BucketWebsite(name).put(WebsiteConfiguration=website.document)

        if logging:
            with self.catch_boto_400("Couldn't add logging configuration", bucket=name):
                for _ in self.change("+", "logging_configuration", bucket=name):
                    self.resource.BucketLogging(name).put(BucketLoggingStatus=logging.document)

        if lifecycle:
            with self.catch_boto_400("Couldn't add logging configuration", bucket=name):
                for _ in self.change("+", "lifecycle_configuration", bucket=name):
                    self.resource.BucketLifecycle(name).put(LifecycleConfiguration=sorted(l.rule for l in lifecycle))

        if tags:
            with self.catch_boto_400("Couldn't add tags", bucket=name):
                tag_set = [{"Value": val, "Key": key} for key, val in tags.items()]
                changes = list(Differ.compare_two_documents("[]", json.dumps(tag_set)))
                for _ in self.change("+", "bucket_tags", bucket=name, tags=tags, changes=changes):
                    self.resource.Bucket(name).Tagging().put(Tagging={"TagSet": tag_set})

    def modify_bucket(self, bucket_info, name, permission_document, bucket):
        location = bucket.location
        acl = bucket.acl
        tags = bucket.tags
        website = bucket.website
        logging = bucket.logging
        lifecycle = bucket.lifecycle

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

        self.modify_acl(bucket_info, name, acl)
        self.modify_website(bucket_info, name, website)
        self.modify_logging(bucket_info, name, logging)
        self.modify_tags(bucket_info, name, tags)
        self.modify_lifecycle(bucket_info, name, lifecycle)

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

    def modify_website(self, bucket_info, name, website):
        current_website = bucket_info.Website()
        current = {}
        with self.ignore_missing():
            current_website.load()
            current = {"IndexDocument": current_website.index_document, "ErrorDocument": current_website.error_document, "RedirectAllRequestsTo": current_website.redirect_all_requests_to, "RoutingRules": current_website.routing_rules}
            current = dict((key, val) for key, val in current.items() if val is not None)

        new_document = {}
        if website:
            new_document = website.document

        changes = list(Differ.compare_two_documents(json.dumps(current), json.dumps(new_document)))
        if changes:
            with self.catch_boto_400("Couldn't modify website configuration", bucket=name):
                symbol = "+" if not current else 'M'
                symbol = '-' if not new_document else symbol
                for _ in self.change(symbol, "website_configuration", bucket=name, changes=changes):
                    if new_document:
                        current_website.put(WebsiteConfiguration=new_document)
                    else:
                        current_website.delete()

    def modify_logging(self, bucket_info, name, logging):
        current_logging = bucket_info.Logging()
        current = {}
        with self.ignore_missing():
            current_logging.load()
            if current_logging.logging_enabled is None:
                current = {}
            else:
                current = {"LoggingEnabled": current_logging.logging_enabled}

        new_document = {}
        if logging:
            new_document = logging.document

        changes = list(Differ.compare_two_documents(json.dumps(current), json.dumps(new_document)))
        if changes:
            with self.catch_boto_400("Couldn't modify logging configuration", bucket=name):
                symbol = "+" if not current else 'M'
                symbol = '-' if not new_document else symbol
                for _ in self.change(symbol, "logging_configuration", bucket=name, changes=changes):
                    if new_document:
                        current_logging.put(BucketLoggingStatus=new_document)
                    else:
                        current_logging.put(BucketLoggingStatus={})

    def modify_lifecycle(self, bucket_info, name, lifecycle):
        current = []
        with self.ignore_missing():
            current_lifecycle = bucket_info.Lifecycle()
            current_lifecycle.load()
            current = current_lifecycle.rules

        new_rules = []
        if lifecycle:
            new_rules = sorted([l.rule for l in lifecycle])

        changes = list(Differ.compare_two_documents(json.dumps(current), json.dumps(new_rules)))
        if changes:
            with self.catch_boto_400("Couldn't modify lifecycle rules", bucket=name):
                symbol = "+" if not current else 'M'
                symbol = '-' if not new_rules else symbol
                for _ in self.change(symbol, "lifecycle_configuration", bucket=name, changes=changes):
                    if new_rules:
                        current_lifecycle.put(LifecycleConfiguration={"Rules": new_rules})
                    else:
                        current_lifecycle.put(LifecycleConfiguration={"Rules": []})

    def modify_acl(self, bucket_info, name, acl):
        current_acl = bucket_info.Acl()
        current_acl.load()
        current_grants = {"AccessControlPolicy": {"Grants": current_acl.grants}}

        owner = dict(current_acl.owner)
        if "ID" or "EmailAddress" in owner:
            owner["Type"] = "CanonicalUser"
        else:
            owner["Type"] = "Group"

        acl_options = acl(owner)
        if "ACL" in acl_options:
            current_grants["ACL"] = acl_options["ACL"]
        changes = list(Differ.compare_two_documents(json.dumps(current_grants), json.dumps(acl_options)))

        if changes:
            with self.catch_boto_400("Couldn't modify acl grants", bucket=name, canned_acl=acl):
                symbol = "+" if not current_grants else 'M'
                symbol = '-' if not acl_options else symbol
                for _ in self.change(symbol, "acl_grants", bucket=name, changes=changes, canned_acl=acl):
                    if "ACL" in acl_options and "AccessControlPolicy" in acl_options:
                        del acl_options["AccessControlPolicy"]
                    else:
                        # owner must be specified
                        # But we don't allow specifying owner in aws_syncr configuration
                        # So, we just set it to the current owner
                        acl_options["AccessControlPolicy"]["Owner"] = current_acl.owner

                    current_acl.put(**acl_options)

