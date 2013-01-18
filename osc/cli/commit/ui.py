"""Defines the commit command."""

from osc.cli.cli import OscCommand, call
from osc.cli.description import CommandDescription, Option
from osc.cli.commit.commit import WCCommitController


class Commit(CommandDescription, OscCommand):
    """Update project or package.

    Examples:
    osc commit                          # in a project or package wc
    osc commit project                  # update project
    osc commit package                  # update package
    osc commit /path/to/wc/or/wc/file   # update package

    """
    cmd = 'commit'
    args = '(wc_path)?'
    opt_message = Option('m', 'message', 'specify a message')
    func = call(WCCommitController().commit)
