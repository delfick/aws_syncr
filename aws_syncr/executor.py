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
    cli_description = "Application that reads YAML and syncs definitions with amazon"
    cli_environment_defaults = {"AWS_SYNCR_CONFIG_FOLDER": ("--config-folder", '.')}
    cli_positional_replacements = [('--environment'), ('--task', 'list_tasks'), ('--artifact', "")]

    def execute(self, args, extra_args, cli_args, logging_handler, no_docker=False):
        cli_args["aws_syncr"]["extra"] = extra_args
        cli_args["aws_syncr"]["debug"] = args.debug

        collector = Collector()
        collector.prepare(cli_args["aws_syncr"]["config_folder"], cli_args, cli_args['aws_syncr']['environment'])
        if hasattr(collector, "configuration") and "term_colors" in collector.configuration:
            self.setup_logging_theme(logging_handler, colors=collector.configuration["term_colors"])

        task = args.aws_syncr_chosen_task
        if task not in available_actions:
            raise BadTask("Unknown task", available=list(available_actions.keys()), wanted=task)

        available_actions[task](collector)

    def setup_other_logging(self, args, verbose=False, silent=False, debug=False):
        logging.getLogger("boto3").setLevel([logging.CRITICAL, logging.DEBUG][verbose or debug])
        logging.getLogger("requests").setLevel([logging.CRITICAL, logging.ERROR][verbose or debug])
        logging.getLogger("botocore").setLevel([logging.CRITICAL, logging.DEBUG][verbose or debug])

    def specify_other_args(self, parser, defaults):
        parser.add_argument("--config-folder"
            , help = "The config folder containing the environments aws_syncr should care about"
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
            , help = "Environment to read options from"
            , dest = "aws_syncr_environment"
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
