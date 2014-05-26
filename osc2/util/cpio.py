"""This module provides classes to read and write a cpio archive."""

import os
import mmap
from struct import pack, unpack
from collections import namedtuple
from cStringIO import StringIO

from osc2.util.io import copy_file, iter_read


TRAILER = 'TRAILER!!!'
IO_BLOCK_SIZE = 512


class CpioError(Exception):
    """Exception class for cpio related errors."""

    def __init__(self, msg):
        """Constructs a new CpioError object.

        msg is the error message.

        """
        super(CpioError, self).__init__()
        self.msg = msg


class FileWrapper(object):
    """This class acts as a wrapper around a file or file-like object."""

    def __init__(self, filename='', mode='r', fobj=None, use_mmap=False):
        """Constructs a new FileWrapper object.

        A ValueError is raised if neither filename nor fobj is specified
        or if both are specified. Also a ValueError is raised if fobj
        is specied and mmap is True (it should be up to the caller if
        it makes sense to mmap the file).

        Keyword arguments:
        filename -- a filename (default: '')
        mode -- the file mode (either 'r' or 'w') (default: 'r')
        fobj -- a file or file-like object (default: None)
        use_mmap -- if a filename is passed the file will be mmap'ed
                (default: False)

        """
        super(FileWrapper, self).__init__()
        if not filename and fobj is None:
            raise ValueError('A filename or fobj is required')
        elif filename and fobj is not None:
            raise ValueError('Either specify a filename or a fobj')
        elif fobj is not None and use_mmap:
            raise ValueError('fobj and mmap are not supported')

        if filename:
            self._close = True
            self._fobj = open(filename, mode)
            if use_mmap:
                self._fobj = mmap.mmap(self._fobj.fileno(), 0,
                                       prot=mmap.PROT_READ)
        elif fobj is not None:
            self._close = False
            self._fobj = fobj
        self._pos = 0
        self._peek_data = ''

    def is_seekable(self):
        """Returns True if the underlying file object is seekable."""
        seek = getattr(self._fobj, 'seek', None)
        return seek is not None

    def read(self, num=-1):
        """Read num bytes.

        If num is -1 read the complete file.

        Keyword arguments:
        num -- the number of bytes to be read (default: -1)

        """
        data = ''
        if self._peek_data:
            if num >= 0:
                data = self._peek_data[:num]
                self._peek_data = self._peek_data[num:]
                num -= len(data)
            else:
                data = self._peek_data
                self._peek_data = ''
        data += self._fobj.read(num)
        self._pos += len(data)
        return data

    def peek(self, num):
        """Peeks num bytes from the file.

        The file pointer will not move forward, that is
        self.tell() equals self.tell() after a peek.

        """
        self._peek_data = self.read(num)
        self._pos -= len(self._peek_data)
        return self._peek_data

    def seek(self, pos, whence=os.SEEK_SET):
        """Seek to pos position.

        Seeking might be possible even if the underlying file is not
        seekable if the following conditions are met:
        * seek forward (absolute position) or
        * seek forward (relative position)

        If neither of the conditions are met an IOError is raised.

        Keyword arguments:
        whence -- defines how to calculate the new position
                  (default: os.SEEK_SET)

        """
        if self._peek_data:
            raise IOError('seek only possible if all peek\'ed data is read')
        if self.is_seekable():
            self._fobj.seek(pos, whence)
            self._pos = self._fobj.tell()
            return
        num = 0
        if whence == os.SEEK_SET and pos >= self._pos:
            num = pos - self._pos
        elif whence == os.SEEK_CUR and pos >= 0:
            num = pos
        else:
            raise IOError('file object is not seekable')
        self.read(num)

    def tell(self):
        """Returns the current file position"""
        return self._pos

    def close(self):
        """Closes the FileWrapper.

        The internal file object is only closed if no fobj was passed to
        the constructor.

        """
        if self._close:
            self._fobj.close()


class CpioEntity(object):
    """Base class which represents a cpio archive entity.

    A cpio entity might be a file, directory etc.

    """

    def __init__(self, hdr):
        """Constructs a new CpioEntity object.

        hdr is the cpio header of the entity.

        """
        super(CpioEntity, self).__init__()
        self.hdr = hdr

    def copyin(self, dest):
        """Copies the entity to dest.

        If dest is no directory a ValueError is raised.

        """
        raise NotImplementedError()


