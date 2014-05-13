"""Defines the review command."""

from osc2.cli.cli import OscCommand, call
from osc2.cli.description import CommandDescription, Option
from osc2.cli.list import list


class List(CommandDescription, OscCommand):
    """List projects, packages and files.

    Examples:
    osc list api://                 # list all projects
    osc list api://project          # list all packages in project
    osc list api://project/package  # list all files in package

    """
    cmd = 'list'
    args = '(api://project?/package?)?'
    use_wc = True
    opt_verbose = Option('v', 'verbose', 'verbose listing (for files only)',
                         action='store_true')
    opt_expand = Option('e', 'expand', 'expand a source link',
                        action='store_true')
    opt_revision = Option('r', 'revision', 'list revision (for files only)',
                          default='latest')
    opt_deleted = Option('D', 'deleted', 'show deleted projects or packages',
                         action='store_true')
    opt_meta = Option('M', 'meta', 'list package\'s meta files',
                      action='store_true')
    func = call(list.list)
