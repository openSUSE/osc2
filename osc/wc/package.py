"""Class to manage package working copies."""

import os
import hashlib
import copy
import shutil
import subprocess

from lxml import etree, objectify

from osc.source import File, Directory
from osc.source import Package as SourcePackage
from osc.util.xml import fromstring
from osc.util.io import copy_file
from osc.wc.util import (wc_read_package, wc_read_project, wc_read_apiurl,
                         wc_init, wc_lock, wc_write_package, wc_write_project,
                         wc_write_apiurl, wc_write_files, wc_read_files,
                         missing_storepaths, WCInconsistentError,
                         _storefile, _PKG_DATA, _read_storefile,
                         _write_storefile, wc_pkg_data_filename)


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


def is_binaryfile(filename):
    """Checks if filename is a binary file.

    filename is the path to the file.
    Return True if it is binary (that is the first 4096
    bytes contain a '\0' character). Otherwise False is
    returned.

    """
    with open(filename, 'rb') as f:
        data = f.read(4096)
    return '\0' in data


class FileConflictError(Exception):
    """Exception raises if an operation can't be executed due to conflicts."""

    def __init__(self, conflicts):
        """Construct a new FileConflictError object.

        conflicts is a list of conflicted files.

        """
        super(FileConflictError, self).__init__()
        self.conflicts = conflicts


class TransactionListener(object):
    """Notify a client about a transaction.

    This way clients can examine the current status of
    update and commit.

    """
    def begin(self, name, uinfo):
        """Signal the beginning of a transaction.

        name is the name of the transaction.
        uinfo is an instance of class UpdateInfo or
        FileUpdateInfo.
        If this method returns False the transaction
        won't be executed.

        """
        raise NotImplementedError()

    def finished(self, name, aborted=False, abort_reason=''):
        """Transaction finished.

        name is the name of the transaction.
        aborted indicates if the transaction was
        aborted by some listener.
        abort_reason might contain a str which
        describes why the transaction was aborted.

        """
        raise NotImplementedError()

    def download(self, filename):
        """Downloading filename."""
        raise NotImplementedError()

    def processed(self, filename, new_state):
        """Operation was performed on file filename.

        new_state is the new state of filename.
        new_state == None indicates that filename was
        removed from the wc.

        """
        raise NotImplementedError()


class TransactionNotifier(object):
    """Notify all transaction listeners."""

    def __init__(self, listeners):
        super(TransactionNotifier, self).__init__()
        self._listeners = listeners

    def _notify(self, method, *args, **kwargs):
        rets = []
        for listener in self._listeners:
            meth = getattr(listener, method)
            rets.append(meth(*args, **kwargs))
        return rets

    def begin(self, *args, **kwargs):
        """Return True if the transaction can start - otherwise False."""
        rets = self._notify('begin', *args, **kwargs)
        falses = [ret for ret in rets if ret is False]
        return len(falses) == 0

    def finished(self, *args, **kwargs):
        self._notify('finished', *args, **kwargs)

    def download(self, *args, **kwargs):
        self._notify('download', *args, **kwargs)

    def processed(self, *args, **kwargs):
        self._notify('processed', *args, **kwargs)


