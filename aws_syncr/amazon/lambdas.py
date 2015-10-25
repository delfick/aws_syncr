from aws_syncr.amazon.common import AmazonMixin
from aws_syncr.differ import Differ

import logging

log = logging.getLogger("aws_syncr.amazon.lambdas")

class Lambdas(AmazonMixin, object):
    def __init__(self, amazon, environment, accounts, dry_run):
        self.amazon = amazon
        self.dry_run = dry_run

        self.accounts = accounts
        self.account_id = accounts[environment]
        self.environment = environment

    def function_info(self, function_name, location):
        with self.ignore_missing():
            return self.amazon.session.client('lambda', location).get_function(FunctionName=function_name)

    def create_function(self, name, description, location, runtime, role, handler, timeout, memory_size, code):
        client = self.amazon.session.client('lambda', location)
        with self.catch_boto_400("Couldn't Make function", function=name):
            for _ in self.change("+", "function", bucket=name):
                kwargs = dict(
                      FunctionName=name, Runtime=runtime, role=role, handler=handler
                    , description = description, Timeout=timeout, MemorySize=memory_size
                    , Publish = True
                    )

                if code.s3_address:
                    kwargs["Code"] = {}
                    kwargs["Code"]["Key"] = code.key
                    kwargs["Code"]["S3Bucket"] = code.bucket
                    if code.version is not NotSpecified:
                        kwargs["Code"]["S3ObjectVersion"] = code.version

                with code.zipfile() as location:
                    if location:
                        kwargs["Code"] = {"ZipFile": location}

                    client.create_function(**kwargs)

    def modify_function(self, function_info, name, description, location, runtime, role, handler, timeout, memory_size, code):
        client = self.amazon.session.client('lambda', location)

        wanted = dict(
              FunctionName=name, Role=role, Handler=handler
            , Description=description, Timeout=timeout, MemorySize=memory_size
            )

        current = dict((key, function_info["Configuration"][key]) for key in (
              "FunctionName", "Role", "Handler", "Description", "Timeout", "MemorySize"
            )
        )

        changes = list(Differ.compare_two_documents(current, wanted))
        if changes:
            with self.catch_boto_400("Couldn't modify function", function=name):
                for _ in self.change("M", "function", changes=changes, function=name):
                    client.update_function_configuration(**wanted)

