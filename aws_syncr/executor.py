#!/usr/bin/env python
"""
This is where the mainline sits and is responsible for setting up the logging,
the argument parsing and for starting up aws_syncr.
"""

from aws_syncr.actions import available_actions
from aws_syncr.collector import Collector
from aws_syncr.errors import BadTask

from delfick_app import App
import logging

log = logging.getLogger("aws_syncr.executor")

class App(App):
    cli_categories = ['aws_syncr']
    cli_description = "Application that reads YAML and syncs definitions with amazon. Run without arguments to see what tasks are available. See http://aws-syncr.readthedocs.org/en/latest/ for more details"
    cli_environment_defaults = {"AWS_SYNCR_CONFIG_FOLDER": ("--config-folder", '.')}
    cli_positional_replacements = [('--environment'), ('--task', 'list_tasks'), ('--artifact', "")]
    issue_tracker_link = "https://github.com/delfick/aws_syncr/issues"

    def execute(self, args_obj, args_dict, extra_args, logging_handler, no_docker=False):
        args_dict["aws_syncr"]["extra"] = extra_args
        args_dict["aws_syncr"]["debug"] = args_obj.debug

        collector = Collector()
        collector.prepare(args_dict["aws_syncr"]["config_folder"], args_dict, args_dict['aws_syncr']['environment'])
        if hasattr(collector, "configuration") and "term_colors" in collector.configuration:
            self.setup_logging_theme(logging_handler, colors=collector.configuration["term_colors"])

        task = args_obj.aws_syncr_chosen_task
        if task not in available_actions:
            raise BadTask("Unknown task", available=list(available_actions.keys()), wanted=task)

        available_actions[task](collector)

    def setup_other_logging(self, args_obj, verbose=False, silent=False, debug=False):
        logging.getLogger("boto3").setLevel([logging.CRITICAL, logging.DEBUG][verbose or debug])
        logging.getLogger("requests").setLevel([logging.CRITICAL, logging.ERROR][verbose or debug])
        logging.getLogger("botocore").setLevel([logging.CRITICAL, logging.DEBUG][verbose or debug])

    def specify_other_args(self, parser, defaults):
        parser.add_argument("--config-folder"
            , help = "The config folder containing accounts.yaml and each environment as a folder containing yaml files."
            , dest = "aws_syncr_config_folder"
            , **defaults["--config-folder"]
            )

        parser.add_argument("--dry-run"
            , help = "Should aws_syncr take any real action or print out what is intends to do"
            , dest = "aws_syncr_dry_run"
            , action = "store_true"
            )

        parser.add_argument("--task"
            , help = "The task to run"
            , dest = "aws_syncr_chosen_task"
            , **defaults["--task"]
            )

        parser.add_argument("--environment"
            , help = "Environment to read options from (i.e. the name of the folder as found in the --config-folder directory)"
            , dest = "aws_syncr_environment"
            , required = "default" not in defaults['--environment']
            , **defaults['--environment']
            )

        parser.add_argument("--artifact"
            , help = "Extra argument to be used as decided by each task"
            , dest = "aws_syncr_artifact"
            , **defaults['--artifact']
            )

        parser.add_argument("--stage"
            , help = "Extra argument to be used as the stage for deploying an api gateway"
            , dest = "aws_syncr_stage"
            , default = ""
            )

        return parser

main = App.main
if __name__ == '__main__':
    main()
