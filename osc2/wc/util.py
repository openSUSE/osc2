"""Provides some utility functions to get data from a
working copy without constructing a Project or Package
instance.

"""

import os
import errno
import fcntl
import shutil
from tempfile import NamedTemporaryFile

from lxml import etree, objectify

from osc2.wc.base import AbstractTransactionState
from osc2.source import File, Directory, Linkinfo
from osc2.util.xml import fromstring
from osc2.util.xpath import XPathBuilder

__all__ = ['wc_is_project', 'wc_is_package', 'wc_read_project',
           'wc_read_package', 'wc_read_apiurl']

# maybe we should define this somewhere else
_STORE = '.osc'
_PKG_DATA = 'data'
_DIFF_DATA = 'diff'
_LOCK = 'wc.lock'
_VERSION = 2.0


class WCInconsistentError(Exception):
    """Represents an invalid working copy state"""

    def __init__(self, path, meta=(), xml_data=None, data=()):
        super(WCInconsistentError, self).__init__()
        self.path = path
        self.meta = meta
        self.xml_data = xml_data
        self.data = data


class WCFormatVersionError(Exception):
    """Represents an outdated wc version format"""

    def __init__(self, version):
        super(WCFormatVersionError, self).__init__()
        self.version = version


class WCLock(object):
    """Represents a lock on a working copy.

    "Coordinates" working copy locking.

    """

    def __init__(self, path):
        """Constructs a new WCLock object.

        path is the path to wc working copy.
        No lock is acquired (it must be explicitly locked
        via the lock() method).

        """
        super(WCLock, self).__init__()
        self._path = path
        self._fobj = None

    def has_lock(self):
        """Check if this object has lock on the working copy.

        Return True if it holds a lock otherwise False.

        """
        return self._fobj is not None

    def lock(self):
        """Acquire the lock on the working copy.

        This call might block if the working copy is already
        locked.
        A RuntimeError is raised if this object already
        has a lock on the working copy.

        """
        global _LOCK
        if self.has_lock():
            # a double lock is no problem at all but if it occurs
            # it smells like a programming/logic error (IMHO)
            raise RuntimeError('Double lock occured')
        lock = _storefile(self._path, _LOCK)
        f = open(lock, 'w')
        fcntl.lockf(f, fcntl.LOCK_EX)
        self._fobj = f

    def unlock(self):
        """Release the lock on the working copy.

        If the working copy wasn't locked before a
        RuntimeError is raised.

        """
        global _LOCK
        if not self.has_lock():
            raise RuntimeError('Attempting to release an unaquired lock.')
        fcntl.lockf(self._fobj, fcntl.LOCK_UN)
        self._fobj.close()
        self._fobj = None
        lock = _storefile(self._path, _LOCK)
        os.unlink(lock)

    def __enter__(self):
        self.lock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unlock()
        # don't suppress any exception
        return False


class AbstractEntryTracker(object):
    """Keeps track of entries.

    For instance an entry can be a file or a
    package.

    """

    def add(self, name, state):
        """Add a new entry to track.

        name is the name of the entry and
        state is the state.
        A ValueError is raised if name is already
        tracked.

        """
        raise NotImplementedError()

    def remove(self, name):
        """Remove a entry.

        name is the name of the entry.
        A ValueError is raised if name is
        not tracked.

        """
        raise NotImplementedError()

    def find(self, name):
        """Return the entry or None."""
        raise NotImplementedError()

    def set(self, name, new_state):
        """Set the state to new_state for entry name.

        A ValueError is raised if entry name is not
        tracked.

        """
        raise NotImplementedError()

    def merge(self, new_states, new_entries):
        """Merge current entries with new_entries and new_states.

        new_entries is a list (or list-like) object which contains
        all new entries. new_states is a entry to state mapping.
        A ValueError is raised if new_states and new_entries are
        inconsistent.

        """
        raise NotImplementedError()

    def write(self):
        """Write file."""
        raise NotImplementedError()

    def __iter__(self):
        """Iterate over entries."""
        raise NotImplementedError()

    @classmethod
    def check(self, path):
        """Check consistency of the backing file.

        path is the path to the working copy.
        Return True if it is consistent otherwise False.

        """
        raise NotImplementedError()