class Merge(object):
    """Encapsulates file merge logic."""
    SUCCESS = 0
    CONFLICT = 1
    BINARY = 2
    FAILURE = 3

    def merge(self, my_filename, old_filename, your_filename, out_filename):
        """Perform a file merge.

        Return values:
        SUCCESS -- merge was successfull
        CONFLICTS -- some conflicts occurred
        BINARY -- the file is a binary file and cannot be merged
        FAILURE -- some internal failure occurred

        """
        if is_binaryfile(my_filename) or is_binaryfile(your_filename):
            if file_md5(my_filename) == file_md5(old_filename):
                copy_file(your_filename, out_filename)
                return Merge.SUCCESS
            return Merge.BINARY
        merge_cmd = "diff3 -m -E %s %s %s > %s" % (my_filename, old_filename,
                                                   your_filename, out_filename)
        ret = subprocess.call(merge_cmd, shell=True)
        if ret == 0:
            return Merge.SUCCESS
        elif ret == 1:
            return Merge.CONFLICT
        else:
            return Merge.FAILURE


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
      same name exists on the server) - this has nothing todo
      with files with state 'C'
    - skipped files (files which shouldn't be checked out/updated)
    - data is a dict which maps a filename to its data object
      (which provides information like size, mtime, md5)
    - remote_xml is the package's remote filelist.

    """

    def __init__(self, unchanged, added, deleted, modified,
                 conflicted, skipped, data, remote_xml):
        super(FileUpdateInfo, self).__init__()
        self.unchanged = unchanged
        self.added = added
        self.deleted = deleted
        self.modified = modified
        self.conflicted = conflicted
        self.skipped = skipped
        self.data = data
        self.remote_xml = remote_xml
        self.rev = remote_xml.get('rev')
        self.srcmd5 = remote_xml.get('srcmd5')

    def __str__(self):
        listnames = ('unchanged', 'added', 'deleted', 'modified',
                     'conflicted', 'skipped')
        ret = []
        for listname in listnames:
            data = ', '.join(getattr(self, listname))
            ret.append('%s: %s' % (listname, data))
        return '\n'.join(ret)


class FileCommitInfo(object):
    """Contains information about a commit.

    It provides the following information:
    - unchanged files (files which weren't changed and will be kept)
    - added files (files which will be added to the package)
    - deleted files (files which will be deleted from the package)
    - modified files (files which were changed)
    - conflicted files (local state '!' and the file is explicitly specified
      for the commit)

    """

    def __init__(self, unchanged, added, deleted, modified, conflicted):
        super(FileCommitInfo, self).__init__()
        self.unchanged = unchanged
        self.added = added
        self.deleted = deleted
        self.modified = modified
        self.conflicted = conflicted


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


class PackageUpdateState(object):
    """Represents the state of a package update"""
    STATE_DOWNLOADING = '1'
    STATE_UPDATING = '2'
    FILENAME = os.path.join('_update', 'state')

    def __init__(self, path, uinfo=None, xml_data=None, **states):
        """Constructs a new PackageUpdateState object.

        path is the path to the package working copy.
        Either uinfo or xml_data has to be specified otherwise
        a ValueError is raised.

        Keyword arguments:
        uinfo -- a FileUpdateInfo object.
        xml_data -- xml string.
        states -- maps each wc file to its current state

        """
        if ((uinfo is not None and xml_data)
            or (uinfo is None and xml_data is None)):
            raise ValueError('either specify uinfo or xml_data')
        super(PackageUpdateState, self).__init__()
        self._path = path
        global _PKG_DATA
        update_dir = _storefile(self._path, '_update')
        data_dir = os.path.join(update_dir, _PKG_DATA)
        self.location = data_dir
        if xml_data:
            self._xml = fromstring(xml_data, entry=File, directory=Directory)
        else:
            self.cleanup()
            os.mkdir(update_dir)
            os.mkdir(data_dir)
            xml_data = ('<update state="%s"/>'
                % PackageUpdateState.STATE_DOWNLOADING)
            self._xml = fromstring(xml_data)
            self._xml.append(self._xml.makeelement('states'))
            self._add_states(states)
            self._xml.append(self._xml.makeelement('updateinfo'))
            self._xml.append(uinfo.remote_xml)
            listnames = ('unchanged', 'added', 'deleted', 'modified',
                         'conflicted', 'skipped')
            for listname in listnames:
                self._add_list(listname, uinfo)
            self._write()

    def _add_states(self, states):
        states_elm = self._xml.find('states')
        for filename, st in states.iteritems():
            elm = states_elm.makeelement('state', filename=filename, name=st)
            states_elm.append(elm)

    def _add_list(self, listname, uinfo):
        uinfo_elm = self._xml.find('updateinfo')
        child = uinfo_elm.makeelement(listname)
        uinfo_elm.append(child)
        for filename in getattr(uinfo, listname):
            data = objectify.DataElement(filename)
            elm = child.makeelement('file')
            child.append(elm)
            getattr(child, 'file').__setitem__(-1, data)

    def _write(self):
        objectify.deannotate(self._xml)
        etree.cleanup_namespaces(self._xml)
        xml_data = etree.tostring(self._xml, pretty_print=True)
        _write_storefile(self._path, PackageUpdateState.FILENAME, xml_data)

    def processed(self, filename, new_state=None):
        # remove file from updateinfo
        uinfo_elm = self._xml.find('updateinfo')
        elm = uinfo_elm.find("//*[text() = '%s']" % filename)
        if elm is None:
            raise ValueError("file \"%s\" is not known" % filename)
        elm.getparent().remove(elm)
        # update states
        elm = self._xml.find("//state[@filename = '%s']" % filename)
        if elm is None:
            self._add_states({filename: new_state})
            elm = self._xml.find("//state[@filename = '%s']" % filename)
        if new_state is None:
            # remove node
            elm.getparent().remove(elm)
        else:
            elm.set('name', new_state)
        self._write()

    @property
    def state(self):
        return self._xml.get('state')

    @state.setter
    def state(self, new_state):
        self._xml.set('state', new_state)
        self._write()

    @property
    def filestates(self):
        states = {}
        for st in self._xml.find('states').iterchildren():
            states[st.get('filename')] = st.get('name')
        return states

    @property
    def uinfo(self):
        lists = {'unchanged': [], 'added': [], 'deleted': [], 'modified': [],
                 'conflicted': [], 'skipped': []}
        data = {}
        directory = self._xml.find('directory')
        uinfo_elm = self._xml.find('updateinfo')
        for listname in lists.keys():
            for entry in uinfo_elm.find(listname).iterchildren():
                filename = entry.text
                lists[listname].append(filename)
                elm = directory.find("//entry[@name='%s']" % filename)
                data[filename] = elm
        return FileUpdateInfo(data=data, remote_xml=directory, **lists)

    def cleanup(self):
        """Remove _update dir"""
        path = _storefile(self._path, '_update')
        if os.path.exists(path):
            shutil.rmtree(path)

    @staticmethod
    def read_state(path):
        """Tries to read the update state.

        path is the path to the package working copy.
        If the update state file does not exist None
        is returned. Otherwise a PackageUpdateState object.

        """
        ret = None
        try:
            data = _read_storefile(path, PackageUpdateState.FILENAME)
            ret = PackageUpdateState(path, xml_data=data)
        except ValueError as e:
            pass
        return ret


class Package(object):
    """Represents a package working copy."""

    def __init__(self, path, skip_handlers=[], merge_class=Merge,
                 transaction_listener=[]):
        """Constructs a new package object.

        path is the path to the working copy.
        Raises a ValueError exception if path is
        no valid package working copy.
        Raises a WCInconsistentError if the wc's
        metadata is corrupt.

        Keyword arguments:
        skip_handlers -- list of FileSkipHandler objects
                         (default: [])
        merge_class -- class which is used for a file merge
                       (default: Merge)
        transaction_listener -- list of TransactionListeners (default: [])

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
        self.merge_class = merge_class
        self.notifier = TransactionNotifier(transaction_listener)
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

    def _calculate_updateinfo(self, revision=''):
        unchanged = []
        added = []
        deleted = []
        modified = []
        conflicted = []
        skipped = []
        spkg = SourcePackage(self.project, self.name)
        remote_files = spkg.list(rev=revision)
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
            if st == 'A':
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
                st = self.status(lfname)
                if st == 'A':
                    # added files shouldn't be deleted
                    # so treat them as unchanged
                    unchanged.append(lfname)
                else:
                    deleted.append(lfname)
                data[lfname] = self._files.find(lfname)
        return FileUpdateInfo(unchanged, added, deleted, modified,
                              conflicted, skipped, data, remote_files)

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

    def update(self, revision='latest'):
        with wc_lock(self.path) as lock:
            ustate = PackageUpdateState.read_state(self.path)
            if (ustate is not None
                and ustate.state == PackageUpdateState.STATE_UPDATING):
                self._update(ustate)
            else:
                uinfo = self._calculate_updateinfo(revision=revision)
                self._calculate_skips(uinfo)
                # check for real conflicts
                conflicts = uinfo.conflicted
                conflicts += [c for c in self.files() if self.status(c) == 'C']
                if conflicts:
                    raise FileConflictError(conflicts)
                if not self.notifier.begin('update', uinfo):
                    msg = 'listener aborted update'
                    self.notifier.finished('update', aborted=True,
                                           abort_reason=msg)
                    return
                # TODO: if ustate is not None check if we can reuse
                #       existing files
                # states might also contain dynamic states like '!' or 'M' etc.
                states = dict([(f, self.status(f)) for f in self.files()])
                ustate = PackageUpdateState(self.path, uinfo=uinfo, **states)
                self._update(ustate)

    def _update(self, ustate):
        if ustate.state == PackageUpdateState.STATE_DOWNLOADING:
            uinfo = ustate.uinfo
            self._download(ustate.location, uinfo.data, *uinfo.added)
            self._download(ustate.location, uinfo.data, *uinfo.modified)
            ustate.state = PackageUpdateState.STATE_UPDATING
        self._perform_merges(ustate)
        self._perform_adds(ustate)
        self._perform_deletes(ustate)
        self._perform_skips(ustate)
        for filename in os.listdir(ustate.location):
            # if a merge/add was interrupted the storefile wasn't copied
            new_filename = os.path.join(ustate.location, filename)
            store_filename = wc_pkg_data_filename(self.path, filename)
            os.rename(new_filename, store_filename)
        self._files.merge(ustate.filestates, ustate.uinfo.remote_xml)
        ustate.cleanup()
        self.notifier.finished('update', aborted=False)

    def _perform_merges(self, ustate):
        uinfo = ustate.uinfo
        filestates = ustate.filestates
        for filename in uinfo.modified:
            wc_filename = os.path.join(self.path, filename)
            old_filename = wc_pkg_data_filename(self.path, filename)
            your_filename = os.path.join(ustate.location, filename)
            st = filestates[filename]
            if st == '!' or st == 'D' and not os.path.exists(wc_filename):
                my_filename = old_filename
            else:
                # XXX: in some weird cases wc_filename.mine might be a tracked
                # file - for now overwrite it
                my_filename = wc_filename + '.mine'
                # a rename would be more efficient but also more error prone
                # (if a update is interrupted)
                copy_file(wc_filename, my_filename)
            merge = self.merge_class()
            ret = merge.merge(my_filename, old_filename, your_filename,
                              wc_filename)
            if ret == Merge.SUCCESS:
                if st == 'D':
                    ustate.processed(filename, 'D')
                else:
                    ustate.processed(filename, ' ')
                os.unlink(my_filename)
            elif ret in (Merge.CONFLICT, Merge.BINARY, Merge.FAILURE):
                copy_file(your_filename, wc_filename + '.rev%s' % uinfo.srcmd5)
                ustate.processed(filename, 'C')
            # copy over new storefile
            os.rename(your_filename, old_filename)
            self.notifier.processed(filename, ustate.filestates[filename])

    def _perform_adds(self, ustate):
        uinfo = ustate.uinfo
        for filename in uinfo.added:
            wc_filename = os.path.join(self.path, filename)
            store_filename = wc_pkg_data_filename(self.path, filename)
            new_filename = os.path.join(ustate.location, filename)
            copy_file(new_filename, wc_filename)
            ustate.processed(filename, ' ')
            os.rename(new_filename, store_filename)
            self.notifier.processed(filename, ' ')

    def _perform_deletes(self, ustate):
        self._perform_deletes_or_skips(ustate, 'deleted', None)

    def _perform_skips(self, ustate):
        self._perform_deletes_or_skips(ustate, 'skipped', 'S')

    def _perform_deletes_or_skips(self, ustate, listname, new_state):
        uinfo = ustate.uinfo
        for filename in getattr(uinfo, listname):
            wc_filename = os.path.join(self.path, filename)
            store_filename = wc_pkg_data_filename(self.path, filename)
            store_md5 = ''
            if os.path.exists(store_filename):
                store_md5 = file_md5(store_filename)
            if (os.path.isfile(wc_filename)
                and file_md5(wc_filename) == store_md5):
                os.unlink(wc_filename)
            if store_md5:
                os.unlink(store_filename)
            ustate.processed(filename, new_state)
            self.notifier.processed(filename, new_state)

    def _download(self, location, data, *filenames):
        for filename in filenames:
            path = os.path.join(location, filename)
            f = data[filename].file()
            self.notifier.download(filename)
            f.write_to(path)

    def _calculate_commitinfo(self, *filenames):
        unchanged = []
        added = []
        deleted = []
        modified = []
        conflicted = []
        wc_filenames = self.files()
        if not filenames:
            filenames = wc_filenames
        for filename in wc_filenames:
            st = self.status(filename)
            if not filename in filenames:
                if st != 'A':
                    unchanged.append(filename)
                continue
            if st in ('!', 'C', '?'):
                conflicted.append(filename)
            elif st == 'A':
                added.append(filename)
            elif st == 'D':
                deleted.append(filename)
            elif st == 'M':
                modified.append(filename)
            else:
                unchanged.append(filename)
        # check for untracked
        for filename in filenames:
            if not filename in wc_filenames:
                conflicted.append(filename)
        return FileCommitInfo(unchanged, added, deleted,
                              modified, conflicted)

    def resolved(self, filename):
        """Remove conflicted state from filename.

        filename is a filename which has state 'C'.
        A ValueError is raised if filename is not "conflicted".

        """
        with wc_lock(self.path) as lock:
            self._resolved(filename)

    def _resolved(self, filename):
        st = self.status(filename)
        if st != 'C':
            raise ValueError("file \"%s\" has no conflicts" % filename)
        self._files.set(filename, ' ')

    def revert(self, filename):
        """Revert filename.

        If filename is marked as 'C', '?' or 'S' a
        ValueError is raised.

        """
        with wc_lock(self.path) as lock:
            self._revert(filename)

    def _revert(self, filename):
        st = self.status(filename)
        wc_filename = os.path.join(self.path, filename)
        store_filename = wc_pkg_data_filename(self.path, filename)
        if st == 'C':
            raise ValueError("cannot revert conflicted file: %s" % filename)
        elif st == '?':
            raise ValueError("cannot revert untracked file: %s" % filename)
        elif st == 'S':
            raise ValueError("cannot revert skipped file: %s" % filename)
        elif st == 'A':
            self._files.remove(filename)
        elif st == 'D':
            self._files.set(filename, ' ')
            if not os.path.exists(wc_filename):
                copy_file(store_filename, wc_filename)
        elif st in ('M', '!'):
            self._files.set(filename, ' ')
            copy_file(store_filename, wc_filename)
        self._files.write()

    def add(self, filename):
        """Add filename to working copy.

        Afterwards filename is tracked with state 'A'.
        A ValueError is raised if filename does not exist or
        or is no file or if it is already tracked.

        """
        with wc_lock(self.path) as lock:
            self._add(filename)

    def _add(self, filename):
        # we only allow the plain filename
        filename = os.path.basename(filename)
        wc_filename = os.path.join(self.path, filename)
        if not os.path.isfile(wc_filename):
            msg = "file \"%s\" does not exist or is no file" % filename
            raise ValueError(msg)
        st = self.status(filename)
        if st == '?':
            self._files.add(filename, 'A')
        elif st == 'D':
            self._files.set(filename, ' ')
        else:
            msg = "file \"%s\" is already tracked" % filename
            raise ValueError(msg)
        self._files.write()

    def remove(self, filename):
        """Remove file from the working copy.

        Actually this marks filename for deletion (filename has
        state 'D' afterwards).
        A ValueError is raised if filename is not tracked or
        if filename is conflicted (has state 'C') or if filename
        is skipped (has state 'S').

        """
        with wc_lock(self.path) as lock:
            self._remove(filename)

    def _remove(self, filename):
        # we only allow the plain filename (no path)
        filename = os.path.basename(filename)
        wc_filename = os.path.join(self.path, filename)
        st = self.status(filename)
        if st == 'C':
            msg = "file \"%s\" is conflicted. Please resolve first." % filename
            raise ValueError(msg)
        elif st == '?':
            raise ValueError("file \"%s\" is not tracked." % filename)
        elif st == 'S':
            raise ValueError("file \"%s\" skipped." % filename)
        elif st in ('A', ' '):
            os.unlink(wc_filename)
        self._files.set(filename, 'D')
        self._files.write()

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
