"""
Collects then parses configuration files and verifies that they are valid.
"""

from aws_syncr.errors import BadConfiguration, BadYaml, BadOption, BadImport
from aws_syncr.option_spec.aws_syncr_specs import AwsSyncrSpec
from aws_syncr.amazon import Amazon

from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta

from option_merge.collector import Collector
from option_merge import MergedOptions
from option_merge import Converter

import pkg_resources
import tempfile
import logging
import yaml
import json
import imp
import os

log = logging.getLogger("aws_syncr.collector")

class Collector(Collector):

    BadFileErrorKls = BadYaml
    BadConfigurationErrorKls = BadConfiguration

    def alter_clone_args_dict(self, new_collector, new_args_dict, new_aws_syncr_options=None):
        new_aws_syncr = self.configuration["aws_syncr"].clone()
        if new_aws_syncr_options:
            new_aws_syncr.update(new_aws_syncr_options)
        new_args_dict["aws_syncr"] = new_aws_syncr

    def prepare(self, configuration_folder, args_dict, environment):
        """Make a temporary configuration file from the files in our folder"""
        self.configuration_folder = configuration_folder
        if not os.path.isdir(configuration_folder):
            raise BadOption("Specified configuration folder is not a directory!", wanted=configuration_folder)
        available = [os.path.join(configuration_folder, name) for name in os.listdir(configuration_folder)]
        available_environments = [os.path.basename(path) for path in available if os.path.isdir(path)]
        available_environments = [e for e in available_environments if not e.startswith('.')]

        # Make sure the environment exists
        if environment and environment not in available_environments:
            raise BadOption("Specified environment doesn't exist", available=available_environments, wanted=environment)

        if environment:
            environment_files = [os.path.join(configuration_folder, "accounts.yaml")]
            for root, dirs, files in os.walk(os.path.join(configuration_folder, environment)):
                environment_files.extend(os.path.join(root, filename) for filename in files)

            with tempfile.NamedTemporaryFile() as fle:
                contents = json.dumps({"includes": environment_files})
                fle.write(contents.encode('utf-8'))
                fle.flush()
                args_dict['aws_syncr']['environment'] = os.path.split(environment)[-1]
                super(Collector, self).prepare(fle.name, args_dict)

    def find_missing_config(self, configuration):
        """Complain if we have no account information"""
        if "accounts" not in configuration:
            raise self.BadConfigurationErrorKls("accounts is a mandatory section and wasn't found")

    def extra_prepare(self, configuration, args_dict):
        """Called before the configuration.converters are activated"""
        aws_syncr = args_dict.pop("aws_syncr")

        self.configuration.update(
            { "$@": aws_syncr.get("extra", "")
            , "aws_syncr": aws_syncr
            , "templates": {}
            , "config_folder": self.configuration_folder
            }
        , source = "<args_dict>"
        )

    def extra_prepare_after_activation(self, configuration, args_dict):
        """Setup our connection to amazon"""
        aws_syncr = configuration['aws_syncr']
        configuration["amazon"] = Amazon(configuration['aws_syncr'].environment, configuration['accounts'], debug=aws_syncr.debug, dry_run=aws_syncr.dry_run)

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
        registered = {}
        directory = pkg_resources.resource_filename("aws_syncr", "option_spec")

        for location in sorted(os.listdir(directory)):
            import_name = os.path.splitext(location)[0]
            if import_name != '__pycache__':
                try:
                    args = imp.find_module(import_name, [directory])
                except ImportError as error:
                    raise BadImport(directory=directory, importing=import_name, error=error)

                try:
                    module = imp.load_module(import_name, *args)
                except SyntaxError as error:
                    raise BadImport(directory=self.directory, importing=self.import_name, error=error)

                if hasattr(module, "__register__"):
                    registered.update(module.__register__())

        configuration['__registered__'] = [name for _, name in sorted(registered.keys())]
        by_name = dict((r[1], registered[r]) for r in registered)
        for thing in ['aws_syncr', 'accounts', 'templates'] + list(by_name.keys()):
            def make_converter(thing):
                def converter(p, v):
                    log.info("Converting %s", p)
                    meta = Meta(p.configuration, [(thing, "")])
                    configuration.converters.started(p)
                    if thing in by_name:
                        return by_name[thing].normalise(meta, v)
                    else:
                        return getattr(aws_syncr_spec, "{0}_spec".format(thing)).normalise(meta, v)
                return converter
            configuration.add_converter(Converter(convert=make_converter(thing), convert_path=[thing]))