class XMLEntryTracker(AbstractEntryTracker):
    """Can be used for trackers which are backed up by a xml.

    Concrete subclasses must implement the filename classmethod.

    """

    def __init__(self, path, entry_tag):
        """Create a new XMLPackageTracker object.

        path is the path to the project working copy.
        A ValueError is raised if the file filename is
        corrupt/inconsistent.

        """
        super(XMLEntryTracker, self).__init__()
        filename = self.filename()
        if not self.check(path):
            raise ValueError("%s file is corrupt" % filename)
        self._path = path
        xml_data = _read_storefile(self._path, filename)
        # XXX: validation
        self._xml = self._fromstring(xml_data)
        self._tag = entry_tag

    def add(self, name, state):
        if self.find(name) is not None:
            raise ValueError("entry \"%s\" already exists" % name)
        elm = self._xml.makeelement(self._tag, name=name,
                                    state=state)
        self._xml.append(elm)

    def remove(self, name):
        elm = self.find(name)
        if elm is None:
            raise ValueError("entry \"%s\" does not exist" % name)
        self._xml.remove(elm)

    def find(self, name):
        xpb = XPathBuilder()
        xp = xpb.descendant(self._tag)[xpb.attr('name') == name]
        return self._xml.find(xp.tostring())

    def set(self, name, new_state):
        entry = self.find(name)
        if entry is None:
            raise ValueError("entry \"%s\" does not exist" % name)
        entry.set('state', new_state)

    def write(self):
        xml_data = etree.tostring(self._xml, pretty_print=True)
        _write_storefile(self._path, self.filename(), xml_data)

    def __iter__(self):
        return self._xml.iterfind(self._tag)

    @classmethod
    def filename(cls):
        raise NotImplementedError()

    @classmethod
    def _fromstring(cls, data):
        return fromstring(data)

    @classmethod
    def check(cls, path):
        try:
            data = _read_storefile(path, cls.filename())
            objectify.fromstring(data)
        except etree.XMLSyntaxError as e:
            return False
        return True


class XMLPackageTracker(XMLEntryTracker):
    """Represents the _packages file."""

    def __init__(self, path):
        super(XMLPackageTracker, self).__init__(path, 'package')

    @classmethod
    def filename(cls):
        return '_packages'

    def merge(self, new_states):
        for package, st in new_states.iteritems():
            if self.find(package) is None:
                self.add(package, st)
            else:
                self.set(package, st)
        delete = []
        for package in self._xml.findall(self._tag):
            name = package.get('name')
            if name not in new_states.keys():
                self.remove(name)
        self.write()


class XMLFileTracker(XMLEntryTracker):
    """Represents the _files file."""

    def __init__(self, path):
        super(XMLFileTracker, self).__init__(path, 'entry')

    def merge(self, new_states, new_entries):
        filenames = [entry.get('name') for entry in new_entries]
        # ignore locally added files
        st_filenames = [f for f, st in new_states.iteritems() if st != 'A']
        if (len(filenames) != len(st_filenames)
                or set(filenames) != set(st_filenames)):
            raise ValueError("data of new_states and new_entries mismatch")
        self._xml = new_entries
        for filename, st in new_states.iteritems():
            if st == 'A':
                # add files with state 'A' again
                self.add(filename, st)
            else:
                self.set(filename, st)
        self.write()

    def revision_data(self):
        """Return a dict which contains the revision data."""
        return {'rev': self._xml.get('rev'), 'srcmd5': self._xml.get('srcmd5')}

    def is_link(self):
        """Return True if package is a link."""
        return self._xml.find('linkinfo') is not None

    def __getattr__(self, name):
        return getattr(self._xml, name)

    @classmethod
    def _fromstring(cls, data):
        return fromstring(data, entry=File, directory=Directory,
                          linkinfo=Linkinfo)

    @classmethod
    def filename(cls):
        return '_files'


