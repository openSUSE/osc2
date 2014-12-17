"""io utility functions.

Using shutil is too "insecure" for our use cases.
Additionally it provides some convenience methods.

"""

import os
import shutil
from tempfile import NamedTemporaryFile, mkdtemp as orig_mkdtemp

__all__ = ['copy_file', 'iter_read']


def _copy_file(fsource_obj, fdest_obj, bufsize, size,
               read_method, write_method):
    """Read from fsource_obj and write to fdest_obj"""
    read = getattr(fsource_obj, read_method)
    write = getattr(fdest_obj, write_method)
    for data in iter_read(fsource_obj, bufsize=bufsize, size=size,
                          read_method=read_method):
        write(data)


def copy_file(source, dest, mode=0644, mtime=None, bufsize=8096,
              size=-1, uid=-1, gid=-1, read_method='read',
              write_method='write'):
    """Copy a file source to file dest.

    source is a file-like object or a filename.
    dest is a file-like object or a filename.
    A ValueError is raised if source is a filename and
    the file does not exist.
    Note: if file-like objects are passed they won't
    be closed.
    No error is raised if the user has insufficient permissions
    to set uid or gid.

    Keyword arguments:
    mode -- the mode of file dest (default: 0644)
    mtime -- the mtime of file dest
    bufsize -- the size of each read request
    size -- copy only size bytes (default: -1, that is copy
            everything)
    uid -- the uid of file dest (default: -1, that is the uid of
           the current user is used)
    gid -- the gid of file dest (default: -1, that is the gid of
           the current user is used)
    read_method -- name of the method which should be called on
                   the source file-like object to perform a read
                   (default: read)
    write_method -- name of the method which should be called on
                    the source file-like object to perform a read
                    (default: write)

    mode and mtime are only used if dest is a filename.

    """
    fsource_obj = None
    fdest_obj = None
    source_flike = False
    dest_flike = False
    if hasattr(source, read_method):
        fsource_obj = source
        source_flike = True
    if hasattr(dest, write_method):
        fdest_obj = dest
        dest_flike = True
    if source_flike and dest_flike:
        _copy_file(fsource_obj, fdest_obj, bufsize,
                   size, read_method, write_method)
        return
    if not source_flike and not os.path.isfile(source):
        raise ValueError("source \"%s\" is no file" % source)
    if not dest_flike:
        if os.path.exists(dest) and not os.path.isfile(dest):
            raise ValueError("dest \"%s\" exists but is no file" % dest)
        dirname = os.path.dirname(dest)
        if os.path.exists(dest) and not os.access(dest, os.W_OK):
            raise ValueError("invalid dest filename: %s is not writable" %
                             dest)
        elif not os.path.exists(dirname):
            # or should we check that it is really a dir?
            raise ValueError("invalid dest filename: dir %s does not exist" %
                             dirname)
        elif not os.access(dirname, os.W_OK):
            raise ValueError("invalid dest filename: dir %s is not writable" %
                             dirname)
    tmp_filename = ''
    try:
        if not source_flike:
            fsource_obj = open(source, 'rb')
        if not dest_flike:
            dirname = os.path.dirname(dest)
            filename = os.path.basename(dest)
            fdest_obj = NamedTemporaryFile(dir=dirname, prefix=filename,
                                           delete=False)
            tmp_filename = fdest_obj.name
        _copy_file(fsource_obj, fdest_obj, bufsize,
                   size, read_method, write_method)
        if tmp_filename:
            fdest_obj.flush()
            os.rename(tmp_filename, dest)
    finally:
        if not source_flike and fsource_obj is not None:
            fsource_obj.close()
        if not dest_flike and fdest_obj is not None:
            fdest_obj.close()
        if tmp_filename and os.path.isfile(tmp_filename):
            os.unlink(tmp_filename)
    if not dest_flike:
        euid = os.geteuid()
        egid = os.getegid()
        if uid != euid or euid != 0:
            # (probably) insufficient permissions
            uid = -1
        if gid != egid or egid != 0:
            # (probably) insufficient permissions
            gid = -1
        os.chown(dest, uid, gid)
        if mtime is not None:
            os.utime(dest, (-1, mtime))
        os.chmod(dest, mode)


