from aws_syncr.errors import BadCredentials, AwsSyncrError
from aws_syncr.amazon.common import AmazonMixin
from aws_syncr.amazon.iam import Iam
from aws_syncr.amazon.s3 import S3
from aws_syncr.amazon.kms import Kms
import boto3

import logging

log = logging.getLogger("aws_syncr.amazon.amazon")

class ValidatingMemoizedProperty(object):
    def __init__(self, kls, key):
        self.kls = kls
        self.key = key

    def __get__(self, instance, owner):
        obj = getattr(instance, self.key, None)
        if not obj:
            if not getattr(instance, "_validated", False) and not getattr(instance, "_validating", False):
                instance.validate_account()
            obj = self.kls(instance, instance.environment, instance.accounts, instance.dry_run)
            setattr(instance, self.key, obj)
        return obj

class Amazon(AmazonMixin, object):
    def __init__(self, environment, accounts, debug=False, dry_run=False):
        self.debug = debug
        self.dry_run = dry_run
        self.accounts = accounts
        self.environment = environment

        self.changes = False
        self.session = boto3.session.Session()

    s3 = ValidatingMemoizedProperty(S3, "_s3")
    iam = ValidatingMemoizedProperty(Iam, "_iam")
    kms = ValidatingMemoizedProperty(Kms, "_kms")

    @property
    def all_roles(self):
        if not hasattr(self, "_all_roles"):
            self.validate_account()
        return self._all_roles

    @property
    def all_users(self):
        if not hasattr(self, "_all_users"):
            self.validate_account()
        return self._all_users

    def validate_account(self):
        """Make sure we are able to connect to the right account"""
        self._validating = True
        with self.catch_invalid_credentials():
            log.info("Finding a role to check the account id")
            all_roles = self._all_roles = list(self.iam.resource.roles.all())
            if not all_roles:
                raise AwsSyncrError("Couldn't find an iam role, can't validate the account....")
            account_id = all_roles[0].meta.data['Arn'].split(":", 5)[4]

        chosen_account = self.accounts[self.environment]
        if chosen_account != account_id:
            raise BadCredentials("Don't have credentials for the correct account!", wanted=chosen_account, got=account_id)

        with self.catch_invalid_credentials():
            log.info("Finding users in your account")
            self._all_users = list(self.iam.resource.users.all())

        self._validating = False
        self._validated = True