class XMLTransactionState(AbstractTransactionState):
    """Represents the state of a transaction"""

    def __init__(self, path, name, initial_state, info=None,
                 xml_data=None, **states):
        """Constructs a new XMLTransactionState object.

        Either info or xml_data has to be specified otherwise
        a ValueError is raised.

        Keyword arguments:
        info -- a FileUpdateInfo or FileCommitInfo object.
        xml_data -- xml string.
        states -- maps each wc file to its current state

        """
        global _PKG_DATA
        if ((info is not None and xml_data)
                or (info is None and xml_data is None)):
            raise ValueError('either specify info or xml_data')
        super(XMLTransactionState, self).__init__(path)
        trans_dir = _storefile(self._path, XMLTransactionState.DIR)
        data_dir = os.path.join(trans_dir, _PKG_DATA)
        self._location = data_dir
        if xml_data:
            self._xml = fromstring(xml_data, entry=File, directory=Directory,
                                   linkinfo=Linkinfo)
        else:
            self.cleanup()
            os.mkdir(trans_dir)
            os.mkdir(data_dir)
            xml_data = ('<transaction name="%s" state="%s"/>'
                        % (name, initial_state))
            self._xml = fromstring(xml_data, entry=File, directory=Directory,
                                   linkinfo=Linkinfo)
            self._xml.append(self._xml.makeelement('states'))
            self._add_states(states)
            self._xml.append(self._xml.makeelement('info'))
            for listname in self._listnames():
                self._add_list(listname, info)
            self._write()

    def _add_states(self, states):
        states_elm = self._xml.find('states')
        for entry, st in states.iteritems():
            elm = states_elm.makeelement('state', entry=entry, name=st)
            states_elm.append(elm)

    def _add_list(self, listname, info):
        info_elm = self._xml.find('info')
        child = info_elm.makeelement(listname)
        info_elm.append(child)
        for entry in getattr(info, listname):
            data = objectify.DataElement(entry)
            elm = child.makeelement('file')
            child.append(elm)
            getattr(child, 'file').__setitem__(-1, data)

    def _write(self):
        objectify.deannotate(self._xml)
        etree.cleanup_namespaces(self._xml)
        xml_data = etree.tostring(self._xml, pretty_print=True)
        _write_storefile(self._path, XMLTransactionState.FILENAME, xml_data)

    def processed(self, entry, new_state=None):
        # remove file from info
        info_elm = self._xml.find('info')
        elm = info_elm.find("//*[text() = '%s']" % entry)
        if elm is None:
            raise ValueError("file \"%s\" is not known" % entry)
        elm.getparent().remove(elm)
        # update states
        elm = self._xml.find("//state[@entry = '%s']" % entry)
        if elm is None:
            self._add_states({entry: new_state})
            elm = self._xml.find("//state[@entry = '%s']" % entry)
        if new_state is None:
            # remove node
            elm.getparent().remove(elm)
        else:
            elm.set('name', new_state)
        self._write()

    @property
    def location(self):
        return self._location

    @property
    def name(self):
        return self._xml.get('name')

    @property
    def state(self):
        return self._xml.get('state')

    @state.setter
    def state(self, new_state):
        self._xml.set('state', new_state)
        self._write()

    @property
    def entrystates(self):
        states = {}
        for st in self._xml.find('states').iterchildren():
            states[st.get('entry')] = st.get('name')
        return states

    def _lists(self):
        """Reconstructs info lists from xml data.

        Return a listname -> list mapping/dict.

        """
        lists = {}
        info_elm = self._xml.find('info')
        for listname in self._listnames():
            lists[listname] = []
            for entry in info_elm.find(listname).iterchildren():
                entry = entry.text
                lists[listname].append(entry)
        return lists

    def clear_info(self, entry):
        """Remove all entries but entry from info lists."""
        info_elm = self._xml.find('info')
        for listname in self._listnames():
            delete = []
            for entry_elm in info_elm.find(listname).iterchildren():
                if entry_elm.text != entry:
                    delete.append(entry_elm)
            for entry_elm in delete:
                entry_elm.getparent().remove(entry_elm)
        self._write()

    def cleanup(self):
        """Remove _transaction dir"""
        path = _storefile(self._path, XMLTransactionState.DIR)
        if os.path.exists(path):
            shutil.rmtree(path)

    @classmethod
    def read_state(cls, path):
        """Tries to read the update state.

        path is the path to the package working copy.
        If the update state file does not exist None
        is returned. Otherwise a XMLTransactionState subclass
        instance is returned.

        """
        ret = None
        try:
            data = _read_storefile(path, XMLTransactionState.FILENAME)
            ret = cls(path, xml_data=data)
        except ValueError as e:
            pass
        return ret


