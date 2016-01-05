from aws_syncr.errors import BadAmazon, BadCredentials

from botocore.exceptions import ClientError, NoCredentialsError

from contextlib import contextmanager

class AmazonMixin:
    @contextmanager
    def catch_boto_400(self, message, heading=None, document=None, **info):
        """Turn a BotoServerError 400 into a BadAmazon"""
        try:
            yield
        except ClientError as error:
            if str(error.response["ResponseMetadata"]["HTTPStatusCode"]).startswith("4"):
                if heading or document:
                    print("=" * 80)
                    if heading:
                        print(heading)
                    print(document)
                    print("=" * 80)
                error_message = error.response["Error"]["Message"]
                raise BadAmazon(message, error_message=error_message, error_code=error.response["ResponseMetadata"]["HTTPStatusCode"], **info)
            else:
                raise

    @contextmanager
    def ignore_missing(self):
        try:
            yield
        except ClientError as error:
            if "ResponseMetadata" in error.response and error.response["ResponseMetadata"]["HTTPStatusCode"] == 404 or error.response["Error"]["Code"] == "404" or error.response["Error"]["Code"] == "NotFoundException":
                pass
            else:
                raise

    @contextmanager
    def catch_invalid_credentials(self):
        try:
            yield
        except NoCredentialsError:
            raise BadCredentials("Failed to find valid credentials")
        except ClientError as error:
            if error.response["ResponseMetadata"]["HTTPStatusCode"] == 403:
                raise BadCredentials("Failed to find valid credentials", error=error.message)
            else:
                raise

    def print_change(self, symbol, typ, changes=None, document=None, **kwargs):
        """Print out a change"""
        values = ", ".join("{0}={1}".format(key, val) for key, val in sorted(kwargs.items()))
        print("{0} {1}({2})".format(symbol, typ, values))
        if changes:
            for change in changes:
                print("\n".join("\t{0}".format(line) for line in change.split('\n')))
        elif document:
            print("\n".join("\t{0}".format(line) for line in document.split('\n')))

    def change(self, symbol, typ, **kwargs):
        """Print out a change and then do the change if not doing a dry run"""
        self.print_change(symbol, typ, **kwargs)
        if not self.dry_run:
            try:
                yield
            except:
                raise
            else:
                self.amazon.changes = True

