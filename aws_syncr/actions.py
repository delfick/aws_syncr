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
    changes = False
    for name, role in collector.configuration["roles"].roles.items():
        changes = changes or syncr.sync_role(role)

    if not changes:
        log.info("No changes were made!!")