def _storedir(path):
    """Return the storedir path"""
    global _STORE
    return os.path.join(path, _STORE)


def _storefile(path, filename):
    """Return the path to the storefile"""
    return os.path.join(_storedir(path), filename)


def _has_storedir(path):
    """Test if path has a storedir (internal function)"""
    storedir = _storedir(path)
    return os.path.isdir(path) and os.path.isdir(storedir)


def missing_storepaths(path, *paths, **kwargs):
    """Test if the path/storedir contains all *paths

    All missing paths will be returned. If the returned
    list is empty all *path are available.

    Keyword arguments:
    dirs -- specifies if each path should be treated as a
            file or as a directory (default: False)
    data -- the paths are expected to exist in storedir/_PKG_DATA


    """
    global _PKG_DATA
    dirs = kwargs.get('dirs', False)
    data = kwargs.get('data', False)
    if not _has_storedir(path):
        return list(paths)
    storedir = _storedir(path)
    if data:
        storedir = _storefile(path, _PKG_DATA)
    missing = []
    for p in paths:
        storepath = os.path.join(storedir, p)
        if dirs:
            if not os.path.isdir(storepath):
                missing.append(p)
        else:
            if not os.path.isfile(storepath):
                missing.append(p)
    return missing


def _read_storefile(path, filename):
    """Read the content of the path/storedir/filename.

    If path/storedir/filename does not exist or is no file
    a ValueError is raised.
    Leading and trailing whitespaces, tabs etc. are stripped.

    """
    if missing_storepaths(path, filename):
        # file does not exist or is no file
        msg = "'%s' is no valid storefile" % filename
        raise ValueError(msg)
    storefile = _storefile(path, filename)
    return _read_file(storefile)


def _read_file(filename):
    """Reads the file specified via filename.

    The returned data is stripped.

    """
    with open(filename, 'r') as f:
        return f.read().strip()


def _write_storefile(path, filename, data):
    """Write a wc file.

    path is the path to the working copy, filename is the name
    of the storefile and data is the data which should be written.
    If data is not empty a trailing \\n character will be added.

    Raises a ValueError if path has no storedir.

    """
    if not _has_storedir(path):
        raise ValueError("path \"%s\" has no storedir" % path)
    fname = _storefile(path, filename)
    tmpfile = None
    try:
        tmpfile = NamedTemporaryFile(dir=_storedir(path), delete=False)
        tmpfile.write(data)
        if data:
            tmpfile.write('\n')
    finally:
        if tmpfile is not None:
            tmpfile.close()
            os.rename(tmpfile.name, fname)


def wc_lock(path):
    """Return a WCLock object.

    path is the path to the working copy.
    The only purpose of this method is to
    "beautify" the following code:

    with wc_lock(path) as lock:
        ...

    """
    return WCLock(path)


def wc_is_project(path):
    """Test if path is a project working copy."""
    missing = missing_storepaths(path, '_apiurl', '_project', '_package')
    if not missing:
        # it is a package dir
        return False
    elif len(missing) == 1 and '_package' in missing:
        return True
    return False


