from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.option_spec.resources import resource_spec
from aws_syncr.errors import BadTemplate

from input_algorithms.spec_base import NotSpecified
from input_algorithms.errors import BadSpecValue
from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
from input_algorithms.spec_base import Spec
from option_merge import MergedOptions
from contextlib import contextmanager
from textwrap import dedent
import tempfile
import logging
import fnmatch
import zipfile
import json
import six
import re
import os

log = logging.getLogger("aws_syncr.option_spec.lambdas")

class formatted_dictionary(sb.Spec):
    def normalise(self, meta, val):
        val = sb.dictionary_spec().normalise(meta, val)
        return self.formatted_dict(meta, val)

    def formatted_dict(self, meta, val, chain=None):
        result = {}
        for key, val in val.items():
            if type(val) is dict:
                result[key] = self.formatted_dict(meta.at(key), val, chain)
            elif isinstance(val, six.string_types):
                result[key] = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter).normalise(meta.at(key), val)
            else:
                result[key] = val
        return result

class only_one_spec(sb.Spec):
    def setup(self, spec):
        self.spec = spec

    def normalise(self, meta, val):
        val = self.spec.normalise(meta, val)
        if type(val) is not list:
            return val

        if len(val) != 1:
            raise BadSpecValue("Please only specify one value", meta=meta)

        return val[0]

class divisible_by_spec(sb.Spec):
    def setup(self, divider):
        self.divider = divider

    def normalise_filled(self, meta, val):
        val = sb.integer_spec().normalise(meta, val)
        if val % self.divider != 0:
            raise BadSpecValue("Value should be divisible by {0}".format(self.divider), meta=meta)
        return val

class function_handler_spec(sb.Spec):
    def normalise_empty(self, meta):
        path = [p for p, _ in meta._path]
        path.pop()
        runtime = meta.everything['.'.join(path)].get("runtime", "python")
        runtime = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter).normalise(meta.at("runtime"), runtime)

        if runtime == 'java8':
            raise BadSpecValue("No default function handler for java", meta=meta)
        elif runtime == 'nodejs':
            return "index.handler"
        elif runtime == 'python2.7':
            return "lambda_function.lambda_handler"
        else:
            raise BadSpecValue("No default function handler for {0}".format(runtime), meta=meta)

    def normalise_filled(self, meta, val):
        return sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter).normalise(meta, val)

class function_code_spec(sb.Spec):
    def normalise_filled(self, meta, val):
        val = sb.dictof(sb.string_choice_spec(["s3", "inline", "directory"]), sb.any_spec()).normalise(meta, val)
        if not val:
            raise BadSpecValue("Please specify s3, inline or directory for your code", meta=meta)

        if len(val) > 1:
            raise BadSpecValue("Please only specify one of s3, inline or directory for your code", got=list(val.keys()), meta=meta)

        formatted_string = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
        if "s3" in val:
            return sb.create_spec(S3Code
                , key = formatted_string
                , bucket = formatted_string
                , version = sb.defaulted(sb.string_spec(), NotSpecified)
                ).normalise(meta, val['s3'])
        elif "inline" in val:
            path = [p for p, _ in meta._path]
            path.pop()
            runtime = meta.everything['.'.join(path)].get("runtime", "python")
            runtime = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter).normalise(meta.at("runtime"), runtime)

            return sb.create_spec(InlineCode
                , code = sb.string_spec()
                , runtime = sb.overridden(runtime)
                ).normalise(meta, {"code": val['inline']})
        else:
            directory = val['directory']
            if isinstance(val['directory'], six.string_types):
                directory = {"directory": val['directory']}

            if 'directory' in directory:
                formatted_string = sb.formatted(sb.string_spec(), formatter=MergedOptionStringFormatter)
                directory['directory'] = formatted_string.normalise(meta.at("directory").at("directory"), directory['directory'])

            return sb.create_spec(DirectoryCode
                , directory = sb.directory_spec()
                , exclude = sb.listof(sb.string_spec())
                ).normalise(meta, directory)

