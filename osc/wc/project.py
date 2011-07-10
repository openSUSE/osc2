"""Class to manage a project working copy."""

import os
import fcntl

from lxml import objectify
from lxml.etree import XMLSyntaxError

from osc.wc.util import (wc_read_project, wc_read_apiurl, wc_read_packages,
                         wc_init, wc_write_apiurl, wc_write_project,
                         wc_write_packages, missing_storepaths, wc_lock,
                         WCInconsistentError)
from osc.source import Project as SourceProject

class UpdateInfo(object):
    """Contains information about an update.

    It provides the following information:
    - added packages (packages which exist on the server
      but not in the local working copy)
    - deleted packages (packages which don't exist on the
      server but are still present in the local wc)
    - conflicted packages (local state '?' and a package with the
      same name exists on the server; local state '!' and package
      still exists on the server)
    - candidate packages (packages which exist on the server
      and in the local wc)

    """

    def __init__(self, candidates, added, deleted, conflicted):
        self.candidates = candidates
        self.added = added
        self.deleted = deleted
        self.conflicted = conflicted

class Project(object):
    """Represents a project working copy."""

    PACKAGES_SCHEMA = ''

    def __init__(self, path):
        """Constructs a new project object.

        path is the path to the working copy.
        Raises a ValueError exception if path is
        no valid project working copy.
        Raises a WCInconsistentError if the wc's
        metadata is corrupt.

        """
        super(Project, self).__init__()
        (meta, xml_data) = self.wc_check(path)
        if meta or xml_data:
            raise WCInconsistentError(path, meta, xml_data)
        self.path = path
        self.apiurl = wc_read_apiurl(path)
        self.name = wc_read_project(path)
        with wc_lock(self.path) as lock:
            data = wc_read_packages(self.path)
            self._packages = objectify.fromstring(data)

    def packages(self, obj=False):
        """Return list of all package names"""
        pkgs = []
        for p in self._packages.iterfind('package'):
            pkgs.append(p.get('name'))
        return pkgs

    def _xml_pkg_node(self, pkg):
        """Return the package element for package pkg.

        If pkg does not exist in the xml None is returned.

        """
        xpath = "//package[@name='%s']" % pkg
        return self._packages.find(xpath)

    def _status(self, pkg):
        """Return the status of package pkg.

        pkg might be an arbitrary str (it doesn't have to
        be an "existing package")

        Status can be one of the following:
        ' ' -- unchanged
        'A' -- pkg will be added to the project
        'D' -- pkg is marked for deletion
        '!' -- pkg is missing (e.g. removed by non-osc command)
        '?' -- pkg is not tracked

        """
        pkg_dir = os.path.join(self.path, pkg)
        exists = os.path.exists(pkg_dir)
        node = self._xml_pkg_node(pkg)
        if node is None:
            return '?'
        st = node.get('state')
        if not exists and st != 'D':
            return '!'
        return st

    def _calculate_updateinfo(self):
        added = []
        deleted = []
        candidates = []
        conflicted = []
        sprj = SourceProject(self.name)
        remote_pkgs = [pkg.name for pkg in sprj.list()]
        local_pkgs = self.packages()
        for pkg in remote_pkgs:
            if pkg in local_pkgs:
                candidates.append(pkg)
            else:
                added.append(pkg)
        for pkg in local_pkgs:
            st = self._status(pkg)
            if st != 'A' and not pkg in remote_pkgs:
                deleted.append(pkg)
        # check for conflicts
        for pkg in candidates[:]:
            if self._status(pkg) in ('A', '!'):
                conflicted.append(pkg)
                candidates.remove(pkg)
        for pkg in added[:]:
            path = os.path.join(self.path, pkg)
            st = self._status(pkg)
            if st == '?' and os.path.exists(path):
                conflicted.append(pkg)
                added.remove(pkg)
        return UpdateInfo(candidates, added, deleted, conflicted)

    @classmethod
    def wc_check(cls, path):
        """Check path is a consistent project working copy.

        A 2-tuple (missing, xml_data) is returned:
        - missing is a tuple which contains all missing storefiles
        - xml_data is a str which contains the invalid packages xml str
          (if the xml is valid xml_data is the empty str (''))

        """
        meta = missing_storepaths(path, '_project', '_apiurl',
                                  '_packages')
        dirs = missing_storepaths(path, 'data', dirs=True)
        missing = meta + dirs
        if '_packages' in missing:
            return (missing, '')
        # check if _packages file is a valid xml
        try:
            data = wc_read_packages(path)
            objectify.fromstring(data)
        except XMLSyntaxError as e:
            return (missing, data)
        return (missing, '')

    @staticmethod
    def init(path, project, apiurl):
        """Initializes a directory as a project working copy.

        path is a path to a directory, project is the name
        of the project and apiurl is the apiurl.

        """
        wc_init(path)
        wc_write_project(path, project)
        wc_write_apiurl(path, apiurl)
        wc_write_packages(path, '<packages/>')
        return Project(path)
