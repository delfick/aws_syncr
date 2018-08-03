# coding: spec

from aws_syncr.option_spec.aws_syncr_specs import AwsSyncrSpec
from aws_syncr.errors import BadOption

from input_algorithms.meta import Meta
from tests.helpers import TestCase

describe TestCase, "Aws_syncr":
    it "complains about invalid account ids":
        accounts = {"prod": 123}
        with self.fuzzyAssertRaisesError(BadOption, "Account id must match a particular regex", got='123', should_match="\\d{12}"):
            AwsSyncrSpec().accounts_spec.normalise(Meta({}, []), accounts)

        accounts = {"prod": "123"}
        with self.fuzzyAssertRaisesError(BadOption, "Account id must match a particular regex", got='123', should_match="\\d{12}"):
            AwsSyncrSpec().accounts_spec.normalise(Meta({}, []), accounts)

        accounts = {"prod": "123456789012"}
        self.assertEqual(AwsSyncrSpec().accounts_spec.normalise(Meta({}, []), accounts), accounts)

    it "Allows valid account ids":
        accounts = {"prod": "123456789012"}
        self.assertEqual(AwsSyncrSpec().accounts_spec.normalise(Meta({}, []), accounts), accounts)

    it "allows a dictionary of string to dictionary for templates":
        templates = {"one": {"a": { 1: 2}}, "two": {"b":3, "c": 5}}
        self.assertEqual(AwsSyncrSpec().templates_spec.normalise(Meta({}, []), templates), templates)

    it "normalises aws_syncr object":
        with self.a_directory() as config_folder:
            aws_syncr = {"config_folder": config_folder, "location": "{loc}", "environment": "{env}"}
            everything = {"loc": "the_location", "env": "totes"}
            expected = {"artifact": "", "stage": "", "debug": False, "extra": "", "dry_run": False, "location": "the_location", "environment": "totes", "config_folder": config_folder}
            self.assertEqual(AwsSyncrSpec().aws_syncr_spec.normalise(Meta(everything, []), aws_syncr), expected)
