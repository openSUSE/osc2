"""Provides various functions for the "review" command."""

import logging

from osc2.util.xpath import XPathBuilder
from osc2.remote import Request
from osc2.search import find_request
from osc2.cli.util.env import edit_message
from osc2.cli.request.request import AbstractRequestController, SHOW_TEMPLATE


REVIEW_TEMPLATE = 'review/request_review.jinja2'
SELECTION_TEMPLATE = 'review/selection.jinja2'
NO_REVIEW_FOUND_TEMPLATE = 'review/no_review_found.jinja2'


def logger():
    """Returns a logging.Logger object."""
    return logging.getLogger(__name__)


class BaseReviewController(AbstractRequestController):
    """Base class for review controllers."""

    @classmethod
    def list(cls, renderer, tgt_project, tgt_package, info):
        """Lists requests for the given project and package.

        project and package might be None.

        """
        super(BaseReviewController, cls).list(renderer, tgt_project,
                                              tgt_package, info)

    @classmethod
    def _change_review_state(cls, renderer, request, review, method, message,
                             info, supersede_id=None):
        """Changes the state of a review.

        method is the method which is called on the
        retrieved request object.
        If message is None $EDITOR is opened.

        """
        cls._change_request_state(renderer, request, method, message,
                                  info, supersede_id, review)

    @classmethod
    def _find_reviews(cls, request, info):
        """Returns a list of reviews.

        If no reviews were found an empty list is returned.
        """
        xpb = XPathBuilder(context_item=True)
        by_kind, xp = cls._build_by_predicate(xpb, info, [])
        if not by_kind:
            # return all reviews
            xp = xpb.review
        logger().debug(xp.tostring())
        return request.findall(xp.tostring())

    @classmethod
    def _build_by_predicate(cls, xpb, info, states):
        """Builds a by_<kind> predicate.

        States is a list of states or the empty list.
        Returns a two tuple. The first element indicates whether
        a at least one by_ predicate was build

        """
        by_kind = False
        xp = xpb.dummy()
        if info.user is not None:
            pred = xpb.attr('by_user') == info.user
            xp = xp | cls._add_states(xpb, pred, states)
            by_kind = True
        if info.group is not None:
            pred = xpb.attr('by_group') == info.group
            xp = xp | cls._add_states(xpb, pred, states)
            by_kind = True
        if info.project is not None:
            pred = xpb.attr('by_project') == info.project
            xp = xp | cls._add_states(xpb, pred, states)
            by_kind = True
        if info.package:
            # info.package is a list
            pred = ((xpb.attr('by_project') == info.package[0].project)
                    & (xpb.attr('by_package') == info.package[0].package))
            xp = xp | cls._add_states(xpb, pred, states)
            by_kind = True
        return by_kind, xp

    @classmethod
    def _add_states(cls, xpb, pred, states):
        """Adds states to the existing predicate pred.

        states is a list of states or the empty list.

        """
        st_pred = xpb.dummy()
        for state in states:
            st_pred = st_pred | (xpb.attr('state') == state)
        return xpb.review[pred & st_pred.parenthesize()]

    @classmethod
    def _find_requests(cls, tgt_project, tgt_package, info):
        """Returns a collection of requests."""
        xpb = XPathBuilder(is_relative=True)
        xp = xpb.dummy()
        by_kind, xp = cls._build_by_predicate(xpb, info, info.state)
        if not by_kind:
            xp = cls._add_states(xpb, xpb.dummy(), info.state)
        xp = (xpb.state.attr('name') == 'review') & xp.parenthesize()
        if tgt_project is not None:
            xp = xp & (xpb.action.target.attr('project') == tgt_project)
        if tgt_package is not None:
            xp = xp & (xpb.action.target.attr('package') == tgt_package)
        logger().debug(xp.tostring())
        res = find_request(xp=xp, apiurl=info.apiurl)
        collection = [r for r in res]
        return collection


class ReviewController(BaseReviewController):
    """Concrete ReviewController."""

    @classmethod
    def change_review_state(cls, renderer, reqid, method, message, info,
                            supersede_id=None):
        """Changes the state of a review.

        method is the method which is called on the
        retrieved request object.
        If message is None $EDITOR is opened.

        """
        request = Request.find(reqid)
        reviews = cls._find_reviews(request, info)
        if reviews:
            # take the first review
            cls._change_review_state(renderer, request, reviews[0], method,
                                     message, info, supersede_id)

    @classmethod
    def add(cls, renderer, reqid, message, info):
        """Adds a new review to a request."""
        request = Request.find(reqid)
        if message is None:
            message = edit_message()
        kwargs = {'comment': message, 'by_user': info.user,
                  'by_group': info.group}
        if info.package:
            kwargs['by_project'] = info.package[0].project
            kwargs['by_package'] = info.package[0].package
        elif info.project is not None:
            kwargs['by_project'] = info.project
        request.add_review(**kwargs)
        renderer.render(SHOW_TEMPLATE, request=request)

    @classmethod
    def shell(cls, renderer, shell_cls, requests, info):
        """Starts an interactive request shell."""
        global_by_kind_filter = None
        if info.user is not None:
            global_by_kind_filter = ('user', info.user)
        if info.group is not None:
            global_by_kind_filter = ('group', info.group)
        if info.project is not None:
            global_by_kind_filter = ('project', info.project)
        if info.package:
            global_by_kind_filter = ('package', info.package)
        sh = shell_cls(global_by_kind_filter, renderer)
        sh.run(requests)


class ReviewShellController(BaseReviewController):
    """Controller for the review shell."""

    @classmethod
    def change_review_state(cls, renderer, request, method, message, info,
                            supersede_id=None):
        """Changes the state of a review."""
        global REVIEW_TEMPLATE
        global SELECTION_TEMPLATE
        global NO_REVIEW_FOUND_TEMPLATE
        reviews = cls._find_reviews(request, info)
        if not reviews:
            info.shell.render(NO_REVIEW_FOUND_TEMPLATE, request=request,
                              info=info)
            return False
        review = reviews[0]
        if len(reviews) > 1:
            items = dict(((str(i), review)
                          for i, review in enumerate(reviews)))
            selector = info.item_selector_factory.create(items,
                                                         renderer,
                                                         SELECTION_TEMPLATE,
                                                         REVIEW_TEMPLATE)
            review = selector.run()
        # here we use info.shell as a "renderer" because the data should be
        # presented in the shell. atm we could also use the "renderer" object
        # directly but this is "semantically" wrong
        cls._change_review_state(info.shell, request, review, method, message,
                                 info, supersede_id)
        return True

    def skip(self):
        """Skips the current request."""
        return True