class CpioFile(CpioEntity):
    """Represents a regular file in a cpio archive."""

    def __init__(self, fobj, hdr):
        """Constructs a new CpioFile object.

        fobj is a FileWrapper instance and hdr is the cpio
        header.

        """
        super(CpioFile, self).__init__(hdr)
        self._fobj = fobj
        self._bytes_read = 0

    def read(self, num=-1):
        """Read num bytes.

        If num is -1 read the complete file.

        Keyword arguments:
        num -- the number of bytes to be read (default: -1)

        """
        offset = self.hdr._offset
        filesize = self.hdr.filesize
        if num > filesize - self._bytes_read or num == -1:
            num = filesize - self._bytes_read
        if filesize - self._bytes_read == 0:
            return ''
        # ok still some bytes left to read
        pos = self._fobj.tell()
        if pos < offset or pos > offset + self.hdr.filesize:
            self._fobj.seek(offset + self._bytes_read)
        data = self._fobj.read(num)
        self._bytes_read += len(data)
        return data

    def copyin(self, dest):
        """Copies the entity to dest.

        Despite the fact that the base class requires
        that dest is a directory dest can also be a file or
        file-like object.

        """
        if not hasattr(dest, 'write'):
            # no file-like object
            dest = os.path.join(dest, self.hdr.name)
        copy_file(self, dest, mode=self.hdr.mode, mtime=self.hdr.mtime)


class CpioHeader(object):
    """Represents a cpio header.

    This class corresponds more or less to "struct cpio_file_stat"
    (see src/cpiohdr.h).

    """
    ENTRIES = ('ino', 'mode', 'uid', 'gid', 'nlink', 'mtime', 'filesize',
               'dev_maj', 'dev_min', 'rdev_maj', 'rdev_min', 'namesize',
               'chksum')

    def __init__(self, magic, data, no_convert=False):
        """Constructs a new CpioHeader object.

        magic is the format magic and data is a tuple which is used to
        fill in the header attributes (each item in the tuple is a
        hexadecimal int).

        """
        super(CpioHeader, self).__init__()
        self.magic = magic
        if not no_convert:
            data = [int(i, 16) for i in data]
        self.__dict__.update(zip(self.ENTRIES, data))
        # will be set later
        self.name = None
        # this is no official header attr but it makes life easier
        # will be set later
        # offset is the absolute position where the file contents start
        self._offset = None

    def __iter__(self):
        """Returns header entries a hexadecimal str (except the magic)."""
        yield self.magic
        for entry in CpioHeader.ENTRIES:
            yield "%08X" % getattr(self, entry)


class ArchiveReader(object):
    """Base class for the cpio format specific readers."""

    def __init__(self, fobj, magic):
        """Constructs a new ArchiveReader object.

        fobj is a FileWrapper instance and magic is the archive
        magic.

        """
        super(ArchiveReader, self).__init__()
        self._fobj = fobj
        self.magic = magic
        self._next_header_pos = 0
        # if True indicates end of archive
        self.trailer_seen = False

    def _move_next_header_pos(self):
        """Moves the FileWrapper instance to the next header position.

        A CpioError is raised if the FileWrapper has an illegal/unexpected
        position.

        """
        pos = self._fobj.tell()
        if pos > self._next_header_pos:
            # this should not happen
            msg = ("unexpected file pos: %d (expected: %d)"
                   % (pos, self._next_header_pos))
            raise CpioError(msg)
        if pos != self._next_header_pos:
            self._fobj.seek(self._next_header_pos, os.SEEK_SET)

    def next_header(self):
        """Returns the next header in the archive.

        None is returned if no header is available.

        """
        raise NotImplementedError()

    def next_file(self):
        """Returns the next file in the archive.

        None is returned if no file is available.

        """
        raise NotImplementedError()


