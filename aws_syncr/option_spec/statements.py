from aws_syncr.errors import BadOption

from input_algorithms.spec_base import NotSpecified
from input_algorithms import spec_base as sb

class statement_spec(sb.Spec):
    args = None
    final_kls = None
    invalid_args = []

    def setup(self, self_type, self_name):
        self.self_type = self_type
        self.self_name = self_name
        if not self.args or not self.final_kls:
            raise NotImplementedError("Need to use a subclass of statement_spec that defines args and final_kls")

    def normalise(self, meta, val):
        nsd = lambda spec: sb.defaulted(spec, NotSpecified)
        args = {}
        for arg, spec in self.args(self.self_type, self.self_name).items():
            if type(arg) is tuple:
                capitalized = ''.join(part.capitalize() for part in arg)
                arg = ''.join(arg)
            else:
                capitalized = arg.capitalize()
            args[(arg, capitalized)] = spec

        kwargs = {}
        for (arg, capitalized), spec in list(args.items()):
            kwargs[arg] = nsd(spec)
            kwargs[capitalized] = sb.any_spec()
        val = sb.set_options(**kwargs).normalise(meta, val)

        kwargs = {}
        for (arg, capitalized) in args:
            if val.get(arg, NotSpecified) is not NotSpecified and val.get(capitalized, NotSpecified) is not NotSpecified:
                raise BadOption("Cannot specify arg as special and capitalized at the same time", arg=arg, special_val=val.get(arg), captialized_val=val.get(capitalized), meta=meta)
            else:
                kwargs[arg] = val[capitalized] if val[capitalized] is not NotSpecified else val[arg]

        for arg in self.invalid_args:
            if type(arg) is tuple:
                capitalized = ''.join(part.capitalize() for part in arg)
                arg = ''.join(arg)
            else:
                capitalized = arg.capitalize()

            if arg in val or capitalized in val:
                raise BadOption("Cannot specify arg in this statement", arg=arg, capitalized=capitalized, meta=meta)

        return self.final_kls(**kwargs)

