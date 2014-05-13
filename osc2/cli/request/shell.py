"""Defines commands for the interactive request shell."""

from osc2.cli.description import build_description, Option
from osc2.cli.cli import call
from osc2.cli.request.request import (RequestShellController,
                                      AbstractRequestShell)


ShellCommand = build_description('ShellCommand', {})


class RequestShellUI(ShellCommand):
    """Interactive request shell."""
    controller = RequestShellController()


class ChangeStateOptions(object):
    """Defines a set of options which are needed for a state change.

    All state changing commands should inherit from this class.

    """
    opt_message = Option('m', 'message', 'specify a message')
    opt_force = Option('f', 'force', 'try to force the state change',
                       action='store_true')


class RequestAccept(ShellCommand, RequestShellUI, ChangeStateOptions):
    """Accept a specific request.

    If no message is specified $EDITOR is opened.

    Example:
    accept [--message MESSAGE]

    """
    cmd = 'accept'
    func = call(RequestShellUI.controller.change_request_state)
    func_defaults = {'method': 'accept'}


class RequestDecline(ShellCommand, RequestShellUI, ChangeStateOptions):
    """Decline a specific request.

    If no message is specified $EDITOR is opened.

    Example:
    decline [--message MESSAGE]

    """
    cmd = 'decline'
    func = call(RequestShellUI.controller.change_request_state)
    func_defaults = {'method': 'decline'}


class RequestRevoke(ShellCommand, RequestShellUI, ChangeStateOptions):
    """Revoke a specific request.

    If no message is specified $EDITOR is opened.

    Example:
    revoke [--message MESSAGE]

    """
    cmd = 'revoke'
    func = call(RequestShellUI.controller.change_request_state)
    func_defaults = {'method': 'revoke'}


class RequestSupersede(ShellCommand, RequestShellUI, ChangeStateOptions):
    """Supersede a request with another (existing) request.

    Example:
    supersede [--message MESSAGE]

    """
    cmd = 'supersede'
    args = 'supersede_id'
    opt_message = Option('m', 'message', 'specify a message')
    func = call(RequestShellUI.controller.change_request_state)
    func_defaults = {'method': 'supersede'}


class RequestDiff(ShellCommand, RequestShellUI):
    """Display the diff for the current request.

    Example:
    diff

    """
    cmd = 'diff'
    func = call(RequestShellUI.controller.diff)


class RequestSkip(ShellCommand, RequestShellUI):
    """Skip the current request.

    Example:
    skip

    """
    cmd = 'skip'
    func = call(RequestShellUI.controller.skip)


class RequestShell(AbstractRequestShell):
    """Represents a request shell."""

    def _root_cmd_cls(self):
        return RequestShellUI