class lambdas_spec(Spec):
    def normalise(self, meta, val):
        if 'use' in val:
            template = val['use']
            if template not in meta.everything['templates']:
                available = list(meta.everything['templates'].keys())
                raise BadTemplate("Template doesn't exist!", wanted=template, available=available, meta=meta)

            val = MergedOptions.using(meta.everything['templates'][template], val)

        formatted_string = sb.formatted(sb.string_or_int_as_string_spec(), MergedOptionStringFormatter, expected_type=six.string_types)
        function_name = meta.key_names()['_key_name_0']

        val = sb.create_spec(Lambda
            , name = sb.overridden(function_name)
            , role = sb.required(only_one_spec(resource_spec("lambda", function_name, only=["iam"])))
            , code = sb.required(function_code_spec())
            , handler = function_handler_spec()
            , timeout = sb.integer_spec()
            , runtime = sb.required(formatted_string)
            , location = sb.required(formatted_string)
            , description = formatted_string
            , sample_event = sb.defaulted(sb.or_spec(formatted_dictionary(), sb.string_spec()), "")
            , desired_output_for_test = sb.defaulted(sb.or_spec(formatted_dictionary(), sb.string_spec()), "")
            , memory_size = sb.defaulted(divisible_by_spec(64), 128)
            ).normalise(meta, val)

        # Hack to make sample_event and desired_output_for_test not appear as a MergedOptions
        for key in ('sample_event', 'desired_output_for_test'):
            if isinstance(val[key], MergedOptions):
                v = val[key].as_dict()
                class Arbritrary(dictobj):
                    fields = list(v.keys())
                val[key] = Arbritrary(**v)
        return val

class Lambdas(dictobj):
    fields = ['items']

    def sync_one(self, aws_syncr, amazon, function):
        """Make sure this function exists and has only attributes we want it to have"""
        function_info = amazon.lambdas.function_info(function.name, function.location)
        if not function_info:
            amazon.lambdas.create_function(function.name, function.description, function.location, function.runtime, function.role, function.handler, function.timeout, function.memory_size, function.code)
        else:
            amazon.lambdas.modify_function(function_info, function.name, function.description, function.location, function.runtime, function.role, function.handler, function.timeout, function.memory_size, function.code)

class Lambda(dictobj):
    fields = {
          'name': "Alias of the function"
        , 'role': "The role assumed by the function"
        , 'code': "Code for the function!"
        , 'handler': "Function within your code that gets executed"
        , 'timeout': "Max function execution time"
        , 'runtime': "Runtime environment for the function"
        , 'location': "The region the function exists in"
        , 'description': "Description of the function"
        , 'sample_event': "A sample event to test with"
        , 'desired_output_for_test': "Keys and values for the output of the test to consider it successful"
        , 'memory_size': "Max memory size for the function"
        }

    def deploy(self, aws_syncr, amazon):
        print(json.dumps(amazon.lambdas.deploy_function(self.name, self.code, self.location), indent=4))

    def test(self, aws_syncr, amazon):
        output = amazon.lambdas.test_function(self.name, self.sample_event, self.location)
        print(json.dumps(output, indent=4))

        if self.desired_output_for_test and self.desired_output_for_test is not NotSpecified:
            content = output['Payload']
            if isinstance(self.desired_output_for_test, six.string_types):
                if not re.match(self.desired_output_for_test, content):
                    print("content '{0}' does not match pattern '{1}'".format(content, self.desired_output_for_test))
                    return False

            else:
                if any(key not in content or content[key] != val for key, val in self.desired_output_for_test.items()):
                    print("Not all of the values match our desired output of '{0}'".format(self.desired_output_for_test))
                    return False

        return True

class S3Code(dictobj):
    fields = ["key", "bucket", "version"]

    @property
    def s3_address(self):
        return "s3://{0}/{1}".format(self.bucket, self.key)

    @contextmanager
    def zipfile(self):
        yield

class InlineCode(dictobj):
    fields = ["code", "runtime"]
    s3_address = None

    @property
    def arcname(self):
        if self.runtime == "python2.7":
            return "./lambda_function.py"
        elif self.runtime == "java8":
            return "./main.java"
        else:
            return "./index.js"

    @contextmanager
    def code_in_file(self):
        with tempfile.NamedTemporaryFile() as fle:
            fle.write(dedent(self.code).encode('utf-8'))
            fle.flush()
            yield fle.name

    @contextmanager
    def zipfile(self):
        with tempfile.NamedTemporaryFile(suffix=".zip") as fle:
            with self.code_in_file() as filename:
                log.info("Making zipfile")
                with zipfile.ZipFile(fle.name, "w") as zf:
                    zf.write(filename, self.arcname)
            yield fle.name

class DirectoryCode(dictobj):
    fields = ["directory", "exclude"]
    s3_address = None

    def files(self):
        for root, dirs, files in os.walk(self.directory, followlinks=True):
            for fle in files:
                location = os.path.join(root, fle)
                if not any(fnmatch.fnmatch(location, os.path.join(self.directory, ex)) for ex in self.exclude):
                    yield location, os.path.relpath(location, self.directory)

    @contextmanager
    def zipfile(self):
        with tempfile.NamedTemporaryFile(suffix=".zip") as fle:
            log.info("Making zipfile")
            with zipfile.ZipFile(fle.name, "w") as zf:
                for filename, arcname in self.files():
                    zf.write(filename, arcname)
            yield fle.name

def __register__():
    return {(22, "lambda"): sb.container_spec(Lambdas, sb.dictof(sb.string_spec(), lambdas_spec()))}

