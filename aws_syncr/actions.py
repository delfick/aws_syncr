from aws_syncr.errors import AwsSyncrError

import logging

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

