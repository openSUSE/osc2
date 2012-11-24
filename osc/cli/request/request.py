"""Provides various functions for the "request" command."""

import logging

from osc.httprequest import HTTPError
from osc.util.xpath import XPathBuilder
from osc.remote import Request
from osc.search import find_request
from osc.cli.util.env import run_pager, edit_message
from osc.cli.util.shell import AbstractShell, ShellSyntaxError


LIST_TEMPLATE = 'request/request_list.jinja2'
SHOW_TEMPLATE = 'request/request_show.jinja2'


def logger():
    """Returns a logging.Logger object."""
    return logging.getLogger(__name__)


class AbstractRequestController(object):
    """Abstract base class for working with requests.

    This class is pretty stateless that's why the methods are
    implemented as classmethods. It's main goal is to reuse
    code for Request and Reviews.

    """

    @classmethod
    def list(cls, renderer, project, package, info):
        """Lists requests for the given project and package.

        project and package might be None.

        """
        global LIST_TEMPLATE
        collection = cls._find_requests(project, package, info)
        collection.sort(reverse=True)
        if info.interactive:
            cls.shell(renderer, info.shell_cls, collection)
            return
        for request in collection:
            renderer.render(LIST_TEMPLATE, request=request)

    @classmethod
    def show(cls, renderer, reqid, info):
        """Shows the request specified by reqid."""
        global SHOW_TEMPLATE
        request = Request.find(reqid)
        if info.interactive:
            cls.shell(renderer, info.shell_cls, [request])
            return
        renderer.render(SHOW_TEMPLATE, request=request)
        if info.diff:
            cls.diff(request)

    @classmethod
    def shell(cls, renderer, shell_cls, requests):
        """Starts an interactive request shell."""
        sh = shell_cls(renderer)
        sh.run(requests)

    @classmethod
    def diff(cls, request):
        """Displays the diff for the request request."""
        run_pager(request.diff())

    @classmethod
    def _change_request_state(cls, renderer, request, method, message, info,
                              supersede_id=None, review=None):
        """Changes the state of the request or the review.

        method is the method which is called on the
        retrieved request object.
        If message is None $EDITOR is opened.

        """
        global SHOW_TEMPLATE
        meth = getattr(request, method)
        if message is None:
            message = edit_message()
        kwargs = {}
        if supersede_id is not None:
            kwargs['reqid'] = supersede_id
        if review is not None:
            kwargs['review'] = review
        if info.force:
            kwargs['force'] = '1'
        meth(comment=message, **kwargs)
        renderer.render(SHOW_TEMPLATE, request=request)

    @classmethod
    def _find_requests(cls, project, package, info):
        """Returns a request collection based on some criteria."""
        raise NotImplementedError()


class RequestController(AbstractRequestController):
    """Concrete RequestController."""

    @classmethod
    def change_request_state(cls, renderer, reqid, method, message, info,
                             supersede_id=None):
        """Changes the state of the request id reqid.

        method is the method which is called on the
        retrieved request object.
        If message is None $EDITOR is opened.

        """
        request = Request.find(reqid)
        cls._change_request_state(renderer, request, method, message, info,
                                  supersede_id)

    @classmethod
    def create(cls, renderer, submit, changedevel, role, grouprole, delete,
               info):
        """Creates a new request."""
        global SHOW_TEMPLATE
        request = Request()
        message = info.message
        if message is None:
            message = edit_message()
        cls._create_submit_actions(request, submit)
        cls._create_changedevel_actions(request, changedevel)
        cls._create_role_actions(request, role)
        cls._create_grouprole_actions(request, grouprole)
        cls._create_delete_actions(request, delete)
        request.description = message
        request.store()
        renderer.render(SHOW_TEMPLATE, request=request)

    @classmethod
    def _create_submit_actions(cls, request, submit):
        """Creates a new submit actions for the request request."""
        for info in submit:
            action = request.add_action(type='submit')
            action.add_source(project=info.src_project,
                              package=info.src_package, rev=info.rev)
            action.add_target(project=info.tgt_project,
                              package=info.tgt_package)

    @classmethod
    def _create_changedevel_actions(cls, request, changedevel):
        """Creates a new change_devel actions for the request request."""
        for info in changedevel:
            action = request.add_action(type='change_devel')
            action.add_source(project=info.src_project,
                              package=info.src_package)
            action.add_target(project=info.tgt_project,
                              package=info.tgt_package)

    @classmethod
    def _create_role_actions(cls, request, role):
        """Creates a new role actions for the request request."""
        for info in role:
            action = request.add_action(type='add_role')
            action.add_target(project=info.project, package=info.package)
            action.add_person(name=info.user, role=info.role)

    @classmethod
    def _create_grouprole_actions(cls, request, grouprole):
        """Creates a new grouprole actions for the request request."""
        for info in grouprole:
            action = request.add_action(type='add_role')
            action.add_target(project=info.project, package=info.package)
            action.add_group(name=info.group, role=info.role)

    @classmethod
    def _create_delete_actions(cls, request, delete):
        """Creates a new delete actions for the request request."""
        for info in delete:
            action = request.add_action(type='delete')
            action.add_target(project=info.project, package=info.package)

    @classmethod
    def _find_requests(cls, project, package, info):
        """Returns a collection of requests."""
        xpb = XPathBuilder(is_relative=True)
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


class AbstractRequestShell(AbstractShell):
    """Represents an abstract request shell."""

    def __init__(self, *args, **kwargs):
        """Constructs a new AbstractRequestShell object.

        *args and **kwargs are passed to the base class'
        __init__ method.

        """
        super(AbstractRequestShell, self).__init__(*args, **kwargs)
        self._request = None

    def _augment_info(self, info):
        """Adds the current request to the info object."""
        super(AbstractRequestShell, self)._augment_info(info)
        info.set('request', self._request)

    def run(self, requests):
        """Run the shell.

        requests is a list of Request objects.

        """
        while requests:
            self._request = requests.pop(0)
            self.render(SHOW_TEMPLATE, request=self._request)
            next_req = False
            while not next_req:
                try:
                    inp = self.prompt()
                    next_req = self._execute(self._request, inp)
                except SystemExit:
                    # argparse automatically exits when the
                    # help is requested
                    pass
                except ShellSyntaxError as e:
                    self._renderer.render_text(str(e))
                except KeyboardInterrupt as e:
                    msg = "Press to ctrl-D to exit"
                    self._renderer.render_text(msg)
                except HTTPError as e:
                    msg = "Error %s: %s" % (e.code, e.url)
                    self._renderer.render_text(msg)
            self.clear()


class RequestShellController(AbstractRequestController):
    """Concrete request controller for the request shell."""

    def __init__(self):
        """Constructs a new ShellRequestController object."""
        self.stats = {}

    def change_request_state(self, shell, request, method, message, info,
                             supersede_id=None):
        """Changes the state of the request req.

        method is the method which is called on the
        retrieved request object.
        If message is None $EDITOR is opened.

        """
        self._change_request_state(shell, request, method, message, info,
                                   supersede_id)
        self.stats.setdefault(method, []).append(req)
        return True

    def skip(self):
        """Skips the current request."""
        return True
