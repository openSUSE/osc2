"""Class to manage package working copies."""

import os
import hashlib
import copy

from lxml.etree import XMLSyntaxError

from osc.source import File
from osc.source import Package as SourcePackage
from osc.util.xml import fromstring
from osc.wc.util import (wc_read_package, wc_read_project, wc_read_apiurl,
                         wc_init, wc_lock, wc_write_package, wc_write_project,
                         wc_write_apiurl, wc_write_files, wc_read_files,
                         missing_storepaths, WCInconsistentError)

def file_md5(filename):
    """Return the md5sum of filename's content.
    
    A ValueError is raised if filename does not exist or
    is no file.
    
    """
    if not os.path.isfile(filename):
        msg = "filename \"%s\" does not exist or is no file" % filename
        raise ValueError(msg)
    bufsize = 1024 * 1024
    md5 = hashlib.md5()
    with open(filename, 'rb') as f:
        data = f.read(bufsize)
        while data:
            md5.update(data)
            data = f.read(bufsize)
    return md5.hexdigest()


class FileUpdateInfo(object):
    """Contains information about an update.

    It provides the following information:
    - unchanged files (files which didn't change)
    - added files (files which exist on the server
      but not in the local working copy)
    - deleted files (files which don't exist on the
      server but are still present in the local wc)
    - modified files (files which were updated on the server)
    - conflicted files (local state '?' and a file with the
      same name exists on the server; local state '!' and file
      still exists on the server) - this has nothing todo with files
      with state 'C'
    - skipped files (files which shouldn't be checked out/updated)
    - data is a dict which maps a filename to its data object
      (which provides information like size, mtime, md5)

    """

    def __init__(self, unchanged, added, deleted, modified,
                 conflicted, skipped, data):
        super(FileUpdateInfo, self).__init__()
        self.unchanged = unchanged
        self.added = added
        self.deleted = deleted
        self.modified = modified
        self.conflicted = conflicted
        self.skipped = skipped
        self.data = data


class FileSkipHandler(object):
    """Used to skip certain files on update or checkout."""

    def skip(self, uinfo):
        """Calculate skipped and unskipped files.

        A 2-tuple (skip, unskip) is returned where skip and
        unskip are lists. All files in the skip list won't be
        checked out (and will be marked as skipped, state 'S').
        All files in the unskip list won't be skipped anymore.

        """
        raise NotImplementedError()


