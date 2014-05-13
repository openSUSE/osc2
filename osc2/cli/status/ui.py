"""Defines the status command."""

from osc2.cli.cli import OscCommand, call
from osc2.cli.description import CommandDescription, Option
from osc2.cli.status.status import status


class Status(CommandDescription, OscCommand):
    """Status of package or package file.

    Examples:
    osc status                          # in a project or package wc
    osc status project                  # update project
    osc status package                  # update package
    osc status /path/to/wc/or/wc/file   # update package

    """
    cmd = 'status'
    args = '(wc_path)?'
    opt_verbose = Option('v', 'verbose', 'also print unchanged states',
                         action='store_true')
    func = call(status)
