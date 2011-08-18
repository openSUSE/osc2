"""Class to manage package working copies."""

import os
import hashlib
import copy
import shutil
import subprocess

from lxml import etree, objectify

from osc.core import Osc
from osc.source import File, Directory, Linkinfo
from osc.source import Package as SourcePackage
from osc.remote import RWLocalFile
from osc.util.xml import fromstring
from osc.util.io import copy_file
from osc.wc.base import (WorkingCopy, UpdateStateMixin, CommitStateMixin,
                         FileConflictError, PendingTransactionError,
                         ListInfo, no_pending_transaction)
from osc.wc.util import (wc_read_package, wc_read_project, wc_read_apiurl,
                         wc_init, wc_lock, wc_write_package, wc_write_project,
                         wc_write_apiurl, wc_write_files, wc_read_files,
                         missing_storepaths, WCInconsistentError,
                         wc_pkg_data_filename, XMLTransactionState)


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


class WCOutOfDateError(Exception):
    """Exception raised if the wc is out of date.

    That is a an operation cannot be executed because
    the wc has to be updated first.

    """

    def __init__(self, local, remote, msg=''):
        """Constructs a new WCOutOfDateError object.

        local is the wc's current revision.
        remote is the latest remote revision.
        msg is an optional error str.

        """
        super(WCOutOfDateError, self).__init__()
        self.local = local
        self.remote = remote
        self.msg = msg


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


class FileUpdateInfo(ListInfo):
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
        super(FileUpdateInfo, self).__init__(unchanged=unchanged, added=added,
                                             deleted=deleted, skipped=skipped,
                                             modified=modified,
                                             conflicted=conflicted)
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


class FileCommitInfo(ListInfo):
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
        super(FileCommitInfo, self).__init__(unchanged=unchanged, added=added,
                                             deleted=deleted,
                                             modified=modified,
                                             conflicted=conflicted)


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


class PackageUpdateState(XMLTransactionState, UpdateStateMixin):

    def __init__(self, path, uinfo=None, xml_data=None, **states):
        initial_state = UpdateStateMixin.STATE_PREPARE
        super(PackageUpdateState, self).__init__(path, 'update', initial_state,
                                                 uinfo, xml_data, **states)
        if xml_data is None:
            self._xml.append(uinfo.remote_xml)

    def _listnames(self):
        return ('unchanged', 'added', 'deleted', 'modified',
                'conflicted', 'skipped')

    @property
    def info(self):
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
        if ustate.state == UpdateStateMixin.STATE_PREPARE:
            ustate.cleanup()
            return True
        return False


class PackageCommitState(XMLTransactionState, CommitStateMixin):

    def __init__(self, path, cinfo=None, xml_data=None, **states):
        initial_state = CommitStateMixin.STATE_TRANSFER
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
    def info(self):
        """Return the FileCommitInfo object."""
        lists = self._lists()
        return FileCommitInfo(**lists)

    @staticmethod
    def rollback(path):
        cstate = PackageCommitState.read_state(path)
        if cstate.name != 'commit':
            raise ValueError("no commit transaction")
        if cstate.state == CommitStateMixin.STATE_COMMITTING:
            return False
        states = cstate.entrystates
        for filename in os.listdir(cstate.location):
            wc_filename = os.path.join(path, filename)
            commit_filename = os.path.join(cstate.location, filename)
            st = states.get(filename, None)
            if st is not None and not os.path.exists(wc_filename):
                # restore original wcfile
                os.rename(commit_filename, wc_filename)
        cstate.cleanup()
        return True


