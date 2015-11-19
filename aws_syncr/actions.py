from aws_syncr.filename_completer import filename_prompt, setup_completer
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.errors import AwsSyncrError
from aws_syncr.errors import UserQuit

from Crypto.Util import Counter
from Crypto.Cipher import AES

from option_merge import MergedOptions
from six.moves import input
from textwrap import dedent
import itertools
import readline
import logging
import base64
import shlex
import yaml
import sys
import six
import os

log = logging.getLogger("aws_syncr.actions")

available_actions = {}

def an_action(func):
    available_actions[func.__name__] = func
    func.label = "Default"
    return func

def find_lambda_function(aws_syncr, configuration):
    lambda_function = aws_syncr.artifact

    if 'lambda' not in configuration:
        raise AwsSyncrError("Please define lambda functions under the 'lambda' section of your configuration")

    if not lambda_function:
        available = list(configuration['lambda'].items.keys())
        raise AwsSyncrError("Please specify --artifact for the lambda function to deploy", available=available)

    wanted = ['lambda', lambda_function]
    if wanted not in configuration:
        raise AwsSyncrError("Couldn't find specified lambda function", available=list(configuration["lambda"].items.keys()))

    return configuration['lambda'].items[lambda_function]

def find_gateway(aws_syncr, configuration):
    amazon = configuration['amazon']

    stage = aws_syncr.stage
    gateway = aws_syncr.artifact

    if 'apigateway' not in configuration:
        raise AwsSyncrError("Please define apigateway in your configuration before trying to deploy a gateway")

    if not gateway:
        available = list(configuration['apigateway'].items.keys())
        raise AwsSyncrError("Please specify --artifact for the gateway function to deploy", available=available)

    wanted = ['apigateway', gateway]
    if wanted not in configuration:
        raise AwsSyncrError("Couldn't find specified api gateway", available=list(configuration["apigateway"].items.keys()))
    gateway = configuration['apigateway'].items[gateway]

    if not stage:
        raise AwsSyncrError("Please specify --stage", available=list(gateway.stage_names))

    return aws_syncr, amazon, stage, gateway

def find_certificate_source(configuration, gateway, certificate):
    source = configuration.source_for(['apigateway', gateway, 'domain_names'])
    location = ["apigateway", gateway, 'domain_names']
    domain_names = configuration.get(location, ignore_converters=True)

    for name, domain in domain_names.items():
        if 'zone' in domain:
            zone = MergedOptionStringFormatter(configuration, '.'.join(location + ['zone']), value=domain.get('zone')).format()
            domain_name = "{0}.{1}".format(name, zone)
            if domain_name == certificate:
                if 'certificate' not in domain:
                    domain['certificate'] = {}

                var = domain['certificate']

                class StickyChain(object):
                    def __init__(self):
                        self.lst = []

                    def __add__(self, other):
                        self.lst.extend(other)
                        return self.lst

                    def __contains__(self, item):
                        return item in self.lst

                    def __getitem__(self, index):
                        return self.lst[index]
                chain = StickyChain()

                if isinstance(var, six.string_types):
                    result = MergedOptionStringFormatter(configuration, '.'.join(location), value=var, chain=chain).format()
                    if not isinstance(result, dict) and not isinstance(result, MergedOptions) and (not hasattr(result, 'is_dict') or not result.is_dict):
                        raise AwsSyncrError("certificate should be pointing at a dictionary", got=result, chain=['.'.join(location)] + chain)

                    location = chain[-1]
                    source = configuration.source_for(location)
                    for info in configuration.storage.get_info(location, ignore_converters=True):
                        location = [str(part) for part in info.path.path]

    return location, source