def wc_is_package(path):
    """Test if path is a package working copy."""
    return not missing_storepaths(path, '_apiurl', '_project', '_package')


def wc_read_project(path):
    """Return the name of the project.

    path is the path to the project or package working
    copy.
    If the storefile does not exist or is no file
    a ValueError is raised.

    """
    return _read_storefile(path, '_project')


def wc_read_packages(path, raw=False):
    """Return a XMLPackageTracker object.

    path is the path to the project working copy.
    If the storefile does not exist or is no file
    a ValueError is raised.

    Keyword arguments:
    raw -- if True return the raw _packages file data
           instead of an object (default: False)

    """
    if raw:
        return _read_storefile(path, XMLPackageTracker.filename())
    return XMLPackageTracker(path)


def wc_read_package(path):
    """Return the name of the package.

    path is the path to the package working copy.
    If the storefile does not exist or is no file
    a ValueError is raised.

    """
    return _read_storefile(path, '_package')


def wc_read_apiurl(path):
    """Return the apiurl for this working copy.

    path is the path to the project or package
    working copy.
    If the storefile does not exist or is no file
    a ValueError is raised.

    """
    return _read_storefile(path, '_apiurl')


def wc_read_files(path, raw=False):
    """Return a XMLFileTracker object.

    path is the path to the package working copy.
    If the storefile does not exist or is no file
    a ValueError is raised.

    Keyword arguments:
    raw -- if True return the raw _files file data
           instead of an object (default: False)

    """
    if raw:
        return _read_storefile(path, '_files')
    return XMLFileTracker(path)


def wc_write_apiurl(path, apiurl):
    """Write the _apiurl file.

    path is the path to the working copy and apiurl
    is the apiurl str.

    """
    _write_storefile(path, '_apiurl', apiurl)


def wc_write_project(path, project):
    """Write the _project file.

    path is the path to the working copy and project
    is the name of the project.

    """
    _write_storefile(path, '_project', project)


def wc_write_package(path, package):
    """Write the _package file.

    path is the path to the working copy and package
    is the name of the package.

    """
    _write_storefile(path, '_package', package)


def wc_write_packages(path, xml_data):
    """Write the _packages file.

    path is the path to the project working copy.

    """
    _write_storefile(path, '_packages', xml_data)


def wc_write_files(path, xml_data):
    """Write the _packages file.

    path is the path to the package working copy and
    xml_data is the xml str.

    """
    _write_storefile(path, '_files', xml_data)


def wc_write_version(path):
    """Write the working copy's format version.

    path is the path to the package working copy.

    """
    global _VERSION
    _write_storefile(path, '_version', str(_VERSION))


def wc_init(path, ext_storedir=None):
    """Initialize path as a working copy.

    path is the path to the new working copy. If path
    does not exist it will be created.
    Raises a ValueError if path is not readable/writable
    or if it is already a working copy or if ext_storedir
    is no dir or is not readable/writable. A WCFormatVersionError
    is raised, if ext_storedir is an already initialized storedir
    with an invalid/unsupported format.

    Keyword arguments:
    ext_storedir -- path to an external storedir (default: None).
                    If specified the path/.osc dir is a symlink to
                    ext_storedir.

    """
    global _PKG_DATA
    write_version = True
    if ext_storedir is not None:
        # some sanity checks
        if (not os.path.isdir(ext_storedir)
                or not os.access(ext_storedir, os.W_OK)):
            msg = ("ext_storedir \"%s\" is no dir or not writable"
                   % ext_storedir)
            raise ValueError(msg)
        if os.listdir(ext_storedir):
            _wc_verify_format(ext_storedir)
            # _version file is present and valid
            write_version = False

    storedir = _storedir(path)
    if os.path.exists(storedir) or os.path.islink(storedir):
        raise ValueError("path \"%s\" is already a working copy" % path)
    elif os.path.exists(path) and not os.path.isdir(path):
        raise ValueError("path \"%s\" already exists but is no dir" % path)
    elif not os.path.exists(path):
        try:
            os.makedirs(path)
        except OSError as e:
            if e.errno != errno.EACCES:
                raise
            raise ValueError("no permission to create path \"%s\"" % path)
    if not os.access(path, os.W_OK):
        msg = "no permission to create a storedir (path: \"%s\")" % path
        raise ValueError(msg)
    if ext_storedir is not None:
        # hmm should we check if path and ext_storedir have
        # a commonprefix?
        ext_storedir = os.path.relpath(ext_storedir, path)
        os.symlink(ext_storedir, storedir)
    else:
        os.mkdir(storedir)
    if write_version:
        wc_write_version(path)
    data_path = _storefile(path, _PKG_DATA)
    if not os.path.isdir(data_path):
        os.mkdir(data_path)


