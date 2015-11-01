"""
Here we define the yaml specification for aws_syncr options

The specifications are responsible for sanitation, validation and normalisation.
"""

from aws_syncr.option_spec.encryption_keys import encryption_keys_spec, EncryptionKeys
from aws_syncr.option_spec.buckets import buckets_spec, Buckets
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.roles import role_spec, Roles
from aws_syncr.errors import BadOption

from input_algorithms.spec_base import (
      defaulted, boolean, string_spec, formatted, create_spec, dictionary_spec
    , directory_spec, dictof, string_or_int_as_string_spec, container_spec
    )
from input_algorithms.validators import Validator
from input_algorithms.dictobj import dictobj

import six
import re

regexes = {
      "amazon_account_id": re.compile('\d{12}')
    }

class AwsSyncr(dictobj):
    fields = {
          "debug": "Set debug capability"
        , "dry_run": "Whether to do a dry run or not"
        , "extra": "Sets the ``$@`` variable. Alternatively specify these after a ``--`` on the commandline"
        , "stage": "Stage to deploy for an api gateway when deploy_gateway is used"
        , "location": "The location to base everything in"
        , "artifact": "Arbitrary argument"
        , "environment": "The environment to sync"
        , "config_folder": "The folder where the configuration can be found"
        }

class valid_account_id(Validator):
    def validate(self, meta, val):
        """Validate an account_id"""
        val = string_or_int_as_string_spec().normalise(meta, val)
        if not regexes['amazon_account_id'].match(val):
            raise BadOption("Account id must match a particular regex", got=val, should_match=regexes['amazon_account_id'].pattern)
        return val

class AwsSyncrSpec(object):
    """Knows about aws_syncr specific configuration"""

    @property
    def aws_syncr_spec(self):
        """Spec for aws_syncr options"""
        formatted_string = formatted(string_spec(), MergedOptionStringFormatter, expected_type=six.string_types)
        return create_spec(AwsSyncr
            , extra = defaulted(formatted_string, "")
            , stage = defaulted(formatted_string, "")
            , debug = defaulted(boolean(), False)
            , dry_run = defaulted(boolean(), False)
            , location = defaulted(formatted_string, "ap-southeast-2")
            , artifact = formatted_string
            , environment = formatted_string
            , config_folder = directory_spec()
            )

    @property
    def accounts_spec(self):
        """Spec for accounts options"""
        formatted_account_id = formatted(valid_account_id(), MergedOptionStringFormatter, expected_type=six.string_types)
        return dictof(string_spec(), formatted_account_id)

    @property
    def templates_spec(self):
        """Spec for templates"""
        return dictof(string_spec(), dictionary_spec())

