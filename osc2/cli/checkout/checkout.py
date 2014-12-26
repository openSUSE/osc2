"""Provides a class to perform checkout operations"""

import os
from collections import Sequence

from osc2.wc.project import Project
from osc2.wc.util import wc_is_project
from osc2.cli.cli import at_most
from osc2.cli.update.update import (WCUpdateController,
                                    RendererUpdateTransactionListener)


class WCCheckoutController(WCUpdateController):
    """Provides methods to checkout a project, package or file.

    In this context checkout means the following:
    - checking out a project or package from the api
    - revert all local modifications of a project or package or file

    """
    def __init__(self, path=None):
        """Constructs a new WCUpdateController instance.

        Keyword arguments:
        path -- the base path where all operations should be executed
                (default: os.getcwd())

        """
        super(WCCheckoutController, self).__init__()
        self._path = path
        if self._path is None:
            self._path = os.getcwd()

    def _path_join(self, path):
        """Joins self._path with path"""
        return os.path.join(self._path, path)

    @staticmethod
    def _inspect_path(path):
        checkout_pkg = False
        wc = None
        todo = []
        if path.filename is not None:
            wc = path.package_obj()
            todo.append(path.filename)
        elif path.package is not None:
            if path.project:
                wc = path.project_obj()
                todo.append(path.package)
                checkout_pkg = wc._status(path.package) == '?'
            else:
                wc = path.package_obj()
        elif path.project is not None:
            wc = path.project_obj()
        else:
            # should never happen
            msg = 'invalid path: project, package, filename None'
            raise ValueError(msg)
        return wc, todo, checkout_pkg

    def checkout(self, renderer, info):
        """Checks out a project, package or file."""
        self._renderer = renderer
        if info.get('path') is not None:
            paths = info.path
            if not isinstance(paths, Sequence):
                paths = [paths]
            for path in paths:
                wc, todo, checkout_pkg = self._inspect_path(path)
                if checkout_pkg:
                    self._checkout_package(wc.apiurl, wc.path, todo[0], info)
                else:
                    wc.revert(*todo)
        if info.get('package') is not None:
            self._checkout_package(info.apiurl, info.project, info.package,
                                   info)
        elif info.get('project') is not None:
            self._checkout_project(info)

    @at_most(1, 'package', msg="At most one remote argument allowed.")
    def _checkout_package(self, apiurl, project, package, info):
        tl = RendererUpdateTransactionListener(self._renderer)
        path = self._path_join(project)
        if wc_is_project(path):
            prj = Project(path, transaction_listener=[tl])
        else:
            prj = Project.init(path, project, apiurl,
                               transaction_listener=[tl])
        self._update_project(prj, info, package)

    @at_most(1, 'project', msg="At most one remote argument allowed.")
    def _checkout_project(self, info):
        """Checks out the project project."""
        path = self._path_join(info.project)
        tl = RendererUpdateTransactionListener(self._renderer)
        prj = Project.init(path, info.project, info.apiurl,
                           transaction_listener=[tl])
        self._update_project(prj, info)