class ArchiveWriter(object):
    """Base class for the cpio format specific writers."""

    def __init__(self, fobj):
        """Constructs a new ArchiveReader object.

        fobj is a file or file-like object.

        """
        self._fobj = fobj
        # number of written bytes (to self._fobj)
        self._bytes_written = 0

    def append(self, filename, fobj=None):
        """Appends a new file to the archive.

        filename is a path to a file or if fobj is not
        None filename is a simple filename.

        Keyword arguments:
        fobj -- file or file-like object which should be appended
                (default: None)

        """
        raise NotImplementedError()

    def copyout(self):
        """"Close" archive.

        That is write the trailer and padding bytes.

        """
        global IO_BLOCK_SIZE
        self._append_trailer()
        pad = IO_BLOCK_SIZE - (self._bytes_written % IO_BLOCK_SIZE)
        if pad > 0:
            self._fobj.write('\0' * pad)
            self._bytes_written += pad

    def _write_header(self, hdr, source):
        """Writes the header.

        hdr is the current header to be written and source is
        a file or file-like object which represents the file.

        """
        raise NotImplementedError()

    def _create_dummy_stat(self, *args):
        """Returns a dummy stat structure.

        args are parameters are the corresponding struct entries.
        args has the following order:
        args = ('st_ino', 'st_mode', 'st_dev', 'st_rdev', 'st_nlink',
                'st_uid', 'st_gid', 'st_size', 'st_mtime')

        """
        entries = ['st_ino', 'st_mode', 'st_dev', 'st_rdev', 'st_nlink',
                   'st_uid', 'st_gid', 'st_size', 'st_mtime']
        dummy_stat = namedtuple('dummy_stat', entries)
        return dummy_stat(*args)

    def _append_trailer(self):
        """Appends the trailer"""
        global TRAILER
        st = self._create_dummy_stat(0, 0, 0, 0, 1, 0, 0, 0, 0)
        hdr = self._create_header(st, TRAILER)
        self._write_header(hdr, StringIO())


class NewAsciiReader(ArchiveReader):
    """This class can read the new ascii format.

    "New" portable format: magic 070701

    """

    def __init__(self, fobj):
        """Constructs a new NewAsciiReader object.

        fobj is a FileWrapper instance.

        """
        super(NewAsciiReader, self).__init__(fobj, NewAsciiFormat.MAGIC)

    def next_header(self):
        if self.trailer_seen:
            return None
        self._move_next_header_pos()
        hdr = self._read_header()
        self._calculate_file_offset(hdr)
        self._calculate_next_header_pos(hdr)
        return hdr

    def next_file(self):
        hdr = self.next_header()
        if hdr is None:
            return None
        return CpioFile(self._fobj, hdr)

    def _read_header(self):
        """Returns the newly read header.

        In case of an error a CpioError is raised.

        """
        global TRAILER
        data = self._fobj.read(NewAsciiFormat.LEN)
        if len(data) != NewAsciiFormat.LEN:
            msg = ("premature end of file (expected at least \'%d\' bytes)"
                   % NewAsciiFormat.LEN)
            raise CpioError(msg)
        data = unpack(NewAsciiFormat.FORMAT, data)
        hdr = CpioHeader(data[0], data[1:])
        # read filename
        data = self._fobj.read(hdr.namesize)
        # ignore trailing '\0'
        hdr.name = data[:-1]
        self.trailer_seen = hdr.name == TRAILER
        return hdr

    def _calculate_file_offset(self, hdr):
        """Calculate the offset where the file content starts.

        hdr is the current header (hdr._offset will be set).

        """
        pos = NewAsciiFormat.LEN + hdr.namesize
        pos += NewAsciiFormat.calculate_padding(pos)
        # in this case _next_header_pos is the start of the passed hdr
        hdr._offset = self._next_header_pos + pos

    def _calculate_next_header_pos(self, hdr):
        """Calculate the position of the next header.

        hdr is the header which was just read.

        """
#        pos = NewAsciiFormat.LEN + hdr.namesize
#        pos += NewAsciiFormat.calculate_padding(pos)
        pos = hdr._offset + hdr.filesize
        pos += NewAsciiFormat.calculate_padding(hdr.filesize)
        self._next_header_pos = pos


