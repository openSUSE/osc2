"""Class to manage package working copies."""

import os
import hashlib
import copy
import shutil
import subprocess

from lxml import etree, objectify

from osc.core import Osc
from osc.source import File, Directory
from osc.source import Package as SourcePackage
from osc.remote import RWLocalFile
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


class WCOutOfDateError(Exception):
    """Exception raised if the wc is out of date.

    That is a an operation cannot be executed because
    the wc has to be updated first.

    """

    def __init__(self):
        super(WCOutOfDateError, self).__init__()


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

    def transfer(self, transfer_type, filename):
        """Transfer filename.

        transfer_type is either 'download' or
        'upload'.

        """
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

    def transfer(self, *args, **kwargs):
        self._notify('transfer', *args, **kwargs)

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


class FileCommitPolicy(object):
    """Used to manipulate the calculated commitinfo."""

    def apply(self, cinfo):
        """Calculate new commit lists.

        cinfo is a FileCommitInfo instance.
        A 4-tuple (unchanged, added, deleted, modified) is
        returned. These lists will be used to create a new
        FileCommitInfo object.

        """
        raise NotImplementedError()


class PendingTransactionError(Exception):
    """Raised if a transaction was aborted and no rollback is possible."""

    def __init__(self, name):
        """Constructs a new PendingTransactionError object.

        name is the name of the pending transaction.

        """
        self.name = name


