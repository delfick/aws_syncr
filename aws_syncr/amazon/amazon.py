from aws_syncr.errors import BadCredentials, AwsSyncrError
from aws_syncr.amazon.apigateway import ApiGateway
from aws_syncr.amazon.common import AmazonMixin
from aws_syncr.amazon.lambdas import Lambdas
from aws_syncr.amazon.route53 import Route53
from aws_syncr.amazon.iam import Iam
from aws_syncr.amazon.kms import Kms
from aws_syncr.amazon.s3 import S3
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
    lambdas = ValidatingMemoizedProperty(Lambdas, "_lambdas")
    route53 = ValidatingMemoizedProperty(Route53, "_route53")
    apigateway = ValidatingMemoizedProperty(ApiGateway, "_apigateway")

    def validate_account(self):
        """Make sure we are able to connect to the right account"""
        self._validating = True
        with self.catch_invalid_credentials():
            log.info("Finding a role to check the account id")
            a_role = list(self.iam.resource.roles.limit(1))
            if not a_role:
                raise AwsSyncrError("Couldn't find an iam role, can't validate the account....")
            account_id = a_role[0].meta.data['Arn'].split(":", 5)[4]

        chosen_account = self.accounts[self.environment]
        if chosen_account != account_id:
            raise BadCredentials("Don't have credentials for the correct account!", wanted=chosen_account, got=account_id)

        self._validating = False
        self._validated = True

