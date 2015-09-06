"""
Collects then parses configuration files and verifies that they are valid.
"""

from aws_syncr.errors import BadConfiguration, BadYaml, BadOption
from aws_syncr.option_spec.aws_syncr_specs import AwsSyncrSpec
from aws_syncr.amazon import Amazon

from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta

from option_merge.collector import Collector
from option_merge import MergedOptions
from option_merge import Converter

import tempfile
import logging
import yaml
import json
import os

log = logging.getLogger("aws_syncr.collector")

class Collector(Collector):

    BadFileErrorKls = BadYaml
    BadConfigurationErrorKls = BadConfiguration

    def alter_clone_cli_args(self, new_collector, new_cli_args, new_aws_syncr_options=None):
        new_aws_syncr = self.configuration["aws_syncr"].clone()
        if new_aws_syncr_options:
            new_aws_syncr.update(new_aws_syncr_options)
        new_cli_args["aws_syncr"] = new_aws_syncr

    def prepare(self, configuration_folder, cli_args, environment):
        """Make a temporary configuration file from the files in our folder"""
        if not os.path.isdir(configuration_folder):
            raise BadOption("Specified configuration folder is not a directory!", wanted=configuration_folder)
        available = [os.path.join(configuration_folder, name) for name in os.listdir(configuration_folder)]
        available_environments = [path for path in available if os.path.isdir(path)]
        if environment not in available_environments:
            raise BadOption("Specified environment doesn't exist", available=available_environments, wanted=environment)

        common_files = [os.path.abspath(path) for path in available if os.path.isfile(path) and path.endswith("yml") or path.endswith("yaml")]
        environment_files = []
        for root, dirs, files in os.walk(os.path.join(configuration_folder, environment)):
            environment_files.extend(os.path.join(root, filename) for filename in files)

        for filename in environment_files:
            if os.path.islink(filename):
                actual_file = os.path.abspath(os.path.join(os.path.dirname(filename), os.readlink(filename)))
                if os.path.islink(filename) and actual_file in common_files:
                    common_files = [filename for filename in common_files if filename != actual_file]

        with tempfile.NamedTemporaryFile() as fle:
            contents = json.dumps({"includes": common_files + environment_files})
            fle.write(contents.encode('utf-8'))
            fle.flush()
            cli_args['aws_syncr']['environment'] = os.path.split(environment)[-1]
            super(Collector, self).prepare(fle.name, cli_args)

    def find_missing_config(self, configuration):
        """Complain if we have no account information"""
        if "accounts" not in configuration:
            raise self.BadConfigurationErrorKls("accounts is a mandatory section and wasn't found")

    def extra_prepare(self, configuration, cli_args):
        """Called before the configuration.converters are activated"""
        aws_syncr = cli_args.pop("aws_syncr")

        self.configuration.update(
            { "$@": aws_syncr.get("extra", "")
            , "aws_syncr": aws_syncr
            , "templates": {}
            }
        , source = "<cli_args>"
        )

    def extra_prepare_after_activation(self, configuration, cli_args):
        """Setup our connection to amazon"""
        aws_syncr = configuration['aws_syncr']
        configuration["amazon"] = Amazon(configuration['aws_syncr'].environment, configuration['accounts'], debug=aws_syncr.debug, dry_run=aws_syncr.dry_run)
        configuration["amazon"].validate_account()

    def home_dir_configuration_location(self):
        return os.path.expanduser("~/.aws_syncrrc.yml")

    def start_configuration(self):
        """Create the base of the configuration"""
        return MergedOptions(dont_prefix=[dictobj])

    def read_file(self, location):
        """Read in a yaml file and return as a python object"""
        try:
            return yaml.load(open(location))
        except (yaml.parser.ParserError, yaml.scanner.ScannerError) as error:
            raise self.BadFileErrorKls("Failed to read yaml", location=location, error_type=error.__class__.__name__, error="{0}{1}".format(error.problem, error.problem_mark))

    def add_configuration(self, configuration, collect_another_source, done, result, src):
        """Used to add a file to the configuration, result here is the yaml.load of the src"""
        if "includes" in result:
            for include in result["includes"]:
                collect_another_source(include)
        configuration.update(result, source=src)

    def extra_configuration_collection(self, configuration):
        """Hook to do any extra configuration collection or converter registration"""
        aws_syncr_spec = AwsSyncrSpec()

        def aws_syncr_converter(p, v):
            log.info("Converting %s", p)
            meta = Meta(p.configuration, [("aws_syncr", "")])
            configuration.converters.started(p)
            return aws_syncr_spec.aws_syncr_spec.normalise(meta, v)
        configuration.add_converter(Converter(convert=aws_syncr_converter, convert_path=["aws_syncr"]))

        def accounts_converter(p, v):
            log.info("Converting %s", p)
            meta = Meta(p.configuration, [("accounts", "")])
            configuration.converters.started(p)
            return aws_syncr_spec.accounts_spec.normalise(meta, v)
        configuration.add_converter(Converter(convert=accounts_converter, convert_path=["accounts"]))

        def roles_converter(p, v):
            log.info("Converting %s", p)
            meta = Meta(p.configuration, [("roles", "")])
            configuration.converters.started(p)
            return aws_syncr_spec.roles_spec.normalise(meta, v)
        configuration.add_converter(Converter(convert=roles_converter, convert_path=["roles"]))

        def templates_converter(p, v):
            log.info("Converting %s", p)
            meta = Meta(p.configuration, [("templates", "")])
            configuration.converters.started(p)
            return aws_syncr_spec.templates_spec.normalise(meta, v)
        configuration.add_converter(Converter(convert=templates_converter, convert_path=["templates"]))
