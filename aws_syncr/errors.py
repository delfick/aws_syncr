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

class InvalidDocument(AwsSyncrError):
    desc = "Bad document"

class BadAmazon(AwsSyncrError):
    desc = "Bad Amazon"

class BadTemplate(AwsSyncrError):
    desc = "Bad template"

class InvalidGrant(AwsSyncrError):
    desc = "Bad Grant"

class BadImport(AwsSyncrError):
    desc = "Failed to import"

class UnknownStage(AwsSyncrError):
    desc = "Unknown stage"

class UnsyncedGateway(AwsSyncrError):
    desc = "Gateway not synced"

class UnknownZone(AwsSyncrError):
    desc = "Unknown zone"

class UnknownEndpoint(AwsSyncrError):
    desc = "Unknown endpoint"

