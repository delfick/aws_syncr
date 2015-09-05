from input_algorithms.errors import BadSpec, BadSpecValue
from delfick_error import DelfickError, ProgrammerError

class AwsSyncrError(DelfickError): pass

# Explicitly make these errors in this context
BadSpec = BadSpec
BadSpecValue = BadSpecValue
ProgrammerError = ProgrammerError

class BadConfiguration(AwsSyncrError):
    desc = "Bad configuration"

class BadOptionFormat(AwsSyncrError):
    desc = "Bad option format"

class BadOption(AwsSyncrError):
    desc = "Bad Option"

class BadYaml(AwsSyncrError):
    desc = "Invalid yaml file"

class UserQuit(AwsSyncrError):
    desc = "User quit the program"

class BadEnvironment(AwsSyncrError):
    desc = "Something bad in the environment"

class BadTask(AwsSyncrError):
    desc = "Bad task"

class BadCredentials(AwsSyncrError):
    desc = "Bad credentials"

class BadPolicy(AwsSyncrError):
    desc = "Bad policy"

