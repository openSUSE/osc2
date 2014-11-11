"""Defines the review command."""

from osc2.cli.cli import OscCommand, call
from osc2.cli.description import CommandDescription, Option
from osc2.cli.review.review import ReviewController
from osc2.cli.review.shell import ReviewShell


class Review(CommandDescription, OscCommand):
    """Show and modify reviews."""
    cmd = 'review'


class ReviewGlobalOptions(object):
    """Defines a set of global options.

    All review subcommands should inherit from this class.

    """
    opt_user = Option('U', 'user', 'use by_user')
    opt_group = Option('G', 'group', 'use by_group')
    opt_project = Option('P', 'project', 'use by_project')
    opt_package = Option('p', 'package', 'use by_package',
                         oargs='project/package', nargs=1, default=[])


class ReviewList(CommandDescription, Review, ReviewGlobalOptions):
    """List reviews.

    By default only requests with state review will be listed.

    Examples:
    osc review list api://
    osc review list api://project
    osc review list api://project/package

    """
    cmd = 'list'
    args = 'api://tgt_project?/tgt_package?'
    opt_state = Option('s', 'state',
                       ('list only requests which have a review with state '
                        'STATE'),
                       choices=['new', 'accepted', 'revoked', 'declined'],
                       action='append', default=['new'])
    opt_interactive = Option('i', 'interactive',
                             'start an interactive request shell',
                             action='store_true')
    func = call(ReviewController.list)
    func_defaults = {'shell_cls': ReviewShell}


class ReviewChangeStateOptions(ReviewGlobalOptions):
    """Defines options for change state commands (like accept etc.)"""
    opt_message = Option('m', 'message', 'specify a message')
    mutex_req_group = [ReviewGlobalOptions.opt_user,
                       ReviewGlobalOptions.opt_group,
                       ReviewGlobalOptions.opt_project,
                       ReviewGlobalOptions.opt_package]


class ReviewAccept(CommandDescription, Review, ReviewChangeStateOptions):
    """Accept a specific review.

    If no message is specified $EDITOR is opened.

    Example:
    osc review accept api://reqid [--message MESSAGE] --user <user>

    """
    cmd = 'accept'
    args = 'api://reqid'
    func = call(ReviewController.change_review_state)
    func_defaults = {'method': 'accept'}


class ReviewDecline(CommandDescription, Review, ReviewChangeStateOptions):
    """Decline a specific review.

    If no message is specified $EDITOR is opened.

    Example:
    osc review decline api://reqid [--message MESSAGE] --user <user>

    """
    cmd = 'decline'
    args = 'api://reqid'
    func = call(ReviewController.change_review_state)
    func_defaults = {'method': 'decline'}


class ReviewRevoke(CommandDescription, Review, ReviewChangeStateOptions):
    """Revoke a specific review.

    If no message is specified $EDITOR is opened.

    Example:
    osc review revoke api://reqid [--message MESSAGE] --user <user>

    """
    cmd = 'revoke'
    args = 'api://reqid'
    func = call(ReviewController.change_review_state)
    func_defaults = {'method': 'revoke'}


class ReviewSupersede(CommandDescription, Review, ReviewChangeStateOptions):
    """Supersede a specific review.

    If no message is specified $EDITOR is opened.

    Example:
    osc review supersede api://reqid api://supersede_id [--message MESSAGE]
        --user <user>

    """
    cmd = 'supersede'
    args = 'api://reqid api://supersede_id'
    func = call(ReviewController.change_review_state)
    func_defaults = {'method': 'supersede'}


class ReviewAdd(CommandDescription, Review, ReviewChangeStateOptions):
    """Add a new review to the request.

    If no message is specified $EDITOR is opened.

    Example:
    osc review add api://reqid [--message MESSAGE] --user <user>

    """
    cmd = 'add'
    args = 'api://reqid'
    func = call(ReviewController.add)
