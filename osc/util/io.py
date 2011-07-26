"""io utility functions.

Using shutil is too "insecure" for our use cases.
Additionally it provides some convenience methods.

"""

import os
from tempfile import NamedTemporaryFile

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
              size=-1, read_method='read', write_method='write'):
    """Copy a file source to file dest.

    source is a file-like object or a filename.
    dest is a file-like object or a filename.
    A ValueError is raised if source is a filename and
    the file does not exist.
    Note: if file-like objects are passed they won't
    be closed.

    Keyword arguments:
    mode -- the mode of file dest (default: 0644)
    mtime -- the mtime of file dest
    bufsize -- the size of each read request
    size -- copy only size bytes (default: -1, that is copy
            everything)
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
