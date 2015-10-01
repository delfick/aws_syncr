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