class NewAsciiWriter(ArchiveWriter):
    """This class can write the new ascii format.

    "New" portable format: magic 070701

    """

    def __init__(self, fobj):
        super(NewAsciiWriter, self).__init__(fobj)

    def _create_header(self, st, filename):
        """Returns a cpio header.

        st is a stat structure (returned by os.stat). filename is
        the name of the file.

        """
        data = []
        data.append(st.st_ino)
        data.append(st.st_mode)
        data.append(st.st_uid)
        data.append(st.st_gid)
        data.append(st.st_nlink)
        data.append(st.st_mtime)
        data.append(st.st_size)
        data.append(os.major(st.st_dev))
        data.append(os.minor(st.st_dev))
        data.append(os.major(st.st_rdev))
        data.append(os.minor(st.st_rdev))
        data.append(len(filename) + 1)
        data.append(0)
        hdr = CpioHeader(NewAsciiFormat.MAGIC, data, no_convert=True)
        hdr.name = filename
        return hdr

    def append(self, filename, fobj=None):
        source = filename
        if fobj is not None:
            # this is only a good idea if it's a small file but we need
            # to know the size... (alternatively we can pass in an optional
            # filesize argument)
            source = StringIO(fobj.read())
            st = self._create_dummy_stat(0, 33188, 0, 0, 1, os.geteuid(),
                                         os.getegid(), len(source.getvalue()),
                                         0)
        else:
            filename = os.path.basename(filename)
            st = os.stat(source)
        hdr = self._create_header(st, filename)
        self._write_header(hdr, source)

    def _write_header(self, hdr, source):
        """Writes the header.

        hdr is the current header to be written and source is
        a file or file-like object which represents the file.

        """
        packed_hdr = pack(NewAsciiFormat.FORMAT, *hdr)
        self._fobj.write(packed_hdr)
        self._fobj.write(hdr.name + '\0')
        # write padding
        offset = NewAsciiFormat.LEN + hdr.namesize
        pad = NewAsciiFormat.calculate_padding(offset)
        if pad > 0:
            self._fobj.write('\0' * pad)
            self._bytes_written += pad
        for data in iter_read(source):
            self._fobj.write(data)
        # write padding
        pad = NewAsciiFormat.calculate_padding(hdr.filesize)
        if pad > 0:
            self._fobj.write('\0' * pad)
            self._bytes_written += pad
        self._bytes_written += NewAsciiFormat.LEN + hdr.namesize + hdr.filesize


class NewAsciiFormat(object):
    """Provides static methods and class attributes for the new ascii format"""
    MAGIC = '070701'
    # format and length of the "struct new_ascii_header" (see src/cpiohdr.h)
    FORMAT = '6s8s8s8s8s8s8s8s8s8s8s8s8s8s'
    LEN = 110

    @staticmethod
    def calculate_padding(offset):
        """Calculate the number of pad bytes based on offset."""
        return (4 - (offset % 4)) % 4


class CpioArchive(object):
    """The main interface to all cpio classes.

    Most users should use this class.
    Currently only reading is supported.

    """
    DEFAULT_READERS = {'070701': NewAsciiReader}

    def __init__(self, filename=None, fobj=None, use_mmap=False, **readers):
        """Constructs a new CpioArchive object.

        Either filename or fobj has to be specified but not
        both.

        Keyword arguments:
        filename -- a filename (default: '')
        fobj -- a file or file-like object (default: None)
        use_mmap -- if a filename is passed the file will be mmap'ed
                    (default: False)
        **readers -- user specified archive readers
                     (a "magic" => "reader_class" mapping)

        """
        self._fobj = FileWrapper(filename=filename, fobj=fobj,
                                 use_mmap=use_mmap)
        self._files = []
        self._reader = None
        self._readers = CpioArchive.DEFAULT_READERS.copy()
        self._readers.update(readers)
        self._init_reader()

    def _init_reader(self):
        """Initialize the archive reader based on the archive's magic.

        A ValueError is raised if no reader for the archive's magic
        is present.

        """
        self.magic = self._fobj.peek(6)
        reader_class = self._readers.get(self.magic, None)
        if reader_class is None:
            raise ValueError("magic: \'%s\' is not supported" % self.magic)
        self._reader = reader_class(self._fobj)

    def files(self):
        """Returns a list which contains all files of the cpio archive."""
        return list(self)

    def filenames(self):
        """Returns a list which contains all filenames of the cpio archive."""
        return [archive_file.hdr.name for archive_file in self]

    def find(self, filename):
        """Returns a CpioFile if filename is present in the archive.

        Otherwise None is returned.

        """
        for archive_file in self:
            if archive_file.hdr.name == filename:
                return archive_file
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._fobj.close()

    def __iter__(self):
        global TRAILER
        for archive_file in self._files:
            yield archive_file
        if not self._reader.trailer_seen:
            while True:
                archive_file = self._reader.next_file()
                if archive_file.hdr.name == TRAILER:
                    break
                self._files.append(archive_file)
                yield archive_file


def cpio_open(filename, use_mmap=False):
    """Opens a cpio archive for reading.

    filename is the path to the cpio archive.

    Keyword arguments:
    use_mmap -- if a filename is passed the file will be mmap'ed
                (default: False)

    """
    return CpioArchive(filename=filename, use_mmap=use_mmap)
