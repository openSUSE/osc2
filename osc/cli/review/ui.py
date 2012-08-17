"""Defines the review command."""

from osc.cli.cli import OscCommand, call
from osc.cli.description import CommandDescription, Option
from osc.cli.review.review import ReviewController


class Review(CommandDescription, OscCommand):
    """Show and modify reviews."""
    cmd = 'review'
    opt_user = Option('U', 'user', 'use by_user', sub=True)
    opt_group = Option('G', 'group', 'use by_group', sub=True)
    opt_project = Option('P', 'project', 'use by_project', sub=True)
    opt_package = Option('p', 'package', 'use by_package', sub=True,
                         oargs='project/package', nargs=1, default=[])


class ReviewList(CommandDescription, Review):
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
    func = call(ReviewController.list)


class ReviewAccept(CommandDescription, Review):
    """Accept a specific review.

    If no message is specified $EDITOR is opened.

    Example:
    osc review accept api://reqid [--message MESSAGE] --user <user>

    """
    cmd = 'accept'
    args = 'api://reqid'
    opt_message = Option('m', 'message', 'specify a message')
    mutex_req_group = [Review.opt_user, Review.opt_group, Review.opt_project,
                       Review.opt_package]
    func = call(ReviewController.change_review_state)
    func_defaults = {'method': 'accept'}


class ReviewDecline(CommandDescription, Review):
    """Decline a specific review.

    If no message is specified $EDITOR is opened.

    Example:
    osc review decline api://reqid [--message MESSAGE] --user <user>

    """
    cmd = 'decline'
    args = 'api://reqid'
    opt_message = Option('m', 'message', 'specify a message')
    mutex_req_group = [Review.opt_user, Review.opt_group, Review.opt_project,
                       Review.opt_package]
    func = call(ReviewController.change_review_state)
    func_defaults = {'method': 'decline'}


class ReviewRevoke(CommandDescription, Review):
    """Revoke a specific review.

    If no message is specified $EDITOR is opened.

    Example:
    osc review revoke api://reqid [--message MESSAGE] --user <user>

    """
    cmd = 'revoke'
    args = 'api://reqid'
    opt_message = Option('m', 'message', 'specify a message')
    mutex_req_group = [Review.opt_user, Review.opt_group, Review.opt_project,
                       Review.opt_package]
    func = call(ReviewController.change_review_state)
    func_defaults = {'method': 'revoke'}


class ReviewSupersede(CommandDescription, Review):
    """Supersede a specific review.

    If no message is specified $EDITOR is opened.

    Example:
    osc review supersede api://reqid api://supersede_id [--message MESSAGE]
        --user <user>

    """
    cmd = 'supersede'
    args = 'api://reqid api://supersede_id'
    opt_message = Option('m', 'message', 'specify a message')
    mutex_req_group = [Review.opt_user, Review.opt_group, Review.opt_project,
                       Review.opt_package]
    func = call(ReviewController.change_review_state)
    func_defaults = {'method': 'supersede'}


class ReviewAdd(CommandDescription, Review):
    """Add a new review to the request.

    If no message is specified $EDITOR is opened.

    Example:
    osc review add api://reqid [--message MESSAGE] --user <user>

    """
    cmd = 'add'
    args = 'api://reqid'
    opt_message = Option('m', 'message', 'specify a message')
    mutex_req_group = [Review.opt_user, Review.opt_group, Review.opt_project,
                       Review.opt_package]
    func = call(ReviewController.add)
