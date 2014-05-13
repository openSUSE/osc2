"""Provides some functions to run applications from the enviroment."""

import os
import subprocess
from tempfile import NamedTemporaryFile

from osc2.cli.cli import UserAbort
from osc2.util.io import copy_file


def run_pager(source, pager='less', suffix=''):
    """Runs pager on source source.

    If the env variable $PAGER is not set the
    pager keyword argument is used.
    Either source is a str or file or file-like
    object.

    Keyword arguments:
    pager -- the default pager (default: less)
    suffix -- the suffix of the tempfile (default: '')

    """
    cmd = [os.getenv('PAGER', default=pager)]
    with NamedTemporaryFile(prefix='osc_', suffix=suffix) as f:
        if hasattr(source, 'read'):
            copy_file(source, f)
        else:
            f.write(source)
        f.flush()
        cmd.append(f.name)
        return subprocess.call(cmd, shell=False)


def run_editor(source, editor='vim'):
    """Runs editor on source source.

    If the env variable $EDITOR is not set the
    editor keyword argument is used.
    source is a filename (that is a str).

    Keyword arguments:
    editor -- the default editor (default: vim)

    """
    cmd = [os.getenv('EDITOR', default=editor), source]
    return subprocess.call(cmd, shell=False)


def edit_message(template=None, footer=None, suffix=''):
    """Opens $EDITOR and displays the template and the footer.

    Returns the data entered by the user (everything after
    the delimeter is ignored).

    Keyword arguments:
    template -- the template str (default: None)
    footer -- the footer str (default: None)
    suffix -- the suffix of the tempfile (default: '')

    """
    delimeter = "--This line, and those below, will be ignored--\n"
    with NamedTemporaryFile(prefix='osc_', suffix=suffix) as f:
        if template is not None:
            f.write(template)
        f.write("\n" + delimeter)
        if footer is not None:
            f.write("\n" + footer)
        f.flush()
        message = ''
        while not message:
            run_editor(f.name)
            f.seek(0, os.SEEK_SET)
            message = f.read().split(delimeter, 1)[0].rstrip()
            if not message or message == template:
                choices = "(a)bort command, (i)gnore, (e)dit> "
                msg = "no message specified: " + choices
                if template == message:
                    msg = "template was not changed: " + choices
                repl = raw_input(msg)
                if repl.lower() == 'i':
                    return message
                elif repl.lower() != 'e':
                    raise UserAbort()
        return message
