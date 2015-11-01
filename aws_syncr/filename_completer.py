from aws_syncr.errors import UserQuit

from six.moves import input
import readline
import glob
import os

def setup_completer():
    if 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")
    readline.set_completer(NoneCompleter)

class NoneCompleter(object):
    def complete(self, text, state):
        self.matches = []
        return None

class FilenameCompleter(object):
    def complete(self, text, state):
        text = os.path.expanduser(readline.get_line_buffer())
        if not text:
            self.matches = glob.glob("*")
        else:
            if os.path.isfile(text):
                self.matches = []

            else:
                dirname = os.path.dirname(text)
                if not dirname:
                    self.matches = glob.glob("*")
                else:
                    self.matches = glob.glob(os.path.join(dirname, "*"))

            self.matches = [os.path.basename(match) for match in self.matches if match.startswith(text)]

        if len(self.matches) > state:
            if len(self.matches) == 1:
                if os.path.isdir(os.path.join(os.path.dirname(text), self.matches[state])):
                    return "{0}/".format(self.matches[state])
            return self.matches[state]
        else:
            return None

def custom_prompt(msg, delims="", completer=lambda: None):
    """Start up a prompt that with particular delims and completer"""
    try:
        orig_delims = readline.get_completer_delims()
        orig_completer = readline.get_completer()

        readline.set_completer_delims(delims)
        readline.set_completer(completer)

        try:
            ret = input(msg)
        finally:
            readline.set_completer_delims(orig_delims)
            readline.set_completer(orig_completer)

        return ret
    except EOFError:
        raise UserQuit()

def filename_prompt(msg, delims="/"):
    completer = FilenameCompleter().complete
    return custom_prompt(msg, delims, completer)