@an_action
def list_tasks(collector):
    """List the available_tasks"""
    print("Usage: aws_syncr <environment> <task>")
    print("")
    print("Available environments to choose from are")
    print("-----------------------------------------")
    print("")
    for environment in os.listdir(collector.configuration_folder):
        location = os.path.join(collector.configuration_folder, environment)
        if os.path.isdir(location) and not environment.startswith("."):
            print("\t{0}".format(environment))

    print("")
    print("Available tasks to choose from are:")
    print("-----------------------------------")
    print("")
    keygetter = lambda item: item[1].label
    tasks = sorted(available_actions.items(), key=keygetter)
    sorted_tasks = sorted(list(tasks), key=lambda item: len(item[0]))
    max_length = max(len(name) for name, _ in sorted_tasks)
    for key, task in sorted_tasks:
        desc = dedent(task.__doc__ or "").strip().split('\n')[0]
        print("\t{0}{1} :-: {2}".format(" " * (max_length-len(key)), key, desc))
    print("")

@an_action
def sync(collector):
    """Sync an environment"""
    amazon = collector.configuration['amazon']
    aws_syncr = collector.configuration['aws_syncr']

    # Convert everything before we try and sync anything
    log.info("Converting configuration")
    converted = {}
    for thing in collector.configuration["__registered__"]:
        if thing in collector.configuration:
            converted[thing] = collector.configuration[thing]

    # Do the sync
    for typ in collector.configuration["__registered__"]:
        if typ in converted:
            thing = converted[typ]
            if not aws_syncr.artifact or aws_syncr.artifact == typ:
                log.info("Syncing {0}".format(typ))
                for name, item in thing.items.items():
                    thing.sync_one(aws_syncr, amazon, item)

    if not amazon.changes:
        log.info("No changes were made!!")

@an_action
def deploy_lambda(collector):
    """Deploy a lambda function"""
    amazon = collector.configuration['amazon']
    aws_syncr = collector.configuration['aws_syncr']
    find_lambda_function(aws_syncr, collector.configuration).deploy(aws_syncr, amazon)

@an_action
def test_lambda(collector):
    """Invoke a lambda function with the defined sample_event and compare against desired_output_for_test"""
    amazon = collector.configuration['amazon']
    amazon._validated = True
    aws_syncr = collector.configuration['aws_syncr']
    if not find_lambda_function(aws_syncr, collector.configuration).test(aws_syncr, amazon):
        raise AwsSyncrError("Failed to test the lambda")

@an_action
def deploy_and_test_lambda(collector):
    """Do a deploy of a lambda function followed by invoking it"""
    deploy_lambda(collector)
    test_lambda(collector)

@an_action
def deploy_gateway(collector):
    """Deploy the apigateway to a particular stage"""
    configuration = collector.configuration
    aws_syncr = configuration['aws_syncr']
    aws_syncr, amazon, stage, gateway = find_gateway(aws_syncr, configuration)
    gateway.deploy(aws_syncr, amazon, stage)

    if not configuration['amazon'].changes:
        log.info("No changes were made!!")

@an_action
def sync_and_deploy_gateway(collector):
    """Do a sync followed by deploying the gateway"""
    configuration = collector.configuration
    aws_syncr = configuration['aws_syncr']
    find_gateway(aws_syncr, configuration)

    artifact = aws_syncr.artifact
    aws_syncr.artifact = ""
    sync(collector)

    aws_syncr.artifact = artifact
    deploy_gateway(collector)

@an_action
def test_gateway(collector):
    """Specify <method> <endpoint> after -- from the commandline and that gateway endpoint will be requested"""
    collector.configuration['amazon']._validated = True
    configuration = collector.configuration
    aws_syncr = configuration['aws_syncr']
    aws_syncr, amazon, stage, gateway = find_gateway(aws_syncr, configuration)
    if not gateway.test(aws_syncr, amazon, stage):
        raise AwsSyncrError("Failed to test the gateway")

@an_action
def test_all_gateway_endpoints(collector):
    """Do a test on all the available gateway endpoints"""
    collector.configuration['amazon']._validated = True
    configuration = collector.configuration
    aws_syncr = configuration['aws_syncr']
    aws_syncr, amazon, stage, gateway = find_gateway(aws_syncr, configuration)

    failure = False
    for method, resource in gateway.available_methods_and_endpoints():
        combination = "{0} {1}".format(method, resource)
        print(combination)
        print("=" * len(combination))
        aws_syncr.extra = combination
        if not gateway.test(aws_syncr, amazon, stage):
            failure = True
        print("")

    if failure:
        raise AwsSyncrError("Atleast one of the endpoints failed the test")

