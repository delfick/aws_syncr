from aws_syncr.errors import BadCredentials, AwsSyncrError
from aws_syncr.amazon.iam import Iam
from aws_syncr.amazon.s3 import S3
import boto3

from botocore.exceptions import ClientError

from contextlib import contextmanager
import logging

log = logging.getLogger("aws_syncr.amazon.amazon")

class Amazon(object):
    def __init__(self, environment, accounts, debug=False, dry_run=False):
        self.debug = debug
        self.dry_run = dry_run
        self.accounts = accounts
        self.environment = environment

        self.changes = False
        self.session = boto3.session.Session()

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

    @contextmanager
    def catch_invalid_credentials(self):
        try:
            yield
        except ClientError as error:
            if error.response["ResponseMetadata"]["HTTPStatsuCode"] == 403:
                raise BadCredentials("Failed to find valid credentials", error=error.message)
            else:
                raise

    @property
    def iam(self):
        iam = getattr(self, '_iam', None)
        if not iam:
            if not getattr(self, "_validated", False) and not getattr(self, "_validating", False):
                self.validate_account()
            iam = self._iam = Iam(self, self.environment, self.accounts, self.dry_run)
        return iam

    @property
    def s3(self):
        s3 = getattr(self, '_s3', None)
        if not s3:
            if not getattr(self, "_validated", False) and not getattr(self, "_validating", False):
                self.validate_account()
            s3 = self._s3 = S3(self, self.environment, self.accounts, self.dry_run)
        return s3

