available_actions = {}

def an_action(func):
    available_actions[func.__name__] = func
    return func

@an_action
def sync(collector):
    """Sync an environment"""
    print("Syncing an environment")