def wc_pkg_data_mkdir(path, new_dir):
    """Create a new package data dir called new_dir.

    Return the path to the dir.
    If new_dir already exists a ValueError is raised.
    Also raises a ValueError is path is no working copy
    or if the working copy misses a package data dir.

    """
    global _PKG_DATA
    if not _has_storedir(path):
        raise ValueError("path \"%s\" has no storedir" % path)
    if missing_storepaths(path, _PKG_DATA, dirs=True):
        raise ValueError("path \"%s\" has no pkg data dir" % path)
    data_path = _storefile(path, _PKG_DATA)
    ndir = os.path.join(data_path, new_dir)
    if os.path.exists(ndir):
        raise ValueError("directory already exists: %s" % ndir)
    os.mkdir(ndir)
    return ndir


def wc_pkg_data_filename(path, filename):
    """Return the filename to the store's _PKG_DATA/filename dir.

    path is the path to the working copy. filename is the
    name of the file.

    """
    global _PKG_DATA
    data_path = _storefile(path, _PKG_DATA)
    return os.path.join(data_path, filename)


def wc_diff_mkdir(path, revision):
    """Return the filename to the diff dir.

    If the directory does not exist it will be
    created.
    revision is the revision of the remote files.

    """
    global _DIFF_DATA
    diff_path = os.path.join(_storefile(path, _DIFF_DATA), revision)
    if not os.path.exists(diff_path):
        os.makedirs(diff_path)
    return diff_path


def wc_verify_format(path):
    """Check if the working copy format.

    path is the path to the working copy.
    A WCFormatVersion error if raised if the working
    copy format is out of date.

    """
    storedir = _storedir(path)
    _wc_verify_format(storedir)


def _wc_verify_format(storedir):
    """Verifies the wc format of the specified storedir.

    A WCFormatVersionError is raised if storedir has an
    invalid/unsupported wc version format.

    """
    global _VERSION
    filename = os.path.join(storedir, '_version')
    try:
        version_fmt = _read_file(filename)
        version_fmt = float(version_fmt)
    except IOError as e:
        if e.errno != errno.ENOENT:
            raise
        raise WCFormatVersionError(None)
    except ValueError as e:
        raise WCFormatVersionError(version_fmt)
    if version_fmt - _VERSION >= 1 or version_fmt - _VERSION <= -1:
        raise WCFormatVersionError(version_fmt)


def wc_parent(path):
    """Return the path of the wc which "contains" this wc.

    path is a path to a working copy or to a file in
    a working copy (the file does not have to exist).
    None is returned if the working copy has no
    parent working copy (for instance a project wc).

    """
    if _has_storedir(path):
        if wc_is_package(path) and os.path.islink(_storedir(path)):
            # link points to storedir/_PKG_DATA/name
            par_dir = os.path.join(_storedir(path), os.pardir, os.pardir,
                                   os.pardir)
            # use realpath to resolve the symlink
            return os.path.realpath(par_dir)
        return None
    par_dir = os.path.normpath(os.path.join(path, os.pardir))
    if _has_storedir(par_dir):
        return os.path.abspath(par_dir)
    return None