@an_action
def encrypt_certificate(collector):
    """Write encrypted values for your certificate to the configuration"""
    configuration = collector.configuration
    amazon = configuration['amazon']
    aws_syncr = configuration['aws_syncr']
    certificate = aws_syncr.artifact

    available = []

    for gateway_name, gateway in configuration.get('apigateway', {}, ignore_converters=True).items():
        for name, options in gateway.get("domain_names", {}).items():
            if "zone" in options:
                location = '.'.join(['apigateway', gateway_name, 'domain_names'])
                formatter = MergedOptionStringFormatter(configuration, location, value=options['zone'])
                available.append((gateway_name, "{0}.{1}".format(name, formatter.format())))

    if not available:
        raise AwsSyncrError("Please specify apigateway.<gateway_name>.domain_names.<domain_name>.name in the configuration")

    if not certificate:
        raise AwsSyncrError("Please specify certificate to encrypt with --artifact", available=[a[1] for a in available])

    if certificate not in [a[1] for a in available]:
        raise AwsSyncrError("Unknown certificate", available=[a[1] for a in available], got=certificate)

    gateway = [name for name, cert in available if cert == certificate][0]
    location, source = find_certificate_source(configuration, gateway, certificate)

    log.info("Gonna edit {0} in {1}".format(location, source))
    current = MergedOptions.using(yaml.load(open(source)))
    dest = current[location]

    try:
        key_id = input("Which kms key do you want to use? ")
        region = input("What region is this key in? ")
    except EOFError:
        raise UserQuit()

    # Make the filename completion work
    setup_completer()

    # Create the datakey to encrypt with
    data_key = amazon.kms.generate_data_key(region, key_id)
    plaintext_data_key = data_key["Plaintext"]
    encrypted_data_key = base64.b64encode(data_key["CiphertextBlob"]).decode('utf-8')

    # Encrypt our secrets
    secrets = {}
    for name, desc in (("body", "certificate's crt file"), ("key", "private key file"), ("chain", "certificate chain")):
        location = None
        while not location or not os.path.isfile(location):
            location = os.path.expanduser(filename_prompt("Where is the {0}? ".format(desc)))
            if not location or not os.path.isfile(location):
                print("Please give a location to a file that exists!")

        data = open(location).read()
        counter = Counter.new(128)
        encryptor = AES.new(plaintext_data_key[:32], AES.MODE_CTR, counter=counter)
        secrets[name] = base64.b64encode(encryptor.encrypt(data)).decode('utf-8')

    # Add in the encrypted values
    dest['body'] = {"kms": secrets['body'], "location": region, "kms_data_key": encrypted_data_key}
    dest['key'] = {"kms": secrets['key'], "location": region, "kms_data_key": encrypted_data_key}
    dest['chain'] = {"kms": secrets['chain'], "location": region, "kms_data_key": encrypted_data_key}

    # And write to the file!
    yaml.dump(current.as_dict(), open(source, 'w'), explicit_start=True, indent=2, default_flow_style=False)

@an_action
def execute_as(collector):
    """Execute a command (after the --) as an assumed role (specified by --artifact)"""
    # Gonna assume role anyway...
    collector.configuration['amazon']._validated = True

    # Find the arn we want to assume
    account_id = collector.configuration['accounts'][collector.configuration['aws_syncr'].environment]
    arn = "arn:aws:iam::{0}:role/{1}".format(account_id, collector.configuration['aws_syncr'].artifact)

    # Determine the command to run
    parts = shlex.split(collector.configuration["aws_syncr"].extra)
    if not parts:
        suggestion = " ".join(sys.argv) + " -- /path/to/command_to_run"
        msg = "No command was provided. Try something like:\n\t\t{0}".format(suggestion)
        raise AwsSyncrError(msg)

    # Get our aws credentials environment variables from the assumed role
    env = dict(os.environ)
    env.update(collector.configuration['amazon'].iam.assume_role_credentials(arn))

    # Turn into the command we want to execute
    os.execvpe(parts[0], parts, env)

