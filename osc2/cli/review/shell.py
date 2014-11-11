"""Defines commands for the interactive review shell."""

from osc2.cli.description import build_description, Option
from osc2.cli.cli import call
from osc2.cli.request.request import AbstractRequestShell
from osc2.cli.review.review import ReviewShellController
from osc2.cli.util.shell import TransparentRenderableItemSelectorFactory


ShellCommand = build_description('ShellCommand', {})
ItemSelectorFactory = TransparentRenderableItemSelectorFactory()


class ReviewShellUI(ShellCommand):
    """Interactive review shell."""
    controller = ReviewShellController()


class ReviewGlobalOptions(object):
    """Defines a set of global options.

    All review subcommands should inherit from this class.

    """
    opt_user = Option('U', 'user', 'use by_user')
    opt_group = Option('G', 'group', 'use by_group')
    opt_project = Option('P', 'project', 'use by_project')
    opt_package = Option('p', 'package', 'use by_package',
                         oargs='project/package', nargs=1, default=[])


class ChangeStateOptions(ReviewGlobalOptions):
    """Defines a set of options which are needed for a state change.

    All state changing commands should inherit from this class.

    """
    opt_message = Option('m', 'message', 'specify a message')
    opt_force = Option('f', 'force', 'try to force the state change',
                       action='store_true')
    # the options are not required because it is possible to select
    # a review manually
    mutex_group = [ReviewGlobalOptions.opt_user,
                   ReviewGlobalOptions.opt_group,
                   ReviewGlobalOptions.opt_project,
                   ReviewGlobalOptions.opt_package]


class ReviewAccept(ShellCommand, ReviewShellUI, ChangeStateOptions):
    """Accept a specific review.

    If no message is specified $EDITOR is opened.

    Example:
    accept [--message MESSAGE]

    """
    cmd = 'accept'
    func = call(ReviewShellUI.controller.change_review_state)
    func_defaults = {'method': 'accept',
                     'item_selector_factory': ItemSelectorFactory}


class ReviewDecline(ShellCommand, ReviewShellUI, ChangeStateOptions):
    """Decline a specific review.

    If no message is specified $EDITOR is opened.

    Example:
    decline [--message MESSAGE]

    """
    cmd = 'decline'
    func = call(ReviewShellUI.controller.change_review_state)
    func_defaults = {'method': 'decline',
                     'item_selector_factory': ItemSelectorFactory}


class ReviewRevoke(ShellCommand, ReviewShellUI, ChangeStateOptions):
    """Revoke a specific review.

    If no message is specified $EDITOR is opened.

    Example:
    revoke [--message MESSAGE]

    """
    cmd = 'revoke'
    func = call(ReviewShellUI.controller.change_review_state)
    func_defaults = {'method': 'revoke',
                     'item_selector_factory': ItemSelectorFactory}


class ReviewSupersede(ShellCommand, ReviewShellUI, ChangeStateOptions):
    """Supersede a request with another (existing) request.

    Example:
    supersede [--message MESSAGE]

    """
    cmd = 'supersede'
    args = 'supersede_id'
    opt_message = Option('m', 'message', 'specify a message')
    func = call(ReviewShellUI.controller.change_review_state)
    func_defaults = {'method': 'supersede',
                     'item_selector_factory': ItemSelectorFactory}


class ReviewDiff(ShellCommand, ReviewShellUI):
    """Display the diff for the current request.

    Example:
    diff

    """
    cmd = 'diff'
    func = call(ReviewShellUI.controller.diff)


class ReviewSkip(ShellCommand, ReviewShellUI):
    """Skip the current request.

    Example:
    skip

    """
    cmd = 'skip'
    func = call(ReviewShellUI.controller.skip)


class ReviewShell(AbstractRequestShell):
    """Represents a review shell."""

    def __init__(self, global_by_kind_filter, *args, **kwargs):
        """Constructs a new ReviewShell object.

        global_by_kind_filter can be used to filter reviews. If the
        user issues for instance the "accept" command (without
        any additional -G, -P, -p, -U option) only reviews which
        which match the "global_by_kind_filter" can be accepted.
        If the user issues "accept -U some_user" the global_by_kind_filter
        is ignored and only reviews which match the "-U some_user" filter
        can be accepted.
        global_by_kind_filter is a 2-tuple (by_kind, value) or None.
        *args and **kwargs are passed to the base class' __init__ method.

        """
        super(ReviewShell, self).__init__(*args, **kwargs)
        self._global_by_kind_filter = global_by_kind_filter

    def _augment_info(self, info):
        super(ReviewShell, self)._augment_info(info)
        if (self._global_by_kind_filter is not None
                and 'user' in info and 'group' in info
                and 'project' in info and 'package' in info
                and info.user is None and info.group is None
                and info.project is None and not info.package):
            # use global_by_kind_filter if no filter was specified
            # by the user
            info.set(self._global_by_kind_filter[0],
                     self._global_by_kind_filter[1])

    def _root_cmd_cls(self):
        return ReviewShellUI
