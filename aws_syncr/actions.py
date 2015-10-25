from aws_syncr.errors import AwsSyncrError

import logging

log = logging.getLogger("aws_syncr.actions")

available_actions = {}

def an_action(func):
    available_actions[func.__name__] = func
    return func

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
    lambda_function = aws_syncr.artifact

    if 'lambda' not in collector.configuration:
        raise AwsSyncrError("Please define lambda functions under the 'lambda' section of your configuration")

    if not lambda_function:
        raise AwsSyncrError("Please specify --artifact for the lambda function to deploy")

    wanted = ['lambda', lambda_function]
    if wanted not in collector.configuration:
        raise AwsSyncrError("Couldn't find specified lambda function", available=list(collector.configuration["lambda"].items.keys()))

    collector.configuration['lambda'].items[lambda_function].deploy(aws_syncr, amazon)
