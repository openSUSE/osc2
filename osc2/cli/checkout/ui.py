"""Defines the checkout command."""

from osc2.cli.cli import OscCommand, call
from osc2.cli.description import CommandDescription, Option
from osc2.cli.checkout.checkout import WCCheckoutController


class Checkout(CommandDescription, OscCommand):
    """Checkout project, package, or file.

    Examples:
    osc2 checkout api://project                 # checkout project
    osc2 checkout api://project/package         # checkout package
    osc2 checkout /path/to/project              # revert all local
                                                  modifications in the project
                                                  working copy
    osc2 checkout /path/to/project/package      # revert all local
                                                  modifications in the package
                                                  working copy
    osc2 checkout /path/to/project/package/file # revert the file file

    """
    cmd = 'checkout'
    args = '(api://project/package?|wc_path)*'
    opt_expand = Option('u', 'unexpand', 'do not expand a source link',
                        action='store_true')
    opt_revision = Option('r', 'revision', 'list revision',
                          default='latest')
    func = call(WCCheckoutController().checkout)
