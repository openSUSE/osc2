"""Defines the request command."""

from osc.cli.cli import OscCommand, call
from osc.cli.description import CommandDescription, Option
from osc.cli.request.request import RequestController


class Request(CommandDescription, OscCommand):
    """Show and modify requests."""
    cmd = 'request'


class RequestList(CommandDescription, Request):
    """List requests.

    By default open requests for a specific project or package will be
    listed.

    Examples:
    osc request list api://
    osc request list api://project
    osc request list api://project/package

    """
    cmd = 'list'
    args = 'api://project?/package?'
    opt_user = Option('U', 'user', 'list only requests for USER')
    opt_group = Option('G', 'group', 'list only requests for GROUP')
    opt_state = Option('s', 'state', 'list only requests with state STATE',
                       choices=['new', 'review', 'accepted', 'revoked',
                                'declined', 'superseded'], action='append',
                       default=['new', 'review'])
    func = call(RequestController.list)


class RequestShow(CommandDescription, Request):
    """Show request.

    Prints more details than the list view.

    Examples:
    osc request show api://reqid
    osc request show api://reqid --diff

    """
    cmd = 'show'
    args = 'api://reqid'
    func = call(RequestController.show)
    opt_diff = Option('d', 'diff', 'generate a diff for the request',
                      action='store_true')


class ChangeStateOptions(object):
    """Defines a set of options which are needed for a state change.

    All state changing commands should inherit from this class.

    """
    opt_message = Option('m', 'message', 'specify a message')
    opt_force = Option('f', 'force', 'try to force the state change',
                       action='store_true')


class RequestAccept(CommandDescription, Request, ChangeStateOptions):
    """Accept a specific request.

    If no message is specified $EDITOR is opened.

    Example:
    osc request accept api://reqid [--message MESSAGE]

    """
    cmd = 'accept'
    args = 'api://reqid'
    func = call(RequestController.change_request_state)
    func_defaults = {'method': 'accept'}


class RequestDecline(CommandDescription, Request, ChangeStateOptions):
    """Decline a specific request.

    If no message is specified $EDITOR is opened.

    Example:
    osc request decline api://reqid [--message MESSAGE]

    """
    cmd = 'decline'
    args = 'api://reqid'
    func = call(RequestController.change_request_state)
    func_defaults = {'method': 'decline'}


class RequestRevoke(CommandDescription, Request, ChangeStateOptions):
    """Revoke a specific request.

    If no message is specified $EDITOR is opened.

    Example:
    osc request revoke api://reqid [--message MESSAGE]

    """
    cmd = 'revoke'
    args = 'api://reqid'
    func = call(RequestController.change_request_state)
    func_defaults = {'method': 'revoke'}


class RequestSupersede(CommandDescription, Request, ChangeStateOptions):
    """Supersede a request with another (existing) request.

    Example:
    osc request supersede api://reqid api://supersede_id [--message MESSAGE]

    """
    cmd = 'supersede'
    args = 'api://reqid api://supersede_id'
    func = call(RequestController.change_request_state)
    func_defaults = {'method': 'supersede'}


class RequestCreate(CommandDescription, Request):
    """Create a new request.

    Example:
    osc request create --submit api://src_project/src_package api://tgt_project
        [--message MESSAGE]
    osc request create --delete api://project/<package> [--message MESSAGE]
    osc request create --role role user api://project/<package>
    etc.

    It is also possible to specify multiple options at the same time (also
    multiple options of the same name are supported).

    """
    cmd = 'create'
    opt_message = Option('m', 'message', 'specify a message')
    opt_submit = Option('', 'submit', 'create new submit action',
                        oargs=('api://src_project/src_package@rev? '
                               'api://tgt_project/tgt_package?'),
                        nargs=2, action='append', default=[])
    opt_changedevel = Option('', 'changedevel',
                             'create new changedevel action',
                             oargs=('api://src_project/src_package '
                                    'api://tgt_project/tgt_package?'),
                             nargs=2, action='append', default=[])
    opt_role = Option('', 'role', 'create new role action',
                      oargs='role user api://project/package?',
                      nargs=3, action='append', default=[])
    opt_grouprole = Option('', 'grouprole', 'create new grouprole action',
                           oargs='role group api://project/package?',
                           nargs=3, action='append', default=[])
    opt_delete = Option('', 'delete', 'create new delete action',
                        oargs='api://project/package?',
                        nargs=1, action='append', default=[])
    func = call(RequestController.create)
