"""Class to manage package working copies."""

import os
import hashlib

from lxml.etree import XMLSyntaxError

from osc.source import File
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


class Package(object):
    """Represents a package working copy."""

    def __init__(self, path):
        """Constructs a new package object.

        path is the path to the working copy.
        Raises a ValueError exception if path is
        no valid package working copy.
        Raises a WCInconsistentError if the wc's
        metadata is corrupt.

        """
        super(Package, self).__init__()
        (meta, xml_data, pkg_data) = self.wc_check(path)
        if meta or xml_data or pkg_data:
            raise WCInconsistentError(path, meta, xml_data, pkg_data)
        self.path = path
        self.apiurl = wc_read_apiurl(self.path)
        self.project = wc_read_project(self.path)
        self.name = wc_read_package(self.path)
        with wc_lock(self.path) as lock:
            self._files = wc_read_files(self.path)

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
