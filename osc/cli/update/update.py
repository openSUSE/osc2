"""Provides classes and functions to work with a wc."""

import os

from osc.wc.base import TransactionListener
from osc.wc.project import Project
from osc.wc.util import wc_is_project, wc_is_package, wc_read_package


UPDATE_FILE_TEMPLATE = 'update/update_file.jinja2'
UPDATE_PACKAGE_TEMPLATE = 'update/update_package.jinja2'


class RendererUpdateTransactionListener(TransactionListener):
    """Informs transaction via the renderer."""

    def __init__(self, renderer, prj=None, pkg=None, *args, **kwargs):
        """Constructs a new RendererUpdateTransactionListener object.

        renderer is the renderer. *args and **kwargs
        are parameters for the superclass' __init__ method.

        Keyword arguments:
        prj -- an optional Project object (default: None)
        pkg -- an optional Package object (default: None)

        """
        super(RendererUpdateTransactionListener, self).__init__(*args,
                                                                **kwargs)
        self._renderer = renderer
        self._transactions = []
        self._project = ''
        self._package = ''

    def begin(self, name, uinfo):
        if name == 'prj_update':
            self._project = uinfo.name
        elif name == 'update':
            self._package = uinfo.name
        self._renderer.render_text("starting transaction: \"%s\"" % name)

    def finished(self, name, aborted=False, abort_reason=''):
        if aborted:
            text = "aborted transaction: \"%s\" - %s" % (name, abort_reason)
            self._renderer.render_text(text)
        else:
            self._renderer.render_text("finished transaction: \"%s\"" % name)
        if name == 'prj_update':
            self._project = ''
        elif name == 'update':
            self._package = ''

    def transfer(self, transfer_type, filename):
        pass

    def processed(self, entity, new_state, old_state):
        global UPDATE_FILE_TEMPLATE
        if self._package:
            self._renderer.render(UPDATE_FILE_TEMPLATE, filename=entity,
                                  new_state=new_state, old_state=old_state,
                                  package=self._package)
        elif self._project:
            self._renderer.render(UPDATE_PACKAGE_TEMPLATE, package=entity,
                                  new_state=new_state, old_state=old_state,
                                  project=self._project)


class WCUpdateController(object):
    """Can be used to update/checkout a project or package."""

    def __init__(self, path=None):
        """Constructs a new WCUpdateController instance.

        Keyword arguments:
        path -- the base path where all operations should be executed
                (default: os.getcwd())

        """
        super(WCUpdateController, self).__init__()
        self._renderer = None
        self._path = path
        if path is None:
            self._path = os.path.join(os.getcwd())

    def _path_join(self, path):
        """Joins self._path with path"""
        return os.path.join(self._path, path)

    def checkout(self, renderer, project, package, info):
        """Checks out a project or a package."""
        self._renderer = renderer
        if package is not None:
            self._checkout_package(project, package, info)
        elif project is not None:
            self._checkout_project(project, info)

    def update(self, renderer, path, info):
        """Updates a project or a list of packages"""
        self._renderer = renderer
        if path is None:
            path = os.curdir
        if wc_is_project(path):
            self._update_project(path, info)
        elif wc_is_package(path):
            par_dir = os.path.join(path, os.pardir)
            if wc_is_project(par_dir):
                self._update_project(par_dir, info, wc_read_package(path))
            else:
                self._update_package(path, info)
        else:
            par_dir = os.path.abspath(os.path.join(path, os.pardir))
            if wc_is_project(par_dir):
                self._update_project(par_dir, info, path)

    def _update_project(self, path, info, *packages):
        """Updates a project wc."""
        tl = RendererUpdateTransactionListener(self._renderer)
        prj = Project(path, transaction_listener=[tl])
        query = self._build_query(info)
        prj.update(*packages, **query)

    def _update_package(self, path, info):
        """Updates a package wc."""
        tl = RendererUpdateTransactionListener(self._renderer)
        pkg = Package(path, transaction_listener=[tl])
        query = self._build_query(info)
        pkg.update(**query)

    def _checkout_package(self, project, package, info):
        path = self._path_join(project)
        tl = RendererUpdateTransactionListener(self._renderer)
        if wc_is_project(path):
            prj = Project(path, transaction_listener=[tl])
        else:
            prj = Project.init(path, project, info.apiurl,
                               transaction_listener=[tl])
        query = self._build_query(info)
        prj.update(package, **query)

    def _checkout_project(self, project, info):
        """Checks out the project project."""
        path = self._path_join(project)
        tl = RendererUpdateTransactionListener(self._renderer)
        prj = Project.init(path, project, info.apiurl,
                           transaction_listener=[tl])
        query = self._build_query(info)
        prj.update(**query)

    def _build_query(self, info):
        """Builds query dict."""
        query = {}
        if not info.unexpand:
            query['expand'] = '1'
        if info.revision is not None:
            query['revision'] = info.revision
        return query
