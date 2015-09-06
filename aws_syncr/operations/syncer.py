class Syncer(object):
    def __init__(self, aws_syncr, amazon):
        self.amazon = amazon
        self.aws_syncr = aws_syncr

    def sync_role(self, role):
        """Make sure this role exists and has only what policies we want it to have"""
        trust_document = role.trust.document
        permission_document = role.permission.document
        policy_name = "syncr_policy_{0}".format(role.name.replace('/', '__'))

        role_info = self.amazon.iam.role_info(role.name)
        if not role_info:
            self.amazon.iam.create_role(role.name, trust_document, policies={policy_name: permission_document})
        else:
            self.amazon.iam.modify_role(role_info, role.name, trust_document, policies={policy_name: permission_document})

        if role.make_instance_profile:
            self.amazon.iam.make_instance_profile(role.name)

    def sync_bucket(self, bucket):
        """Make sure this bucket exists and has only attributes we want it to have"""
        if bucket.permission.statements:
            permission_document = bucket.permission.document
        else:
            permission_document = ""

        bucket_info = self.amazon.s3.bucket_info(bucket.name)
        if not bucket_info:
            self.amazon.s3.create_bucket(bucket.name, permission_document, bucket.location, bucket.tags)
        else:
            self.amazon.s3.modify_bucket(bucket_info, bucket.name, permission_document, bucket.location, bucket.tags)

