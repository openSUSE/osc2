"""Defines the update command."""

from osc2.cli.cli import OscCommand, call
from osc2.cli.description import CommandDescription, Option
from osc2.cli.update.update import WCUpdateController


class Update(CommandDescription, OscCommand):
    """Update project or package.

    Examples:
    osc update                  # in a project or package wc
    osc update project          # update project
    osc update package          # update package

    """
    cmd = 'update'
    args = '(wc_path)?'
    opt_expand = Option('u', 'unexpand', 'do not expand a source link',
                        action='store_true')
    opt_revision = Option('r', 'revision', 'list revision',
                          default='latest')
    func = call(WCUpdateController().update)
