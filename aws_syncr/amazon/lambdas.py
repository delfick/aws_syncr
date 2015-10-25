from aws_syncr.amazon.common import AmazonMixin
from aws_syncr.differ import Differ

from contextlib import contextmanager
import logging
import base64
import json

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

    @contextmanager
    def code_options(self, code):
        options = {}
        if code.s3_address:
            options["Key"] = code.key
            options["S3Bucket"] = code.bucket
            if code.version is not NotSpecified:
                options["S3ObjectVersion"] = code.version
            yield options
        else:
            with code.zipfile() as location:
                if location:
                    yield {"ZipFile": open(location, 'rb').read()}

    def create_function(self, name, description, location, runtime, role, handler, timeout, memory_size, code):
        client = self.amazon.session.client('lambda', location)
        with self.catch_boto_400("Couldn't Make function", function=name):
            for _ in self.change("+", "function", function=name):
                kwargs = dict(
                      FunctionName=name, Runtime=runtime, Role=role, Handler=handler
                    , Description = description, Timeout=timeout, MemorySize=memory_size
                    )

                with self.code_options(code) as options:
                    kwargs["Code"] = options
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

    def deploy_function(self, name, code, location):
        client = self.amazon.session.client('lambda', location)
        with self.code_options(code) as options:
            for _ in self.change("D", "function", function=name):
                with self.catch_boto_400("Couldn't deploy function", function=name):
                    return client.update_function_code(FunctionName=name, **options)

    def test_function(self, name, event, location):
        client = self.amazon.session.client('lambda', location)
        log.info("Invoking function %s", name)
        res = client.invoke(FunctionName=name, InvocationType="RequestResponse", Payload=event, LogType="Tail")
        res['Payload'] = json.loads(res['Payload'].read().decode('utf-8'))
        if 'LogResult' in res:
            print(base64.b64decode(res['LogResult']).decode('utf-8'))
            del res['LogResult']
        return res
