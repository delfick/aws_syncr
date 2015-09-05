import logging

log = logging.getLogger("aws_syncr.actions")

available_actions = {}

def an_action(func):
    available_actions[func.__name__] = func
    return func

@an_action
def sync(collector):
    """Sync an environment"""
    for thing in ('roles', ):
        log.info("Syncing %s", thing)
        collector.configuration[thing].sync()

