import argparse
import sys
from gettext import gettext

class ColoredArgParser(argparse.ArgumentParser):

    # color_dict is a class attribute, here we avoid compatibility
    # issues by attempting to override the __init__ method
    # RED : Error, GREEN : Okay, YELLOW : Warning, Blue: Help/Info 
    color_dict = {'RED' : '1;31', 'GREEN' : '1;32', 
                'YELLOW' : '1;33', 'BLUE' : '1;36'}

    def print_usage(self, file = None):
        if file is None:
            file = sys.stdout
        self._print_message(self.format_usage()[0].upper() + 
                            self.format_usage()[1:],
                            file, self.color_dict['YELLOW'])

    def print_help(self, file = None):
        if file is None:
            file = sys.stdout
        self._print_message(self.format_help()[0].upper() +
                            self.format_help()[1:],
                            file, self.color_dict['BLUE'])

    def _print_message(self, message, file = None, color = None):
        if message:
            if file is None:
                file = sys.stderr
            # Print messages in bold, colored text if color is given.
            if color is None:
                file.write(message)
            else:
                # \x1b[ is the ANSI Control Sequence Introducer (CSI)
                file.write('\x1b[' + color + 'm' + message.strip() + '\x1b[0m\n')

    def exit(self, status = 0, message = None):
        if message:
            self._print_message(message, sys.stderr, self.color_dict['RED'])
        sys.exit(status)

    def error(self, message):
        self.print_usage(sys.stderr)
        args = {'prog' : self.prog, 'message': message}
        self.exit(2, gettext('%(prog)s: Error: %(message)s\n') % args)
