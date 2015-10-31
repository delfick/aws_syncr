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
    for typ, thing in converted.items():
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