class Package(object):
    """Represents a package working copy."""

    def __init__(self, path, skip_handlers=[]):
        """Constructs a new package object.

        path is the path to the working copy.
        Raises a ValueError exception if path is
        no valid package working copy.
        Raises a WCInconsistentError if the wc's
        metadata is corrupt.

        Keyword arguments:
        skip_handlers -- list of FileSkipHandler objects
                         (default: [])

        """
        super(Package, self).__init__()
        (meta, xml_data, pkg_data) = self.wc_check(path)
        if meta or xml_data or pkg_data:
            raise WCInconsistentError(path, meta, xml_data, pkg_data)
        self.path = path
        self.apiurl = wc_read_apiurl(self.path)
        self.project = wc_read_project(self.path)
        self.name = wc_read_package(self.path)
        self.skip_handlers = skip_handlers
        with wc_lock(self.path) as lock:
            self._files = wc_read_files(self.path)

    def files(self):
        """Return list of filenames which are tracked."""
        filenames = []
        for fname in self._files:
            filenames.append(fname.get('name'))
        return filenames

    def status(self, filename):
        """Return the status of file filename.

        filename might be an arbitrary str (it doesn't have to
        be an "existing file")

        Status can be one of the following:
        ' ' -- unchanged
        'A' -- filename will be added
        'D' -- filename is marked for deletion
        'M' -- filename is modified
        '!' -- filename is missing (e.g. removed by non-osc command)
        'C' -- filename is conflicted (a merge failed)
        'S' -- filename is skipped
        '?' -- filename is not tracked

        """
        fname = os.path.join(self.path, filename)
        exists = os.path.exists(fname)
        entry = self._files.find(filename)
        if entry is None:
            return '?'
        st = entry.get('state')
        if st == 'D':
            return 'D'
        elif st != 'S' and not exists:
            return '!'
        elif st == ' ' and entry.get('md5') != file_md5(fname):
            return 'M'
        return st

    # XXX: we probably need a rev
    def _calculate_updateinfo(self):
        unchanged = []
        added = []
        deleted = []
        modified = []
        conflicted = []
        skipped = []
        spkg = SourcePackage(self.project, self.name)
        remote_files = spkg.list()
        local_files = self.files()
        data = {}
        for rfile in remote_files:
            rfname = rfile.get('name')
            data[rfname] = rfile
            if not rfname in local_files:
                if os.path.exists(os.path.join(self.path, rfname)):
                    conflicted.append(rfname)
                else:
                    added.append(rfname)
                continue
            st = self.status(rfname)
            lfile = self._files.find(rfname)
            if st in ('A', '!'):
                conflicted.append(rfname)
            elif st == 'S':
                skipped.append(rfname)
            elif lfile.get('md5') == rfile.get('md5'):
                unchanged.append(rfname)
            else:
                modified.append(rfname)
        remote_fnames = [f.get('name') for f in remote_files]
        for lfname in local_files:
            if not lfname in remote_fnames:
                data[lfname] = self._files.find(lfname)
                deleted.append(lfname)
        return FileUpdateInfo(unchanged, added, deleted, modified,
                              conflicted, skipped, data)

    def _calculate_skips(self, uinfo):
        """Calculate skip and unskip files.

        A ValueError is raised if a FileSkipHandler returns
        an invalid skip or unskip list.

        """
        def uinfo_remove(skip):
            uinfo.unchanged = [f for f in uinfo.unchanged if f != skip]
            uinfo.added = [f for f in uinfo.added if f != skip]
            uinfo.deleted = [f for f in uinfo.deleted if f != skip]
            uinfo.modified = [f for f in uinfo.modified if f != skip]
            uinfo.conflicted = [f for f in uinfo.conflicted if f != skip]
            uinfo.skipped = [f for f in uinfo.skipped if f != skip]

        for handler in self.skip_handlers:
            skips, unskips = handler.skip(copy.deepcopy(uinfo))
            inv = [f for f in skips if not f in uinfo.data.keys()]
            inv += [f for f in unskips if not f in uinfo.skipped]
            if inv:
                msg = "invalid skip/unskip files: %s" % ', '.join(inv)
                raise ValueError(msg)
            for skip in skips:
                uinfo_remove(skip)
                uinfo.skipped.append(skip)
            for unskip in unskips:
                uinfo.skipped.remove(unskip)
                if os.path.exists(os.path.join(self.path, unskip)):
                    uinfo.conflicted.append(unskip)
                else:
                    uinfo.added.append(unskip)

    @classmethod
    def wc_check(cls, path):
        """Check path is a consistent package working copy.

        A 3-tuple (missing, xml_data) is returned:
        - missing is a tuple which contains all missing storefiles
        - xml_data is a str which contains the invalid files xml str
          (if the xml is valid xml_data is the empty str (''))

        """
        meta = missing_storepaths(path, '_project', '_package',
                                  '_apiurl', '_files')
        dirs = missing_storepaths(path, 'data', dirs=True)
        missing = meta + dirs
        if '_files' in missing:
            return (missing, '', [])
        # check if _files file is a valid xml
        try:
            files = wc_read_files(path)
        except ValueError as e:
            return (missing, wc_read_files(path, raw=True), [])
        filenames = [f.get('name') for f in files
                     if not f.get('state') in ('A', 'S')]
        pkg_data = missing_storepaths(path, *filenames, data=True)
        return (missing, '', pkg_data)

    @staticmethod
    def init(path, project, package, apiurl, ext_storedir=None):
        """Initializes a directory as a package working copy.

        path is a path to a directory, project is the name
        of the project, package is the name of the package
        and apiurl is the apiurl.

        Keyword arguments:
        ext_storedir -- path to the storedir (default: None).
                        If not specified a "flat" package is created,
                        otherwise path/.osc is a symlink to storedir.

        """
        wc_init(path, ext_storedir=ext_storedir)
        wc_write_project(path, project)
        wc_write_package(path, package)
        wc_write_apiurl(path, apiurl)
        wc_write_files(path, '<directory/>')
        return Package(path)
