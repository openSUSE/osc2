"""Defines the checkout command."""

from osc2.cli.cli import OscCommand, call
from osc2.cli.description import CommandDescription, Option
from osc2.cli.checkout.checkout import WCCheckoutController


class Checkout(CommandDescription, OscCommand):
    """Checkout project or package.

    Examples:
    osc checkout api://project          # checkout project
    osc checkout api://project/package  # checkout package

    """
    cmd = 'checkout'
    args = '(api://project/package?|wc_path)*'
    opt_expand = Option('u', 'unexpand', 'do not expand a source link',
                        action='store_true')
    opt_revision = Option('r', 'revision', 'list revision',
                          default='latest')
    func = call(WCCheckoutController().checkout)
