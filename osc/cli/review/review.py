"""Provides various functions for the "review" command."""

import logging

from osc.util.xpath import XPathBuilder
from osc.remote import Request
from osc.search import find_request
from osc.cli.util.env import edit_message
from osc.cli.request.request import AbstractRequestController, SHOW_TEMPLATE


def logger():
    """Returns a logging.Logger object."""
    return logging.getLogger(__name__)


class ReviewController(AbstractRequestController):
    """Concrete ReviewController."""

    @classmethod
    def list(cls, renderer, tgt_project, tgt_package, info):
        """Lists requests for the given project and package.

        project and package might be None.

        """
        super(ReviewController, cls).list(renderer, tgt_project,
                                          tgt_package, info)

    @classmethod
    def change_review_state(cls, renderer, reqid, method, message, info,
                            supersede_id=None):
        """Changes the state of a review.

        method is the method which is called on the
        retrieved request object.
        If message is None $EDITOR is opened.

        """
        request = Request.find(reqid)
        review = cls._find_review(request, info)
        if review is not None:
            cls._change_request_state(renderer, request, method, message,
                                      info, supersede_id, review)

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
    def _find_review(cls, request, info):
        """Returns a review or None."""
        xpb = XPathBuilder(context_item=True)
        _, xp = cls._build_by_predicate(xpb, info, [])
        logger().debug(xp.tostring())
        reviews = request.findall(xp.tostring())
        if reviews:
            return reviews[0]
        return None

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
        xpb = XPathBuilder()
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
