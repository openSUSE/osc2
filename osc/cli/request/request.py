"""Provides various functions for the "request" command."""

import logging

from osc.util.xpath import XPathBuilder
from osc.remote import Request
from osc.search import find_request
from osc.cli.util.env import run_pager, edit_message


LIST_TEMPLATE = 'request/request_list.jinja2'
SHOW_TEMPLATE = 'request/request_show.jinja2'


def logger():
    """Returns a logging.Logger object."""
    return logging.getLogger(__name__)


def list(renderer, project, package, info):
    """Lists requests for the given project and package.

    project and package might be None.

    """
    global LIST_TEMPLATE
    collection = _find_requests(project, package, info)
    collection.sort(reverse=True)
    for request in collection:
        renderer.render(LIST_TEMPLATE, request=request)


def show(renderer, reqid, info):
    """Shows the request specified by reqid."""
    global SHOW_TEMPLATE
    request = Request.find(reqid)
    renderer.render(SHOW_TEMPLATE, request=request)
    if info.diff:
        run_pager(request.diff())


def change_request_state(renderer, reqid, method, message, info,
                         supersede_id=None):
    """Changes the state of the request id reqid.

    method is the method which is called on the
    retrieved request object.
    If message is None $EDITOR is opened.

    """
    global SHOW_TEMPLATE
    request = Request.find(reqid)
    meth = getattr(request, method)
    if message is None:
        message = edit_message()
    kwargs = {}
    if supersede_id is not None:
        kwargs['reqid'] = supersede_id
    meth(comment=message, **kwargs)
    renderer.render(SHOW_TEMPLATE, request=request)


def create(renderer, submit, changedevel, role, grouprole, delete, info):
    """Creates a new request."""
    global SHOW_TEMPLATE
    request = Request()
    message = info.message
    if message is None:
        message = edit_message()
    _create_submit_actions(request, submit)
    _create_changedevel_actions(request, changedevel)
    _create_role_actions(request, role)
    _create_grouprole_actions(request, grouprole)
    _create_delete_actions(request, delete)
    request.description = message
    request.store()
    renderer.render(SHOW_TEMPLATE, request=request)


def _create_submit_actions(request, submit):
    """Creates a new submit actions for the request request."""
    for info in submit:
        action = request.add_action(type='submit')
        action.add_source(project=info.src_project, package=info.src_package,
                          rev=info.rev)
        action.add_target(project=info.tgt_project, package=info.tgt_package)


def _create_changedevel_actions(request, changedevel):
    """Creates a new change_devel actions for the request request."""
    for info in changedevel:
        action = request.add_action(type='change_devel')
        action.add_source(project=info.src_project, package=info.src_package)
        action.add_target(project=info.tgt_project, package=info.tgt_package)


def _create_role_actions(request, role):
    """Creates a new role actions for the request request."""
    for info in role:
        action = request.add_action(type='add_role')
        action.add_target(project=info.project, package=info.package)
        action.add_person(name=info.user, role=info.role)


def _create_grouprole_actions(request, grouprole):
    """Creates a new grouprole actions for the request request."""
    for info in grouprole:
        action = request.add_action(type='add_role')
        action.add_target(project=info.project, package=info.package)
        action.add_group(name=info.group, role=info.role)


def _create_delete_actions(request, delete):
    """Creates a new delete actions for the request request."""
    for info in delete:
        action = request.add_action(type='delete')
        action.add_target(project=info.project, package=info.package)


def _find_requests(project, package, info):
    """Returns a collection of requests."""
    todo = {}
    xpb = XPathBuilder()
    pred = xpb.dummy()
    xp = xpb.dummy()
    # state has at least one element
    for state in info.state:
        xp = xp | xpb.state.attr('name') == state
    xp = xp.parenthesize()
    if info.user is not None:
        xp = xp & ((xpb.state.attr('who') == info.user)
                   | (xpb.history.attr('who') == info.user)).parenthesize()
    if project is not None:
        tmp = ((xpb.action.target.attr('project') == project)
               | (xpb.action.source.attr('project') == project))
        xp = xp & tmp.parenthesize()
    if package is not None:
        tmp = ((xpb.action.target.attr('package') == package)
               | (xpb.action.source.attr('package') == package))
        xp = xp & tmp.parenthesize()
    logger().debug(xp.tostring())
    res = find_request(xp=xp, apiurl=info.apiurl)
    collection = [r for r in res]
    return collection
