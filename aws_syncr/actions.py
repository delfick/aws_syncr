from aws_syncr.operations.syncer import Syncer

import logging

log = logging.getLogger("aws_syncr.actions")

available_actions = {}

def an_action(func):
    available_actions[func.__name__] = func
    return func

@an_action
def sync(collector):
    """Sync an environment"""
    syncr = Syncer(collector.configuration['aws_syncr'], collector.configuration['amazon'])

    # Convert everything before we try and sync anything
    converted = {}
    for thing, singular in (("roles", "role"), ("buckets", "bucket")):
        if thing in collector.configuration:
            converted[thing] = (singular, getattr(collector.configuration[thing], thing).items())

    # Do the sync
    for singular, items in converted.values():
        for name, item in items:
            getattr(syncr, "sync_{0}".format(singular))(item)

    if not syncr.amazon.changes:
        log.info("No changes were made!!")

