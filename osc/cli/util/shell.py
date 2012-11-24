"""Provides an abstract base class for an interactive shell."""

import readline
import subprocess

from osc.cli import parse


class ShellSyntaxError(SyntaxError):
    """Represents a shell syntax error."""
    pass


class AbstractShell(object):
    """Represents an abstract base class for a shell."""

    def __init__(self, renderer, clear='clear', complete=True):
        """Constructs a new AbstractShell object.

        renderer is a renderer.

        Keyword arguments:
        clear -- path to the clear binary (default: 'clear')
        complete -- if True root commands can be tab-completed (default: True)

        """
        self._renderer = renderer
        self._clear = clear
        if complete:
            readline.set_completer(self.complete)
            readline.parse_and_bind('tab: complete')

    def complete(self, text, state):
        """Acts as a readline completer function.

        Completion only works for top level commands (adding
        completion for subcommands is probably a bit more work).

        """
        root_cls = self._root_cmd_cls()
        cmd_cls = root_cls.cls_map()[root_cls.__name__]
        matches = [cls.cmd for cls in cmd_cls if cls.cmd.startswith(text)]
        match = None
        try:
            match = matches[state]
        except IndexError:
            pass
        return match

    def _check_input(self, inp):
        """Checks user input for syntax errors.

        inp is the user input. In case of a syntax error
        a SyntaxError is raised.

        """
        cnt = 0
        for i in xrange(len(inp)):
            if inp[i] != '"':
                continue
            cnt += 1
            if i == 0 or i == len(inp) - 1:
                continue
            if (cnt % 2 == 0 and inp[i + 1] != ' '
                or cnt % 2 == 1 and inp[i - 1] != ' '):
                msg = "invalid user input: %s (wrong quoting)" % inp
                raise ShellSyntaxError(msg)
        return cnt % 2 == 0

    def _split_input(self, inp):
        """Returns the whitespace splitted user input.

        Additionally quoted text is interpreted as a single
        element.

        """
        l = inp.split(' ')
        data = []
        while l:
            cur = l.pop(0)
            if cur.startswith('"') and not cur.endswith('"'):
                tmp = [cur]
                while l and not cur.endswith('"'):
                    cur = l.pop(0)
                    tmp.append(cur)
                data.append(' '.join(tmp).strip('"'))
            else:
                data.append(cur.strip('"'))
        return data

    def prompt(self, text='', prompt='> '):
        """Returns the str entered by the user.

        Keyword arguments:
        text -- print text before prompting for input (default: '')
        prompt -- specify a prompt (default: '> ')

        """
        if text:
            self._renderer.render_text(text)
        inp = raw_input(prompt)
        self._check_input(inp)
        while not self._check_input(inp):
            inp += "\n" + raw_input()
        return inp

    def render(self, *args, **kwargs):
        """Displays data to the user.

        It simply delegates the render call to
        the renderer object.

        """
        self._renderer.render(*args, **kwargs)

    def clear(self):
        """Clears the terminal screen."""
        subprocess.call([self._clear], shell=False)

    def _execute(self, req, inp):
        """Executes user specified command.

        req is the request which should be manipulated. inp
        is the user input.
        Returns True if the next request should be considered
        otherwise False.

        """
        args = self._split_input(inp)
        info = parse.parse(self._root_cmd_cls(), args)
        self._augment_info(info)
        return info.func(info)

    def _augment_info(self, info):
        """Adds or modifies the info object.

        info is a osc.oscargs.ResolvedInfo instance which
        is returned by the parse.parse method.
        Subclasses may override this method.

        """
        info.set('shell', self)

    def _root_cmd_cls(self):
        """Returns the root command class.

        The root command class is used to initialize the
        argument parser.

        """
        raise NotImplementedError()

    def run(self, *args, **kwargs):
        """Runs the shell with the specified args and kwargs."""
        raise NotImplementedError()
