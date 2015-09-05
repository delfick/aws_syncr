"""
Here we define the yaml specification for aws_syncr options

The specifications are responsible for sanitation, validation and normalisation.
"""

from aws_syncr.formatter import MergedOptionStringFormatter

from input_algorithms.spec_base import defaulted, boolean, string_spec, formatted, create_spec, directory_spec
from input_algorithms.dictobj import dictobj

import six

class AwsSyncr(dictobj):
    fields = {
          "debug": "Set debug capability"
        , "extra": "Sets the ``$@`` variable. Alternatively specify these after a ``--`` on the commandline"
        , "environment": "The environment to sync"
        , "config_folder": "The folder where the configuration can be found"
        }

class AwsSyncrSpec(object):
    """Knows about aws_syncr specific configuration"""

    @property
    def aws_syncr_spec(self):
        formatted_string = formatted(string_spec(), MergedOptionStringFormatter, expected_type=six.string_types)

        """Spec for aws_syncr options"""
        return create_spec(AwsSyncr
            , extra = defaulted(formatted_string, "")
            , debug = defaulted(boolean(), False)
            , environment = formatted_string
            , config_folder = directory_spec()
            )

