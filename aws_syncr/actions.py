from aws_syncr.filename_completer import filename_prompt, setup_completer
from aws_syncr.formatter import MergedOptionStringFormatter
from aws_syncr.errors import AwsSyncrError
from aws_syncr.errors import UserQuit

from Crypto.Util import Counter
from Crypto.Cipher import AES

from option_merge import MergedOptions
from six.moves import input
import readline
import logging
import base64
import yaml
import six
import os

log = logging.getLogger("aws_syncr.actions")

available_actions = {}

def an_action(func):
    available_actions[func.__name__] = func
    return func

def find_lambda_function(aws_syncr, configuration):
    lambda_function = aws_syncr.artifact

    if 'lambda' not in configuration:
        raise AwsSyncrError("Please define lambda functions under the 'lambda' section of your configuration")

    if not lambda_function:
        raise AwsSyncrError("Please specify --artifact for the lambda function to deploy")

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
        raise AwsSyncrError("Please specify --artifact for the gateway function to deploy")

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

    for domain in domain_names:
        if 'name' in domain:
            domain_name = MergedOptionStringFormatter(configuration, '.'.join(location + ['name']), value=domain.get('name')).format()
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
    amazon = collector.configuration['amazon']
    amazon._validated = True
    aws_syncr = collector.configuration['aws_syncr']
    find_lambda_function(aws_syncr, collector.configuration).test(aws_syncr, amazon)

@an_action
def deploy_and_test_lambda(collector):
    deploy_lambda(collector)
    test_lambda(collector)

@an_action
def deploy_gateway(collector):
    configuration = collector.configuration
    aws_syncr = configuration['aws_syncr']
    aws_syncr, amazon, stage, gateway = find_gateway(aws_syncr, configuration)
    gateway.deploy(aws_syncr, amazon, stage)

    if not configuration['amazon'].changes:
        log.info("No changes were made!!")

@an_action
def sync_and_deploy_gateway(collector):
    configuration = collector.configuration
    aws_syncr = configuration['aws_syncr']
    find_gateway(aws_syncr, configuration)

    artifact = aws_syncr.artifact
    aws_syncr.artifact = ""
    sync(collector)

    aws_syncr.artifact = artifact
    deploy_gateway(collector)

@an_action
def encrypt_certificate(collector):
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