class Package(WorkingCopy):
    """Represents a package working copy."""

    def __init__(self, path, skip_handlers=[], commit_policies=[],
                 merge_class=Merge, **kwargs):
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
        **kwargs -- see class WorkingCopy for the details

        """
        (meta, xml_data, pkg_data) = self.wc_check(path)
        if meta or xml_data or pkg_data:
            raise WCInconsistentError(path, meta, xml_data, pkg_data)
        self.apiurl = wc_read_apiurl(path)
        self.project = wc_read_project(path)
        self.name = wc_read_package(path)
        self.skip_handlers = skip_handlers
        self.commit_policies = commit_policies
        self.merge_class = merge_class
        with wc_lock(path) as lock:
            self._files = wc_read_files(path)
        # call super at the end due to finish_pending_transaction
        super(Package, self).__init__(path, PackageUpdateState,
                                      PackageCommitState, **kwargs)

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

    def has_conflicts(self):
        return [c for c in self.files() if self.status(c) == 'C']

    def _calculate_updateinfo(self, revision='', remote_files=None, **kwargs):
        unchanged = []
        added = []
        deleted = []
        modified = []
        conflicted = []
        skipped = []
        if remote_files is None:
            spkg = SourcePackage(self.project, self.name)
            remote_files = spkg.list(rev=revision, apiurl=self.apiurl,
                                     **kwargs)
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
        for handler in self.skip_handlers:
            skips, unskips = handler.skip(copy.deepcopy(uinfo))
            inv = [f for f in skips if not f in uinfo.data.keys()]
            inv += [f for f in unskips if not f in uinfo.skipped]
            if inv:
                msg = "invalid skip/unskip files: %s" % ', '.join(inv)
                raise ValueError(msg)
            for skip in skips:
                uinfo.remove(skip)
                uinfo.skipped.append(skip)
            for unskip in unskips:
                uinfo.skipped.remove(unskip)
                if os.path.exists(os.path.join(self.path, unskip)):
                    uinfo.conflicted.append(unskip)
                else:
                    uinfo.added.append(unskip)

    def update(self, revision='latest', **kwargs):
        """Update working copy.

        Keyword arguments:
        revision -- the update revision (default: latest)
        **kwargs -- optional arguments for the "getfilelist" http
                    request

        """
        with wc_lock(self.path) as lock:
            ustate = PackageUpdateState.read_state(self.path)
            if not self.is_updateable(rollback=True):
                if self.has_conflicts():
                    raise FileConflictError(self.has_conflicts())
                # commit can be the only pending transaction
                raise PendingTransactionError('commit')
            elif (ustate is not None
                and ustate.state == UpdateStateMixin.STATE_UPDATING):
                self._update(ustate)
            else:
                uinfo = self._calculate_updateinfo(revision=revision, **kwargs)
                self._calculate_skips(uinfo)
                conflicts = uinfo.conflicted
                if conflicts:
                    # these are _only_ update conflicts
                    raise FileConflictError(conflicts)
                if not self._transaction_begin('update', uinfo):
                    return
                # TODO: if ustate is not None check if we can reuse
                #       existing files
                # states might also contain dynamic states like '!' or 'M' etc.
                states = dict([(f, self.status(f)) for f in self.files()])
                ustate = PackageUpdateState(self.path, uinfo=uinfo, **states)
                self._update(ustate)

    def _update(self, ustate):
        if ustate.state == UpdateStateMixin.STATE_PREPARE:
            uinfo = ustate.info
            self._download(ustate.location, uinfo.data, *uinfo.added)
            self._download(ustate.location, uinfo.data, *uinfo.modified)
            ustate.state = UpdateStateMixin.STATE_UPDATING
        self._perform_merges(ustate)
        self._perform_adds(ustate)
        self._perform_deletes(ustate)
        self._perform_skips(ustate)
        for filename in os.listdir(ustate.location):
            # if a merge/add was interrupted the storefile wasn't copied
            new_filename = os.path.join(ustate.location, filename)
            store_filename = wc_pkg_data_filename(self.path, filename)
            os.rename(new_filename, store_filename)
        self._files.merge(ustate.entrystates, ustate.info.remote_xml)
        ustate.cleanup()
        self.notifier.finished('update', aborted=False)

    def _perform_merges(self, ustate):
        uinfo = ustate.info
        filestates = ustate.entrystates
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
            self.notifier.processed(filename, ustate.entrystates[filename])

    def _perform_adds(self, ustate):
        uinfo = ustate.info
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
        uinfo = ustate.info
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
            f = data[filename].file(apiurl=self.apiurl)
            self.notifier.transfer('download', filename)
            f.write_to(path)

    def is_modified(self):
        cinfo = self._calculate_commitinfo()
        return (cinfo.added or cinfo.deleted
                or cinfo.modified or cinfo.conflicted)

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
                # no 'A' state because unchanged files are part
                # of the commit
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
                    cinfo.remove(filename)
                    cinfo.append(filename, listname)

    def commit(self, *filenames, **kwargs):
        """Commit working copy.

        If no filenames are specified all tracked files
        are committed.

        Keyword arguments:
        **kwargs -- optional parameters for the final commit
                    http request

        """
        with wc_lock(self.path) as lock:
            cstate = self._pending_transaction()
            if not self.is_commitable(rollback=True):
                if self.has_conflicts():
                    raise FileConflictError(self.has_conflicts())
                # update can be the only pending transaction
                raise PendingTransactionError('update')
            elif (cstate is not None
                and cstate.state == CommitStateMixin.STATE_COMMITTING):
                self._commit(cstate)
            else:
                cinfo = self._calculate_commitinfo(*filenames)
                self._apply_commit_policies(cinfo)
                conflicts = cinfo.conflicted
                if conflicts:
                    # conflicts shouldn't contain real conflicts because
                    # otherwise is_commitable returns False
                    raise FileConflictError(conflicts)
                remote = self.latest_revision()
                local = self._files.revision_data().get('srcmd5')
                if local != remote:
                    msg = 'commit not possible. Please update first'
                    raise WCOutOfDateError(local, remote, msg)
                if not self._transaction_begin('commit', cinfo):
                    return
                states = dict([(f, self.status(f)) for f in self.files()])
                cstate = PackageCommitState(self.path, cinfo=cinfo, **states)
                self._commit(cstate, **kwargs)

    def _commit(self, cstate, **kwargs):
        cinfo = cstate.info
        # FIXME: validation
        if cstate.state == CommitStateMixin.STATE_TRANSFER:
            cfilelist = self._calculate_commit_filelist(cinfo)
            missing = self._commit_filelist(cfilelist, **kwargs)
            send_filenames = self._read_send_files(missing)
            if send_filenames:
                self._commit_files(cstate, send_filenames)
                filelist = self._commit_filelist(cfilelist, **kwargs)
            else:
                filelist = missing
            cstate.append_filelist(filelist)
            cstate.state = CommitStateMixin.STATE_COMMITTING
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
        self._files.merge(cstate.entrystates, cstate.filelist)
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

    def _commit_filelist(self, xml_data, **kwargs):
        request = Osc.get_osc().get_reqobj()
        path = "/source/%s/%s" % (self.project, self.name)
        query = {'cmd': 'commitfilelist'}
        if self.is_expanded():
            # the expanded check is not neccessary
            query['keeplink'] = '1'
            query['expand'] = '1'
        query.update(kwargs)
        f = request.post(path, data=xml_data, apiurl=self.apiurl, **query)
        return fromstring(f.read(), directory=Directory, entry=File,
                          linkinfo=Linkinfo)

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
            lfile.write_back(force=True, rev='repository', apiurl=self.apiurl)
            cstate.processed(filename, ' ')
            commit_filename = os.path.join(cstate.location, filename)
            # move wcfile into transaction dir
            os.rename(lfile.path, commit_filename)
            self.notifier.processed(filename, ' ')

    def latest_revision(self):
        """Return the latest remote revision."""
        spkg = SourcePackage(self.project, self.name)
        directory = spkg.list(rev='latest', apiurl=self.apiurl)
        if self.is_link():
            if directory.linkinfo.has_error():
                # FIXME: proper error handling
                return 'latest'
            elif self.is_expanded():
                return directory.linkinfo.get('xsrcmd5')
        return directory.get('srcmd5')

    @no_pending_transaction
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
        super(Package, self).revert(filename)
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
        super(Package, self).add(filename)
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
        super(Package, self).remove(filename)
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

    def is_link(self):
        """Return True if the package is a source link."""
        return self._files.is_link()

    def is_expanded(self):
        """Return True if the working copy is expanded."""
        return self.is_link() and self._files.linkinfo.is_expanded()

    def is_unexpanded(self):
        """Return True if the working copy is unexpanded."""
        return self.is_link() and not self.is_expanded()

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
    def init(path, project, package, apiurl, ext_storedir=None, **kwargs):
        """Initializes a directory as a package working copy.

        path is a path to a directory, project is the name
        of the project, package is the name of the package
        and apiurl is the apiurl.

        Keyword arguments:
        ext_storedir -- path to the storedir (default: None).
                        If not specified a "flat" package is created,
                        otherwise path/.osc is a symlink to storedir.
        kwargs -- optional keyword args which are passed to Package's
                  __init__ method

        """
        wc_init(path, ext_storedir=ext_storedir)
        wc_write_project(path, project)
        wc_write_package(path, package)
        wc_write_apiurl(path, apiurl)
        wc_write_files(path, '<directory/>')
        return Package(path, **kwargs)
