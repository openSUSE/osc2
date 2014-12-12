"""Defines the add command."""

from osc2.cli.cli import OscCommand, call
from osc2.cli.description import CommandDescription, Option
from osc2.cli.add.add import add


class Add(CommandDescription, OscCommand):
    """Adds a package or a file to a working copy.

    Examples:
    osc2 add /path/prj/pkg      # adds pkg to the prj working copy
    osc2 add /path/prj/pkg/file # adds file to the pkg working copy

    """
    cmd = 'add'
    args = '(wc_path)+'
    opt_package_only = Option('', 'package-only',
                              'only add the package, but not its files',
                              action='store_true')
    func = call(add)
