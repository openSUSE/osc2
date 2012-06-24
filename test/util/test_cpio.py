import os
import mmap
import unittest
# use StringIO instead of cStringIO because seek will be overridden
from StringIO import StringIO

from osc.util.cpio import (FileWrapper, NewAsciiReader, CpioError,
                           NewAsciiWriter, CpioArchive, cpio_open)
from test.osctest import OscTest


def suite():
    return unittest.makeSuite(TestCpio)


class TestCpio(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = os.path.join('util', 'test_cpio_fixtures')
        super(TestCpio, self).__init__(*args, **kwargs)

    def test1(self):
        """test FileWrapper with filename (no mmap)"""
        fname = self.fixture_file('filewrapper1.txt')
        f = FileWrapper(filename=fname, use_mmap=False)
        self.assertFalse(isinstance(f._fobj, mmap.mmap))
        self.assertTrue(f.is_seekable())
        self.assertEqual(f.tell(), 0)
        self.assertEqual(f.read(1), 'T')
        self.assertEqual(f.tell(), 1)
        # seek to position 0 again
        f.seek(0)
        self.assertEqual(f.read(5), 'This ')
        self.assertEqual(f.tell(), 5)
        # read rest of the file
        self.assertEqual(f.read(), 'is a simple\ntext file.\n')
        f.close()

    def test2(self):
        """test FileWrapper with file object (no mmap)"""
        fname = self.fixture_file('filewrapper1.txt')
        with open(fname, 'r') as fobj:
            f = FileWrapper(fobj=fobj, use_mmap=False)
            self.assertFalse(isinstance(f._fobj, mmap.mmap))
            self.assertTrue(f.is_seekable())
            self.assertEqual(f.tell(), 0)
            self.assertEqual(f.read(1), 'T')
            self.assertEqual(f.tell(), 1)
            # seek to position 0 again
            f.seek(-1, os.SEEK_CUR)
            self.assertEqual(f.tell(), 0)
            self.assertEqual(f.read(5), 'This ')
            self.assertEqual(f.tell(), 5)
            # read rest of the file
            self.assertEqual(f.read(), 'is a simple\ntext file.\n')
            f.close()
            # the fobj should not be closed in this case
            self.assertFalse(fobj.closed)

    def test3(self):
        """test FileWrapper with filename (mmap=True)"""
        fname = self.fixture_file('filewrapper1.txt')
        f = FileWrapper(filename=fname, use_mmap=True)
        self.assertTrue(isinstance(f._fobj, mmap.mmap))
        self.assertTrue(f.is_seekable())
        self.assertEqual(f.tell(), 0)
        self.assertEqual(f.read(1), 'T')
        self.assertEqual(f.tell(), 1)
        # seek to position 0 again
        f.seek(0, os.SEEK_SET)
        self.assertEqual(f.tell(), 0)
        self.assertEqual(f.read(5), 'This ')
        self.assertEqual(f.tell(), 5)
        # read rest of the file
        self.assertEqual(f.read(), 'is a simple\ntext file.\n')
        f.close()

    def test4(self):
        """test FileWrapper with file object (mmap=True) (raises ValueError)"""
        fname = self.fixture_file('filewrapper1.txt')
        with open(fname, 'r') as fobj:
            self.assertRaises(ValueError, FileWrapper, fobj=fobj,
                              use_mmap=True)
            self.assertFalse(fobj.closed)

    def test5(self):
        """test FileWrapper with unseekable file object"""
        sio = StringIO('Simple test file')
        sio.seek = None
        f = FileWrapper(fobj=sio, use_mmap=False)
        self.assertFalse(f.is_seekable())
        self.assertFalse(isinstance(f._fobj, mmap.mmap))
        self.assertEqual(f.tell(), 0)
        self.assertEqual(f.read(3), 'Sim')
        self.assertEqual(f.tell(), 3)
        # seeking backward is not supposed to work
        self.assertRaises(IOError, f.seek, 0, os.SEEK_SET)
        self.assertRaises(IOError, f.seek, -2, os.SEEK_SET)
        self.assertRaises(IOError, f.seek, -2, os.SEEK_CUR)
        self.assertRaises(IOError, f.seek, 5, os.SEEK_END)
        # seeking forward (absolute) does work (skip 'pl')
        f.seek(5, os.SEEK_SET)
        self.assertEqual(f.read(3), 'e t')
        # seeking forward (relative) does work (skip 'est')
        f.seek(3, os.SEEK_CUR)
        # read the rest of the file
        self.assertEqual(f.read(), ' file')
        f.close()
        # sio should not be closed
        self.assertFalse(sio.closed)

    def test6(self):
        """test FileWrapper (invalid arguments)"""
        sio = StringIO('foo')
        fname = self.fixture_file('filewrapper1.txt')
        self.assertRaises(ValueError, FileWrapper)
        self.assertRaises(ValueError, FileWrapper, filename=fname, fobj=sio)

    def test7(self):
        """test FileWrapper's peek method"""
        fname = self.fixture_file('filewrapper1.txt')
        with open(fname, 'r') as fobj:
            f = FileWrapper(fobj=fobj, use_mmap=False)
            self.assertFalse(isinstance(f._fobj, mmap.mmap))
            self.assertEqual(f.peek(3), 'Thi')
            self.assertEqual(f.tell(), 0)
            # seeking is not allowed unless all peek'ed bytes are read
            self.assertRaises(IOError, f.seek, 8, os.SEEK_SET)
            self.assertEqual(f.read(2), 'Th')
            self.assertEqual(f.tell(), 2)
            # seek is still not possible (1 peek byte left)
            self.assertRaises(IOError, f.seek, 8, os.SEEK_SET)
            self.assertEqual(f.read(2), 'is')
            self.assertEqual(f.tell(), 4)
            # seek is possible
            f.seek(8, os.SEEK_SET)
            self.assertEqual(f.read(), 'a simple\ntext file.\n')

    def test8(self):
        """test NewAsciiReader (no padding after file contents)"""
        fname = self.fixture_file('new_ascii_reader1.cpio')
        f = FileWrapper(filename=fname)
        archive_reader = NewAsciiReader(f)
        hdr = archive_reader.next_header()
        self.assertEqual(hdr.magic, '070701')
        self.assertEqual(hdr.ino, 1788112)
        self.assertEqual(hdr.mode, 33188)
        self.assertEqual(hdr.uid, 1000)
        self.assertEqual(hdr.gid, 100)
        self.assertEqual(hdr.nlink, 1)
        self.assertEqual(hdr.mtime, 1340459653)
        self.assertEqual(hdr.filesize, 28)
        self.assertEqual(hdr.dev_maj, 8)
        self.assertEqual(hdr.dev_min, 10)
        self.assertEqual(hdr.rdev_maj, 0)
        self.assertEqual(hdr.rdev_min, 0)
        self.assertEqual(hdr.namesize, 17)
        self.assertEqual(hdr.chksum, 0)
        self.assertEqual(hdr.name, 'filewrapper1.txt')
#        self.assertTrue(hdr.is_regular_file())
        # next header is trailer
        hdr = archive_reader.next_header()
        self.assertEqual(hdr.magic, '070701')
        self.assertEqual(hdr.ino, 0)
        self.assertEqual(hdr.mode, 0)
        self.assertEqual(hdr.uid, 0)
        self.assertEqual(hdr.gid, 0)
        self.assertEqual(hdr.nlink, 1)
        self.assertEqual(hdr.mtime, 0)
        self.assertEqual(hdr.filesize, 0)
        self.assertEqual(hdr.dev_maj, 0)
        self.assertEqual(hdr.dev_min, 0)
        self.assertEqual(hdr.rdev_maj, 0)
        self.assertEqual(hdr.rdev_min, 0)
        self.assertEqual(hdr.namesize, 11)
        self.assertEqual(hdr.chksum, 0)
        self.assertEqual(hdr.name, 'TRAILER!!!')
#        self.assertFalse(hdr.is_regular_file())
        # no more headers available
        self.assertIsNone(archive_reader.next_header())

    def test9(self):
        """test NewAsciiReader (no padding except for trailer)"""
        # nearly identical to test7 but the filename differ
        fname = self.fixture_file('new_ascii_reader2.cpio')
        f = FileWrapper(filename=fname)
        archive_reader = NewAsciiReader(f)
        hdr = archive_reader.next_header()
        self.assertEqual(hdr.magic, '070701')
        self.assertEqual(hdr.ino, 1788112)
        self.assertEqual(hdr.mode, 33188)
        self.assertEqual(hdr.uid, 1000)
        self.assertEqual(hdr.gid, 100)
        self.assertEqual(hdr.nlink, 1)
        self.assertEqual(hdr.mtime, 1340459653)
        self.assertEqual(hdr.filesize, 28)
        self.assertEqual(hdr.dev_maj, 8)
        self.assertEqual(hdr.dev_min, 10)
        self.assertEqual(hdr.rdev_maj, 0)
        self.assertEqual(hdr.rdev_min, 0)
        self.assertEqual(hdr.namesize, 14)
        self.assertEqual(hdr.chksum, 0)
        self.assertEqual(hdr.name, 'filewrapper_1')
#        self.assertTrue(hdr.is_regular_file())
        # next header is trailer
        hdr = archive_reader.next_header()
        self.assertEqual(hdr.magic, '070701')
        self.assertEqual(hdr.ino, 0)
        self.assertEqual(hdr.mode, 0)
        self.assertEqual(hdr.uid, 0)
        self.assertEqual(hdr.gid, 0)
        self.assertEqual(hdr.nlink, 1)
        self.assertEqual(hdr.mtime, 0)
        self.assertEqual(hdr.filesize, 0)
        self.assertEqual(hdr.dev_maj, 0)
        self.assertEqual(hdr.dev_min, 0)
        self.assertEqual(hdr.rdev_maj, 0)
        self.assertEqual(hdr.rdev_min, 0)
        self.assertEqual(hdr.namesize, 11)
        self.assertEqual(hdr.chksum, 0)
        self.assertEqual(hdr.name, 'TRAILER!!!')
#        self.assertFalse(hdr.is_regular_file())
        # no more headers available
        self.assertIsNone(archive_reader.next_header())

    def test10(self):
        """test NewAsciiReader (unseekable file object)"""
        # identical to test8 but this time a unseekable fobj is used
        fname = self.fixture_file('new_ascii_reader2.cpio')
        sio = StringIO(open(fname, 'r').read())
        sio.seek = None
        f = FileWrapper(fobj=sio)
        archive_reader = NewAsciiReader(f)
        hdr = archive_reader.next_header()
        self.assertEqual(hdr.magic, '070701')
        self.assertEqual(hdr.ino, 1788112)
        self.assertEqual(hdr.mode, 33188)
        self.assertEqual(hdr.uid, 1000)
        self.assertEqual(hdr.gid, 100)
        self.assertEqual(hdr.nlink, 1)
        self.assertEqual(hdr.mtime, 1340459653)
        self.assertEqual(hdr.filesize, 28)
        self.assertEqual(hdr.dev_maj, 8)
        self.assertEqual(hdr.dev_min, 10)
        self.assertEqual(hdr.rdev_maj, 0)
        self.assertEqual(hdr.rdev_min, 0)
        self.assertEqual(hdr.namesize, 14)
        self.assertEqual(hdr.chksum, 0)
        self.assertEqual(hdr.name, 'filewrapper_1')
#        self.assertTrue(hdr.is_regular_file())
        # next header is trailer
        hdr = archive_reader.next_header()
        self.assertEqual(hdr.magic, '070701')
        self.assertEqual(hdr.ino, 0)
        self.assertEqual(hdr.mode, 0)
        self.assertEqual(hdr.uid, 0)
        self.assertEqual(hdr.gid, 0)
        self.assertEqual(hdr.nlink, 1)
        self.assertEqual(hdr.mtime, 0)
        self.assertEqual(hdr.filesize, 0)
        self.assertEqual(hdr.dev_maj, 0)
        self.assertEqual(hdr.dev_min, 0)
        self.assertEqual(hdr.rdev_maj, 0)
        self.assertEqual(hdr.rdev_min, 0)
        self.assertEqual(hdr.namesize, 11)
        self.assertEqual(hdr.chksum, 0)
        self.assertEqual(hdr.name, 'TRAILER!!!')
#        self.assertFalse(hdr.is_regular_file())
        # no more headers available
        self.assertIsNone(archive_reader.next_header())

    def test11(self):
        """test NewAsciiReader (2 files)"""
        fname = self.fixture_file('new_ascii_reader3.cpio')
        f = FileWrapper(filename=fname)
        archive_reader = NewAsciiReader(f)
        # check file foo
        hdr = archive_reader.next_header()
        self.assertEqual(hdr.magic, '070701')
        self.assertEqual(hdr.ino, 1788176)
        self.assertEqual(hdr.mode, 33188)
        self.assertEqual(hdr.uid, 1000)
        self.assertEqual(hdr.gid, 100)
        self.assertEqual(hdr.nlink, 1)
        self.assertEqual(hdr.mtime, 1340493596)
        self.assertEqual(hdr.filesize, 9)
        self.assertEqual(hdr.dev_maj, 8)
        self.assertEqual(hdr.dev_min, 10)
        self.assertEqual(hdr.rdev_maj, 0)
        self.assertEqual(hdr.rdev_min, 0)
        self.assertEqual(hdr.namesize, 4)
        self.assertEqual(hdr.chksum, 0)
        self.assertEqual(hdr.name, 'foo')
#        self.assertTrue(hdr.is_regular_file())
        # check file foobar
        hdr = archive_reader.next_header()
        self.assertEqual(hdr.magic, '070701')
        self.assertEqual(hdr.ino, 1788110)
        self.assertEqual(hdr.mode, 33188)
        self.assertEqual(hdr.uid, 1000)
        self.assertEqual(hdr.gid, 100)
        self.assertEqual(hdr.nlink, 1)
        self.assertEqual(hdr.mtime, 1340493602)
        self.assertEqual(hdr.filesize, 18)
        self.assertEqual(hdr.dev_maj, 8)
        self.assertEqual(hdr.dev_min, 10)
        self.assertEqual(hdr.rdev_maj, 0)
        self.assertEqual(hdr.rdev_min, 0)
        self.assertEqual(hdr.namesize, 7)
        self.assertEqual(hdr.chksum, 0)
        self.assertEqual(hdr.name, 'foobar')
#        self.assertTrue(hdr.is_regular_file())
        # next header is trailer
        hdr = archive_reader.next_header()
        self.assertEqual(hdr.magic, '070701')
        self.assertEqual(hdr.ino, 0)
        self.assertEqual(hdr.mode, 0)
        self.assertEqual(hdr.uid, 0)
        self.assertEqual(hdr.gid, 0)
        self.assertEqual(hdr.nlink, 1)
        self.assertEqual(hdr.mtime, 0)
        self.assertEqual(hdr.filesize, 0)
        self.assertEqual(hdr.dev_maj, 0)
        self.assertEqual(hdr.dev_min, 0)
        self.assertEqual(hdr.rdev_maj, 0)
        self.assertEqual(hdr.rdev_min, 0)
        self.assertEqual(hdr.namesize, 11)
        self.assertEqual(hdr.chksum, 0)
        self.assertEqual(hdr.name, 'TRAILER!!!')
#        self.assertFalse(hdr.is_regular_file())
        # no more headers available
        self.assertIsNone(archive_reader.next_header())

    def test12(self):
        """test NewAsciiReader read file content"""
        # identical to test10 but this time we read the file contents
        fname = self.fixture_file('new_ascii_reader3.cpio')
        f = FileWrapper(filename=fname)
        archive_reader = NewAsciiReader(f)
        # check file foo
        archv_file = archive_reader.next_file()
        self.assertEqual(archv_file.hdr.magic, '070701')
        self.assertEqual(archv_file.hdr.ino, 1788176)
        self.assertEqual(archv_file.hdr.mode, 33188)
        self.assertEqual(archv_file.hdr.uid, 1000)
        self.assertEqual(archv_file.hdr.gid, 100)
        self.assertEqual(archv_file.hdr.nlink, 1)
        self.assertEqual(archv_file.hdr.mtime, 1340493596)
        self.assertEqual(archv_file.hdr.filesize, 9)
        self.assertEqual(archv_file.hdr.dev_maj, 8)
        self.assertEqual(archv_file.hdr.dev_min, 10)
        self.assertEqual(archv_file.hdr.rdev_maj, 0)
        self.assertEqual(archv_file.hdr.rdev_min, 0)
        self.assertEqual(archv_file.hdr.namesize, 4)
        self.assertEqual(archv_file.hdr.chksum, 0)
        self.assertEqual(archv_file.hdr.name, 'foo')
        # read file content
        self.assertEqual(archv_file.read(4), 'file')
        self.assertEqual(archv_file.read(), ' foo\n')
#        self.assertTrue(archv_file.hdr.is_regular_file())
        # check file foobar
        archv_file = archive_reader.next_file()
        self.assertEqual(archv_file.hdr.magic, '070701')
        self.assertEqual(archv_file.hdr.ino, 1788110)
        self.assertEqual(archv_file.hdr.mode, 33188)
        self.assertEqual(archv_file.hdr.uid, 1000)
        self.assertEqual(archv_file.hdr.gid, 100)
        self.assertEqual(archv_file.hdr.nlink, 1)
        self.assertEqual(archv_file.hdr.mtime, 1340493602)
        self.assertEqual(archv_file.hdr.filesize, 18)
        self.assertEqual(archv_file.hdr.dev_maj, 8)
        self.assertEqual(archv_file.hdr.dev_min, 10)
        self.assertEqual(archv_file.hdr.rdev_maj, 0)
        self.assertEqual(archv_file.hdr.rdev_min, 0)
        self.assertEqual(archv_file.hdr.namesize, 7)
        self.assertEqual(archv_file.hdr.chksum, 0)
        self.assertEqual(archv_file.hdr.name, 'foobar')
        # read file content
        self.assertEqual(archv_file.read(13), 'This is file\n')
        self.assertEqual(archv_file.read(), 'bar.\n')
#        self.assertTrue(archv_file.hdr.is_regular_file())
        # next header is trailer
        archv_file = archive_reader.next_file()
        self.assertEqual(archv_file.hdr.magic, '070701')
        self.assertEqual(archv_file.hdr.ino, 0)
        self.assertEqual(archv_file.hdr.mode, 0)
        self.assertEqual(archv_file.hdr.uid, 0)
        self.assertEqual(archv_file.hdr.gid, 0)
        self.assertEqual(archv_file.hdr.nlink, 1)
        self.assertEqual(archv_file.hdr.mtime, 0)
        self.assertEqual(archv_file.hdr.filesize, 0)
        self.assertEqual(archv_file.hdr.dev_maj, 0)
        self.assertEqual(archv_file.hdr.dev_min, 0)
        self.assertEqual(archv_file.hdr.rdev_maj, 0)
        self.assertEqual(archv_file.hdr.rdev_min, 0)
        self.assertEqual(archv_file.hdr.namesize, 11)
        self.assertEqual(archv_file.hdr.chksum, 0)
        self.assertEqual(archv_file.hdr.name, 'TRAILER!!!')
#        self.assertFalse(archv_file.hdr.is_regular_file())
        # no more headers available
        self.assertIsNone(archive_reader.next_file())

    def test13(self):
        """test NewAsciiReader read files"""
        fname = self.fixture_file('new_ascii_reader3.cpio')
        f = FileWrapper(filename=fname)
        archive_reader = NewAsciiReader(f)
        foo_file = archive_reader.next_file()
        self.assertEqual(foo_file.hdr.name, 'foo')
        foobar_file = archive_reader.next_file()
        self.assertEqual(foobar_file.hdr.name, 'foobar')
        # read around in both files
        self.assertEqual(foobar_file.read(7), 'This is')
        self.assertEqual(foo_file.read(3), 'fil')
        self.assertEqual(foobar_file.read(6), ' file\n')
        # read rest of file foo
        self.assertEqual(foo_file.read(), 'e foo\n')
        # read rest of file foobar
        self.assertEqual(foobar_file.read(), 'bar.\n')

    def test14(self):
        """test NewAsciiReader read files (unseekable fobj)"""
        # the read sequence is identical to test12
        # but the expected results are different because the fobj
        # is not seekable
        fname = self.fixture_file('new_ascii_reader3.cpio')
        sio = StringIO(open(fname, 'r').read())
        sio.seek = None
        f = FileWrapper(fobj=sio)
        self.assertFalse(f.is_seekable())
        archive_reader = NewAsciiReader(f)
        foo_file = archive_reader.next_file()
        self.assertEqual(foo_file.hdr.name, 'foo')
        foobar_file = archive_reader.next_file()
        self.assertEqual(foobar_file.hdr.name, 'foobar')
        # read around in both files
        self.assertEqual(foobar_file.read(7), 'This is')
        self.assertRaises(IOError, foo_file.read, 3)
        self.assertEqual(foobar_file.read(6), ' file\n')
        # read rest of file foo
        self.assertRaises(IOError, foo_file.read)
        # read rest of file foobar
        self.assertEqual(foobar_file.read(), 'bar.\n')

    def test15(self):
        """test CpioFile's copyin method (dest is directory)"""
        dest = self.fixture_file('copyin')
        os.mkdir(dest)
        fname = self.fixture_file('new_ascii_reader3.cpio')
        f = FileWrapper(filename=fname)
        archive_reader = NewAsciiReader(f)
        # copyin file foo
        archive_file = archive_reader.next_file()
        archive_file.copyin(dest)
        fname = self.fixture_file('copyin', archive_file.hdr.name)
        self.assertTrue(os.path.isfile(fname))
        self.assertEqualFile('file foo\n', fname)
        # check mode, mtime, uid and gid
        st = os.stat(fname)
        self.assertEqual(st.st_mode, 33188)
        self.assertEqual(st.st_mtime, 1340493596)
        self.assertEqual(st.st_uid, 1000)
        self.assertEqual(st.st_gid, 100)
        # copyin file foobar
        archive_file = archive_reader.next_file()
        archive_file.copyin(dest)
        fname = self.fixture_file('copyin', archive_file.hdr.name)
        self.assertTrue(os.path.isfile(fname))
        self.assertEqualFile('This is file\nbar.\n', fname)
        # check mode, mtime, uid and gid
        st = os.stat(fname)
        self.assertEqual(st.st_mode, 33188)
        self.assertEqual(st.st_mtime, 1340493602)
        self.assertEqual(st.st_uid, 1000)
        self.assertEqual(st.st_gid, 100)

    def test16(self):
        """test CpioFile's copyin method unseekable fobj (dest is directory)"""
        # identical to test14 except that the input is not seekable
        dest = self.fixture_file('copyin')
        os.mkdir(dest)
        fname = self.fixture_file('new_ascii_reader3.cpio')
        sio = StringIO(open(fname, 'r').read())
        f = FileWrapper(fobj=sio)
        archive_reader = NewAsciiReader(f)
        # copyin file foo
        archive_file = archive_reader.next_file()
        archive_file.copyin(dest)
        fname = self.fixture_file('copyin', archive_file.hdr.name)
        self.assertTrue(os.path.isfile(fname))
        self.assertEqualFile('file foo\n', fname)
        # check mode, mtime, uid and gid
        st = os.stat(fname)
        self.assertEqual(st.st_mode, 33188)
        self.assertEqual(st.st_mtime, 1340493596)
        self.assertEqual(st.st_uid, 1000)
        self.assertEqual(st.st_gid, 100)
        # copyin file foobar
        archive_file = archive_reader.next_file()
        archive_file.copyin(dest)
        fname = self.fixture_file('copyin', archive_file.hdr.name)
        self.assertTrue(os.path.isfile(fname))
        self.assertEqualFile('This is file\nbar.\n', fname)
        # check mode, mtime, uid and gid
        st = os.stat(fname)
        self.assertEqual(st.st_mode, 33188)
        self.assertEqual(st.st_mtime, 1340493602)
        self.assertEqual(st.st_uid, 1000)
        self.assertEqual(st.st_gid, 100)

    def test17(self):
        """test CpioFile's copyin method (dest is a file-like object)"""
        fname = self.fixture_file('new_ascii_reader3.cpio')
        f = FileWrapper(filename=fname)
        archive_reader = NewAsciiReader(f)
        # copyin file foo
        sio = StringIO()
        archive_file = archive_reader.next_file()
        archive_file.copyin(sio)
        self.assertEqual(sio.getvalue(), 'file foo\n')
        # copyin file foobar
        sio = StringIO()
        archive_file = archive_reader.next_file()
        archive_file.copyin(sio)
        self.assertEqual(sio.getvalue(), 'This is file\nbar.\n')

    def test18(self):
        """test NewAsciiWriter's append method"""
        fname = self.fixture_file('foo')
        sio = StringIO()
        archive_writer = NewAsciiWriter(sio)
        archive_writer.append(fname)
        self.assertEqual(archive_writer._bytes_written, 128)
        fname = self.fixture_file('new_ascii_writer_foo_header')
        # we can only compare the sizes because the inode, dev_maj and dev_min
        # of the foo file has changed (because it was copied to a
        # tmpdir - that's how our testsuite works...)
        self.assertEqual(len(sio.getvalue()), len(open(fname, 'r').read()))
        # check manually...
        sio.seek(0, os.SEEK_SET)
        f = FileWrapper(fobj=sio)
        archive_reader = NewAsciiReader(f)
        hdr = archive_reader.next_header()
        self.assertEqual(hdr.magic, '070701')
#        self.assertEqual(hdr.ino, 1788176)
        self.assertEqual(hdr.mode, 33188)
        self.assertEqual(hdr.uid, 1000)
        self.assertEqual(hdr.gid, 100)
        self.assertEqual(hdr.nlink, 1)
        self.assertEqual(hdr.mtime, 1340493596)
        self.assertEqual(hdr.filesize, 9)
#        self.assertEqual(hdr.dev_maj, 8)
#        self.assertEqual(hdr.dev_min, 10)
        self.assertEqual(hdr.rdev_maj, 0)
        self.assertEqual(hdr.rdev_min, 0)
        self.assertEqual(hdr.namesize, 4)
        self.assertEqual(hdr.chksum, 0)
        self.assertEqual(hdr.name, 'foo')

    def test19(self):
        """test NewAsciiWriter's append method (fobj)"""
        fname = self.fixture_file('foo')
        sio_fobj = StringIO(open(fname, 'r').read())
        sio = StringIO()
        archive_writer = NewAsciiWriter(sio)
        archive_writer.append('foo', fobj=sio_fobj)
        self.assertEqual(archive_writer._bytes_written, 128)
        self.assertEqualFile(sio.getvalue(),
                             'new_ascii_writer_foo_header_default')

    def test20(self):
        """test NewAsciiWriter's _append_trailer method"""
        sio = StringIO()
        archive_writer = NewAsciiWriter(sio)
        archive_writer._append_trailer()
        self.assertEqual(archive_writer._bytes_written, 124)
        self.assertEqualFile(sio.getvalue(),
                             'new_ascii_writer_trailer_header')

    def test21(self):
        """test NewAsciiWriter's copyout method"""
        fname = self.fixture_file('foo')
        sio_fobj = StringIO(open(fname, 'r').read())
        sio = StringIO()
        archive_writer = NewAsciiWriter(sio)
        archive_writer.append('foo', fobj=sio_fobj)
        archive_writer.copyout()
        self.assertEqual(archive_writer._bytes_written, 512)
        fname = self.fixture_file('new_ascii_writer.cpio')
        self.assertEqual(len(sio.getvalue()), len(open(fname, 'r').read()))

    def test22(self):
        """test NewAsciiWriter's copyout method"""
        # write a complete cpio archive
        f = StringIO()
        archive_writer = NewAsciiWriter(f)
        sio = StringIO('This is a small\ntest file.\n')
        archive_writer.append('test1', fobj=sio)
        sio = StringIO('Yet another\ntest file.\n')
        archive_writer.append('test2', fobj=sio)
        sio = StringIO('The last test file.\n')
        archive_writer.append('last_file', fobj=sio)
        archive_writer.copyout()
        self.assertEqual(archive_writer._bytes_written, 1024)
        self.assertEqualFile(f.getvalue(), 'new_ascii_writer_sio.cpio')

    def test23(self):
        """test CpioArchive class"""
        fname = self.fixture_file('cpio_archive.cpio')
        archive = CpioArchive(filename=fname)
        filenames = ['bar', 'file1', 'foo']
        contents = ['File bar\nhas some\ncontent...\n',
                    'This is yet\nanother\nfile.\n',
                    'file foo\n']
        for archive_file in archive:
            self.assertEqual(archive_file.hdr.name, filenames.pop(0))
            self.assertEqual(archive_file.read(), contents.pop(0))
        self.assertEqual(archive.filenames(), ['bar', 'file1', 'foo'])
        self.assertEqual(len(archive.files()), 3)
        # read file bar again (no content because the whole file was already
        # read)
        archive_file = archive.find('bar')
        self.assertIsNotNone(archive_file)
        self.assertEqual(archive_file.read(), '')
        # try to find non existent file
        self.assertIsNone(archive.find('unknown'))
        self.assertEqual(archive.magic, '070701')

    def test24(self):
        """test CpioArchive class unseekable input 1"""
        fname = self.fixture_file('cpio_archive.cpio')
        sio = StringIO(open(fname, 'r').read())
        sio.seek = None
        archive = CpioArchive(fobj=sio)
        filenames = ['bar', 'file1', 'foo']
        contents = ['File bar\nhas some\ncontent...\n',
                    'This is yet\nanother\nfile.\n',
                    'file foo\n']
        for archive_file in archive:
            self.assertEqual(archive_file.hdr.name, filenames.pop(0))
            self.assertEqual(archive_file.read(), contents.pop(0))
        self.assertEqual(archive.filenames(), ['bar', 'file1', 'foo'])
        self.assertEqual(len(archive.files()), 3)
        # read file bar again
        archive_file = archive.find('bar')
        self.assertIsNotNone(archive_file)
        # the empty str because the file was already completely read
        # => no seek is made and no IOError is raised
        self.assertEqual(archive_file.read(), '')
        # try to find non existent file
        self.assertIsNone(archive.find('unknown'))
        self.assertEqual(archive.magic, '070701')

    def test25(self):
        """test CpioArchive class unseekable input 2"""
        fname = self.fixture_file('cpio_archive.cpio')
        sio = StringIO(open(fname, 'r').read())
        sio.seek = None
        archive = CpioArchive(fobj=sio)
        # get the second file in the archive
        archive_file = archive.find('file1')
        self.assertIsNotNone(archive_file)
        self.assertEqual(archive_file.read(4), 'This')
        # now get the first file in the archive
        archive_file = archive.find('bar')
        self.assertIsNotNone(archive_file)
        # a read raises an IOError because we cannot seek back
        self.assertRaises(IOError, archive_file.read)
        # read rest from the second file
        archive_file = archive.find('file1')
        self.assertIsNotNone(archive_file)
        self.assertEqual(archive_file.read(), ' is yet\nanother\nfile.\n')
        # finally read the last file
        archive_file = archive.find('foo')
        self.assertIsNotNone(archive_file)
        self.assertEqual(archive_file.read(), 'file foo\n')
        self.assertEqual(archive.magic, '070701')

    def test26(self):
        """test CpioArchive's __enter__, __exit__ methods"""
        # identical to test23 except that cpio_open is used and
        # the CpioArchive is used via context manager
        fname = self.fixture_file('cpio_archive.cpio')
        with cpio_open(fname) as archive:
            filenames = ['bar', 'file1', 'foo']
            contents = ['File bar\nhas some\ncontent...\n',
                        'This is yet\nanother\nfile.\n',
                        'file foo\n']
            for archive_file in archive:
                self.assertEqual(archive_file.hdr.name, filenames.pop(0))
                self.assertEqual(archive_file.read(), contents.pop(0))
            self.assertEqual(archive.filenames(), ['bar', 'file1', 'foo'])
            self.assertEqual(len(archive.files()), 3)
            # read file bar again (no content because the whole file was already
            # read)
            archive_file = archive.find('bar')
            self.assertIsNotNone(archive_file)
            self.assertEqual(archive_file.read(), '')
            # try to find non existent file
            self.assertIsNone(archive.find('unknown'))
            self.assertEqual(archive.magic, '070701')

if __name__ == '__main__':
    unittest.main()