def iter_read(fsource, bufsize=8096, size=-1, read_method='read'):
    """Iterate over fsource and yield at most bufsize bytes.

    source is a file-like object or a filename.
    A ValueError is raised if source is a filename and
    the file does not exist.
    Note: if a file-like objects is passed it won't
    be closed.

    bufsize -- the size of each read() request
    size -- copy only size bytes (default: -1, that is copy
            everything)
    read_method -- name of the method which should be called on
                   the source file-like object to perform a read
                   (default: read)

    """
    fsource_obj = None
    source_flike = False
    if hasattr(fsource, read_method):
        fsource_obj = fsource
        source_flike = True
    try:
        if not source_flike:
            fsource_obj = open(fsource, 'rb')
        read = getattr(fsource_obj, read_method)
        rsize = bufsize
        if bufsize < size:
            rsize = bufsize
        elif size > -1:
            rsize = size
        data = read(rsize)
        while data:
            yield data
            size -= len(data)
            if size == 0:
                break
            if bufsize < size:
                rsize = bufsize
            elif size > -1:
                rsize = size
            data = read(rsize)
    finally:
        if not source_flike and fsource_obj is not None:
            fsource_obj.close()


# inspired by lnussel's mytmpdir class in osc's
# (osc1) build.py module
class TemporaryDirectory(object):
    """Represents a temporary directory.

    The temporary directory is created lazily. Once this instance
    is destroyed, the corresponding temporary directory is removed
    as well (unless delete=False was passed to the __init__ method).
    Moreover, an instance of this class can be used as a
    context manager (__exit__ deletes the temporary directory, unless
    delete=False was passed to the __init__ method).

    """
    def __init__(self, rmdir=False, delete=True, *args, **kwargs):
        """Constructs a new TemporaryDirectory instance.

        If rmdir is set to True, os.rmdir is used to remove
        the temporary directory (default: False; in this case,
        shutil.rmtree is used).
        If delete is set to False, the temporary directory is
        not automatically removed (removing it is up to the
        caller) (default: True).

        *args and **kwargs are passed to the tempfile.mkdtemp
        call.

        """
        super(TemporaryDirectory, self).__init__()
        # _path represents 3 states: '' (no tmpdir exists), the actual tmpdir,
        # and None (tmpdir removed (final state))
        self._path = ''
        self._params = (args, kwargs)
        self._delete = delete
        self._rm = self._rmtree
        if rmdir:
            self._rm = self._rmdir

    # avoid corner cases: if this module is deleted, the global names
    # "shutil"/"os" may not be available anymore (see documentation of
    # __del__ (tempfile.NamedTemporaryFile uses a similar workaround
    # for such a situation))
    _rmtree = staticmethod(shutil.rmtree)

    # staticmethod is not necessarily needed here
    _rmdir = staticmethod(os.rmdir)

    @property
    def path(self):
        """Returns the path of the tmpdir."""
        if self._path == '':
            args, kwargs = self._params
            self._path = orig_mkdtemp(*args, **kwargs)
        return self._path

    def _cleanup(self, meth=None, delete=False):
        """Removes the tmpdir, if it exists and delete is set to True.

        Afterwards, this object becomes stale.
        meth can be used to specify the cleanup method. If meth is None,
        the default cleanup method, which was specified in __init__, is used.

        """
        if self._path and os.path.isdir(self._path) and delete:
            if meth is None:
                meth = self._rm
            meth(self._path)
        # if delete is True, the object becomes "stale"
        # (regardless, if a tmpdir was created or not)
        if delete:
            self._path = None

    def rmtree(self):
        self._cleanup(meth=self._rmtree, delete=True)

    def rmdir(self):
        self._cleanup(meth=self._rmdir, delete=True)

    def __enter__(self):
        if self.path is None:
            msg = 'tmpdir was already removed'
            raise ValueError(msg)
        return self

    def __exit__(self, *args, **kwargs):
        self._cleanup(delete=self._delete)

    def __del__(self):
        self._cleanup(delete=self._delete)

    def __str__(self):
        return self.path