class XMLTransactionState(object):
    """Represents the state of a transaction"""

    DIR = '_transaction'
    FILENAME = os.path.join(DIR, 'state')

    def __init__(self, path, name, initial_state, info=None,
                 xml_data=None, **states):
        """Constructs a new XMLTransactionState object.

        path is the path to the package working copy.
        name is the name of the transaction.
        initial_state is the initial state of the transaction.
        Either info or xml_data has to be specified otherwise
        a ValueError is raised.

        Keyword arguments:
        info -- a FileUpdateInfo or FileCommitInfo object.
        xml_data -- xml string.
        states -- maps each wc file to its current state

        """
        if ((info is not None and xml_data)
            or (info is None and xml_data is None)):
            raise ValueError('either specify info or xml_data')
        super(XMLTransactionState, self).__init__()
        self._path = path
        global _PKG_DATA
        trans_dir = _storefile(self._path, XMLTransactionState.DIR)
        data_dir = os.path.join(trans_dir, _PKG_DATA)
        self.location = data_dir
        if xml_data:
            self._xml = fromstring(xml_data, entry=File, directory=Directory)
        else:
            self.cleanup()
            os.mkdir(trans_dir)
            os.mkdir(data_dir)
            xml_data = ('<transaction name="%s" state="%s"/>'
                % (name, initial_state))
            self._xml = fromstring(xml_data)
            self._xml.append(self._xml.makeelement('states'))
            self._add_states(states)
            self._xml.append(self._xml.makeelement('info'))
            for listname in self._listnames():
                self._add_list(listname, info)
            self._write()

    def _add_states(self, states):
        states_elm = self._xml.find('states')
        for filename, st in states.iteritems():
            elm = states_elm.makeelement('state', filename=filename, name=st)
            states_elm.append(elm)

    def _add_list(self, listname, info):
        info_elm = self._xml.find('info')
        child = info_elm.makeelement(listname)
        info_elm.append(child)
        for filename in getattr(info, listname):
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
        """The file filename was processed.

        new_state is the new state of filename. If new_state
        is None filename won't be tracked anymore. Afterwards
        filename is removed from the info list.
        A ValueError is raised if filename is not part of
        a info list.

        """
        # remove file from info
        info_elm = self._xml.find('info')
        elm = info_elm.find("//*[text() = '%s']" % filename)
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
    def filestates(self):
        states = {}
        for st in self._xml.find('states').iterchildren():
            states[st.get('filename')] = st.get('name')
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
                filename = entry.text
                lists[listname].append(filename)
        return lists

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
        is returned. Otherwise a PackageUpdateState object.

        """
        ret = None
        try:
            data = _read_storefile(path, XMLTransactionState.FILENAME)
            ret = cls(path, xml_data=data)
        except ValueError as e:
            pass
        return ret

    @staticmethod
    def rollback(path):
        """Revert current transaction (if possible).

        Return True if a rollback is possible (this also
        indicates that the rollback itself was successfull).
        Otherwise False is returned.
        A ValueError is raised if the transaction names/types
        mismatch.

        """
        raise NotImplementedError()


class PackageUpdateState(XMLTransactionState):
    STATE_DOWNLOADING = '1'
    STATE_UPDATING = '2'

    def __init__(self, path, uinfo=None, xml_data=None, **states):
        initial_state = PackageUpdateState.STATE_DOWNLOADING
        super(PackageUpdateState, self).__init__(path, 'update', initial_state,
                                                 uinfo, xml_data, **states)
        if xml_data is None:
            self._xml.append(uinfo.remote_xml)

    def _listnames(self):
        return ('unchanged', 'added', 'deleted', 'modified',
                'conflicted', 'skipped')

    @property
    def uinfo(self):
        """Return the FileUpdateInfo object."""
        lists = self._lists()
        directory = self._xml.find('directory')
        data = {}
        for filenames in lists.itervalues():
            for filename in filenames:
                elm = directory.find("//entry[@name='%s']" % filename)
                data[filename] = elm
        return FileUpdateInfo(data=data, remote_xml=directory, **lists)

    @property
    def filelist(self):
        return self._xml.find('directory')

    @staticmethod
    def rollback(path):
        ustate = PackageUpdateState.read_state(path)
        if ustate.name != 'update':
            raise ValueError("no update transaction")
        if ustate.state == PackageUpdateState.STATE_DOWNLOADING:
            ustate.cleanup()
            return True
        return False


class PackageCommitState(XMLTransactionState):
    STATE_UPLOADING = '10'
    STATE_COMMITTING = '11'

    def __init__(self, path, cinfo=None, xml_data=None, **states):
        initial_state = PackageCommitState.STATE_UPLOADING
        super(PackageCommitState, self).__init__(path, 'commit', initial_state,
                                                 cinfo, xml_data, **states)

    def _listnames(self):
        return ('unchanged', 'added', 'deleted', 'modified',
                'conflicted')

    def append_filelist(self, filelist):
        self._xml.append(filelist)
        self._write()

    @property
    def filelist(self):
        return self._xml.find('directory')

    @property
    def cinfo(self):
        """Return the FileCommitInfo object."""
        lists = self._lists()
        return FileCommitInfo(**lists)

    @staticmethod
    def rollback(path):
        cstate = PackageCommitState.read_state(path)
        if cstate.name != 'commit':
            raise ValueError("no commit transaction")
        if cstate.state == PackageCommitState.STATE_COMMITTING:
            return False
        states = cstate.filestates
        for filename in os.listdir(cstate.location):
            wc_filename = os.path.join(path, filename)
            commit_filename = os.path.join(cstate.location, filename)
            st = states.get(filename, None)
            if st is not None and not os.path.exists(wc_filename):
                # restore original wcfile
                os.rename(commit_filename, wc_filename)
        cstate.cleanup()
        return True


class Package(object):
    """Represents a package working copy."""

    def __init__(self, path, skip_handlers=[], commit_policies=[],
                 merge_class=Merge, transaction_listener=[]):
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
        self.commit_policies = commit_policies
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
            if not self.is_updateable(rollback=True):
                # commit can be the only pending transaction
                raise PendingTransactionError('commit')
            elif (ustate is not None
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
            self.notifier.transfer('download', filename)
            f.write_to(path)

    def is_updateable(self, rollback=False):
        """Check if wc can be updated.

        If rollback is True a pending transaction will be
        rolled back (if possible).
        Return True if an update is possible. Otherwise
        False is returned.

        """
        ustate = PackageUpdateState.read_state(self.path)
        if ustate is None:
            return True
        elif ustate.name == 'update':
            return True
        elif rollback:
            return PackageCommitState.rollback(self.path)
        return ustate.state == PackageCommitState.STATE_UPLOADING

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

    def _apply_commit_policies(self, cinfo):
        """Apply commit policies.

        A ValueError is raised if a commit policy returns
        an invalid unchanged or deleted list.

        """
        def cinfo_remove(filename):
            cinfo.unchanged = [f for f in cinfo.unchanged if f != filename]
            cinfo.added = [f for f in cinfo.added if f != filename]
            cinfo.deleted = [f for f in cinfo.deleted if f != filename]
            cinfo.modified = [f for f in cinfo.modified if f != filename]

        filenames = self.files()
        for policy in self.commit_policies:
            unchanged, deleted = policy.apply(copy.deepcopy(cinfo))
            dis = [f for f in unchanged if f in deleted]
            if dis:
                msg = "commit policy: unchanged and deleted not disjunct"
                raise ValueError(msg)
            lists = {'unchanged': unchanged, 'deleted': deleted}
            for listname, data in lists.iteritems():
                for filename in data:
                    if not filename in filenames:
                        msg = ("commit policy: file \"%s\" isn't tracked"
                               % filename)
                        raise ValueError(msg)
                    cinfo_remove(filename)
                    cinfo_list = getattr(cinfo, listname)
                    cinfo_list.append(filename)

    def commit(self, *filenames):
        """Commit working copy.

        If no filenames are specified all tracked files
        are committed.

        """
        with wc_lock(self.path) as lock:
            cstate = PackageCommitState.read_state(self.path)
            if not self.is_commitable(rollback=True):
                # update can be the only pending transaction
                raise PendingTransactionError('update')
            elif (cstate is not None
                and cstate.state == PackageCommitState.STATE_COMMITTING):
                self._commit(cstate)
            else:
                cinfo = self._calculate_commitinfo(*filenames)
                self._apply_commit_policies(cinfo)
                conflicts = cinfo.conflicted
                conflicts += [c for c in self.files() if self.status(c) == 'C']
                if conflicts:
                    raise FileConflictError(conflicts)
                if not self.notifier.begin('commit', cinfo):
                    msg = 'listener aborted commit'
                    self.notifier.finished('commit', aborted=True,
                                           abort_reason=msg)
                    return
                states = dict([(f, self.status(f)) for f in self.files()])
                cstate = PackageCommitState(self.path, cinfo=cinfo, **states)
                self._commit(cstate)

    def _commit(self, cstate):
        cinfo = cstate.cinfo
        # FIXME: validation
        if cstate.state == PackageCommitState.STATE_UPLOADING:
            cfilelist = self._calculate_commit_filelist(cinfo)
            missing = self._commit_filelist(cfilelist)
            send_filenames = self._read_send_files(missing)
            if send_filenames:
                self._commit_files(cstate, send_filenames)
                filelist = self._commit_filelist(cfilelist)
            else:
                filelist = missing
            cstate.append_filelist(filelist)
            cstate.state = PackageCommitState.STATE_COMMITTING
        # only local changes left
        for filename in cinfo.deleted:
            store_filename = wc_pkg_data_filename(self.path, filename)
            # it might be already removed (if we resume a commit)
            if os.path.exists(store_filename):
                os.unlink(store_filename)
            cstate.processed(filename, None)
            self.notifier.processed(filename, None)
        for filename in os.listdir(cstate.location):
            wc_filename = os.path.join(self.path, filename)
            store_filename = wc_pkg_data_filename(self.path, filename)
            commit_filename = os.path.join(cstate.location, filename)
            if os.path.exists(store_filename):
                # just to reduce disk space usage
                os.unlink(store_filename)
            copy_file(commit_filename, wc_filename)
            os.rename(commit_filename, store_filename)
        self._files.merge(cstate.filestates, cstate.filelist)
        # fixup mtimes
        for filename in self.files():
            if self.status(filename) != ' ':
                continue
            entry = self._files.find(filename)
            wc_filename = os.path.join(self.path, filename)
            store_filename = wc_pkg_data_filename(self.path, filename)
            mtime = int(entry.get('mtime'))
            os.utime(wc_filename, (-1, mtime))
            os.utime(store_filename, (-1, mtime))
        cstate.cleanup()
        self.notifier.finished('commit', aborted=False)

    def _calculate_commit_filelist(self, cinfo):
        def _append_entry(xml, entry):
            xml.append(xml.makeelement('entry', name=entry.get('name'),
                                       md5=entry.get('md5')))

        xml = fromstring('<directory/>')
        for filename in cinfo.unchanged:
            if self.status(filename) == 'A':
                # skip added files
                continue
            _append_entry(xml, self._files.find(filename))
        for filename in cinfo.added + cinfo.modified:
            wc_filename = os.path.join(self.path, filename)
            md5 = file_md5(wc_filename)
            _append_entry(xml, {'name': filename, 'md5': md5})
        xml_data = etree.tostring(xml, pretty_print=True)
        return xml_data

    def _commit_filelist(self, xml_data):
        request = Osc.get_osc().get_reqobj()
        path = "/source/%s/%s" % (self.project, self.name)
        f = request.post(path, data=xml_data, cmd='sourcecommitfilelist')
        return fromstring(f.read(), entry=File, directory=Directory)

    def _read_send_files(self, directory):
        if directory.get('error') != 'missing':
            return []
        send_filenames = []
        for entry in directory:
            send_filenames.append(entry.get('name'))
        return send_filenames

    def _commit_files(self, cstate, send_filenames):
        for filename in send_filenames:
            wc_filename = os.path.join(self.path, filename)
            path = "/source/%s/%s/%s" % (self.project, self.name, filename)
            lfile = RWLocalFile(wc_filename, wb_path=path, append=True)
            self.notifier.transfer('upload', filename)
            lfile.write_back(force=True, rev='repository')
            cstate.processed(filename, ' ')
            commit_filename = os.path.join(cstate.location, filename)
            # move wcfile into transaction dir
            os.rename(lfile.path, commit_filename)
            self.notifier.processed(filename, ' ')

    def is_commitable(self, rollback=False):
        """Check if wc can be committed.

        If rollback is True a pending transaction will be
        rolled back (if possible).
        Return True if a commit is possible. Otherwise
        False is returned.

        """
        cstate = PackageCommitState.read_state(self.path)
        if cstate is None:
            return True
        elif cstate.name == 'commit':
            return True
        elif rollback:
            return PackageUpdateState.rollback(self.path)
        return ustate.state == PackageUpdateState.STATE_DOWNLOADING

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
