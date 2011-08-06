import os
import unittest
import tempfile
import shutil
import stat

from lxml import etree

from osc.wc.package import (Package, FileSkipHandler, PackageUpdateState,
                            FileUpdateInfo, file_md5, is_binaryfile,
                            TransactionListener, FileConflictError,
                            FileCommitPolicy, PendingTransactionError)
from osc.wc.util import WCInconsistentError
from osc.source import Package as SourcePackage
from test.osctest import OscTest
from test.httptest import GET, PUT, POST


def suite():
    return unittest.makeSuite(TestPackage)


class TL(TransactionListener):
    def __init__(self, abort=True):
        self._begin = []
        self._finished = []
        self._transfer = []
        self._processed = {}
        self._abort = abort

    def begin(self, name, uinfo):
        self._begin.append(name)
        return not self._abort

    def finished(self, name, aborted=False, abort_reason=''):
        self._finished.append(name)

    def transfer(self, transfer_type, filename):
        self._transfer.append((transfer_type, filename))

    def processed(self, filename, new_state):
        self._processed[filename] = new_state


class TestPackage(OscTest):
    UPLOAD_REV = '<revision rev="repository"><srcmd5>empty</srcmd5></repository>'

    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = 'wc/test_package_fixtures'
        super(TestPackage, self).__init__(*args, **kwargs)

    def _check_md5(self, path, filename, md5, data=False):
        fname = os.path.join(path, filename)
        if data:
            fname = os.path.join(path, '.osc', 'data', filename)
        self.assertEqual(file_md5(fname), md5)

    def _exists(self, path, filename, store=False, data=False):
        if store and data:
            raise ValueError('store and data are mutually exclusive')
        fname = os.path.join(path, filename)
        if store:
            fname = os.path.join(path, '.osc', filename)
        elif data:
            fname = os.path.join(path, '.osc', 'data', filename)
        self.assertTrue(os.path.exists(fname))

    def _not_exists(self, path, filename, store=False, data=False):
        self.assertRaises(AssertionError, self._exists, path, filename,
                          store, data)

    def test1(self):
        """init a flat package dir"""
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp()
            pkg = Package.init(tmpdir, 'openSUSE:Tools', 'foo',
                               'https://api.opensuse.org')
            prj_fname = os.path.join(tmpdir, '.osc', '_project')
            self.assertTrue(os.path.exists(prj_fname))
            self.assertEqual(open(prj_fname, 'r').read(), 'openSUSE:Tools\n')
            pkg_fname = os.path.join(tmpdir, '.osc', '_package')
            self.assertTrue(os.path.exists(pkg_fname))
            self.assertEqual(open(pkg_fname, 'r').read(), 'foo\n')
            apiurl_fname = os.path.join(tmpdir, '.osc', '_apiurl')
            self.assertTrue(os.path.exists(apiurl_fname))
            self.assertEqual(open(apiurl_fname, 'r').read(),
                            'https://api.opensuse.org\n')
            files_fname = os.path.join(tmpdir, '.osc', '_files')
            self.assertTrue(os.path.exists(files_fname))
            self.assertEqual(open(files_fname, 'r').read(),
                             '<directory/>\n')
            data_dir = os.path.join(tmpdir, '.osc', 'data')
            self.assertTrue(os.path.exists(data_dir))
            self.assertEqual(pkg.project, 'openSUSE:Tools')
            self.assertEqual(pkg.name, 'foo')
            self.assertEqual(pkg.apiurl, 'https://api.opensuse.org')
        finally:
            if tmpdir is not None:
                shutil.rmtree(tmpdir)

    def test2(self):
        """init a package dir (no flat package)"""
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp()
            storedir = os.mkdir(os.path.join(tmpdir, 'foobar'))
            pkg = Package.init(tmpdir, 'openSUSE:Tools', 'foo',
                               'https://api.opensuse.org',
                               ext_storedir=storedir)
            prj_fname = os.path.join(tmpdir, '.osc', '_project')
            self.assertTrue(os.path.exists(prj_fname))
            self.assertEqual(open(prj_fname, 'r').read(), 'openSUSE:Tools\n')
            pkg_fname = os.path.join(tmpdir, '.osc', '_package')
            self.assertTrue(os.path.exists(pkg_fname))
            self.assertEqual(open(pkg_fname, 'r').read(), 'foo\n')
            apiurl_fname = os.path.join(tmpdir, '.osc', '_apiurl')
            self.assertTrue(os.path.exists(apiurl_fname))
            self.assertEqual(open(apiurl_fname, 'r').read(),
                            'https://api.opensuse.org\n')
            files_fname = os.path.join(tmpdir, '.osc', '_files')
            self.assertTrue(os.path.exists(files_fname))
            self.assertEqual(open(files_fname, 'r').read(),
                             '<directory/>\n')
            data_dir = os.path.join(tmpdir, '.osc', 'data')
            self.assertTrue(os.path.exists(data_dir))
            self.assertEqual(pkg.project, 'openSUSE:Tools')
            self.assertEqual(pkg.name, 'foo')
            self.assertEqual(pkg.apiurl, 'https://api.opensuse.org')
        finally:
            if tmpdir is not None:
                shutil.rmtree(tmpdir)

    def test3(self):
        """init existing wc"""
        path = self.fixture_file('prj', 'foo')
        self.assertRaises(ValueError, Package.init, path,
                          'prj', 'foo', 'http://localhost')

    def test4(self):
        """read package (no flat pkg)"""
        path = self.fixture_file('prj', 'bar')
        pkg = Package(path)
        self.assertEqual(pkg.project, 'prj')
        self.assertEqual(pkg.name, 'bar')
        self.assertEqual(pkg.apiurl, 'http://localhost')

    def test5(self):
        """read invalid package (no _package file)"""
        path = self.fixture_file('inv_foo1')
        self.assertRaises(WCInconsistentError, Package, path)

    def test6(self):
        """read invalid package (missing data file)"""
        path = self.fixture_file('inv_foo2')
        self.assertRaises(WCInconsistentError, Package, path)

    def test7(self):
        """read invalid package (corrupt _files xml)"""
        path = self.fixture_file('inv_foo3')
        self.assertRaises(WCInconsistentError, Package, path)

    def test8(self):
        """read valid package (flat pkg)"""
        path = self.fixture_file('foo')
        pkg = Package(path)
        self.assertEqual(pkg.project, 'prj')
        self.assertEqual(pkg.name, 'foo')
        self.assertEqual(pkg.apiurl, 'http://localhost')

    def test9(self):
        """test status"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('file1'), ' ')
        self.assertEqual(pkg.status('added'), 'A')
        self.assertEqual(pkg.status('added2'), 'A')
        self.assertEqual(pkg.status('delete'), 'D')
        self.assertEqual(pkg.status('delete_mod'), 'D')
        self.assertEqual(pkg.status('missing'), '!')
        self.assertEqual(pkg.status('modified'), 'M')
        self.assertEqual(pkg.status('skipped'), 'S')
        self.assertEqual(pkg.status('conflict'), 'C')
        self.assertEqual(pkg.status('nonexistent'), '?')
        self.assertEqual(pkg.status('unknown'), '?')

    @GET('http://localhost/source/prj/foo', file='foo_list1.xml')
    def test10(self):
        """test _calculate_updateinfo 1"""
        path = self.fixture_file('foo')
        pkg = Package(path)
        uinfo = pkg._calculate_updateinfo()
        self.assertEqual(uinfo.unchanged, ['file'])
        self.assertEqual(uinfo.added, ['added'])
        self.assertEqual(uinfo.deleted, [])
        self.assertEqual(uinfo.modified, [])
        self.assertEqual(uinfo.conflicted, [])
        self.assertEqual(uinfo.skipped, [])

    @GET('http://localhost/source/prj/foo?rev=2', file='foo_list2.xml')
    def test11(self):
        """test _calculate_updateinfo 2"""
        path = self.fixture_file('foo')
        pkg = Package(path)
        uinfo = pkg._calculate_updateinfo(revision='2')
        self.assertEqual(uinfo.unchanged, [])
        self.assertEqual(uinfo.added, ['added'])
        self.assertEqual(uinfo.deleted, [])
        self.assertEqual(uinfo.modified, ['file'])
        self.assertEqual(uinfo.conflicted, [])
        self.assertEqual(uinfo.skipped, [])

    @GET('http://localhost/source/prj/bar', file='bar_list1.xml')
    def test12(self):
        """test _calculate_updateinfo 3"""
        path = self.fixture_file('prj', 'bar')
        pkg = Package(path)
        uinfo = pkg._calculate_updateinfo()
        self.assertEqual(uinfo.unchanged, [])
        self.assertEqual(uinfo.added, ['added'])
        self.assertEqual(uinfo.deleted, ['baz'])
        self.assertEqual(uinfo.modified, ['file1'])
        self.assertEqual(uinfo.conflicted, [])
        self.assertEqual(uinfo.skipped, [])

    @GET('http://localhost/source/prj/bar', file='bar_list2.xml')
    def test13(self):
        """test _calculate_updateinfo 4"""
        path = self.fixture_file('prj', 'bar')
        pkg = Package(path)
        uinfo = pkg._calculate_updateinfo()
        self.assertEqual(uinfo.unchanged, ['file1'])
        self.assertEqual(uinfo.added, ['added'])
        self.assertEqual(uinfo.deleted, ['baz'])
        self.assertEqual(uinfo.modified, [])
        self.assertEqual(uinfo.conflicted, [])
        self.assertEqual(uinfo.skipped, [])

    @GET('http://localhost/source/foo/status1',
         file='status1_list1.xml')
    def test14(self):
        """test _calculate_updateinfo 5"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        uinfo = pkg._calculate_updateinfo()
        self.assertEqual(uinfo.unchanged, ['conflict', 'added2'])
        self.assertEqual(uinfo.added, [])
        self.assertEqual(uinfo.deleted, ['file1', 'delete', 'delete_mod'])
        self.assertEqual(uinfo.modified, ['missing', 'modified'])
        self.assertEqual(uinfo.conflicted, ['added'])
        self.assertEqual(uinfo.skipped, ['skipped'])

    @GET('http://localhost/source/foo/status1',
         file='status1_list1.xml')
    @GET('http://localhost/source/foo/status1',
         file='status1_list1.xml')
    def test15(self):
        """test _calculate_skips 1"""
        class FSH_1(FileSkipHandler):
            def skip(self, uinfo):
                # check for deepcopy
                uinfo.deleted.remove('file1')
                return ['modified'], []
        class FSH_2(FileSkipHandler):
            def skip(self, uinfo):
                return ['conflict'], ['skipped']
        path = self.fixture_file('status1')
        pkg = Package(path, [FSH_1()])
        uinfo = pkg._calculate_updateinfo()
        pkg._calculate_skips(uinfo)
        # only FSH_1
        self.assertEqual(uinfo.unchanged, ['conflict', 'added2'])
        self.assertEqual(uinfo.added, [])
        self.assertEqual(uinfo.deleted, ['file1', 'delete', 'delete_mod'])
        self.assertEqual(uinfo.modified, ['missing'])
        self.assertEqual(uinfo.conflicted, ['added'])
        self.assertEqual(uinfo.skipped, ['skipped', 'modified'])
        # FSH_1 and FSH_2
        uinfo = pkg._calculate_updateinfo()
        pkg.skip_handlers.append(FSH_2())
        pkg._calculate_skips(uinfo)
        self.assertEqual(uinfo.unchanged, ['added2'])
        self.assertEqual(uinfo.added, ['skipped'])
        self.assertEqual(uinfo.deleted, ['file1', 'delete', 'delete_mod'])
        self.assertEqual(uinfo.modified, ['missing'])
        self.assertEqual(uinfo.conflicted, ['added'])
        self.assertEqual(uinfo.skipped, ['modified', 'conflict'])

    @GET('http://localhost/source/foo/status1',
         file='status1_list1.xml')
    def test16(self):
        """test _calculate_skips 2"""
        class FSH(FileSkipHandler):
            def skip(self, uinfo):
                return [], ['skipped']
        path = self.fixture_file('status1')
        pkg = Package(path, [FSH()])
        uinfo = pkg._calculate_updateinfo()
        skipped = os.path.join(path, 'skipped')
        # touch empty file
        open(skipped, 'w').close()
        pkg._calculate_skips(uinfo)
        self.assertEqual(uinfo.unchanged, ['conflict', 'added2'])
        self.assertEqual(uinfo.added, [])
        self.assertEqual(uinfo.deleted, ['file1', 'delete', 'delete_mod'])
        self.assertEqual(uinfo.modified, ['missing', 'modified'])
        self.assertEqual(uinfo.conflicted, ['added', 'skipped'])
        self.assertEqual(uinfo.skipped, [])

    @GET('http://localhost/source/foo/status1',
         file='status1_list1.xml')
    def test17(self):
        """ test _calculate_skips 3 (invalid skip list)"""
        class FSH(FileSkipHandler):
            def skip(self, uinfo):
                return ['doesnotexist'], []
        path = self.fixture_file('status1')
        pkg = Package(path, [FSH()])
        uinfo = pkg._calculate_updateinfo()
        self.assertRaises(ValueError, pkg._calculate_skips, uinfo)

    @GET('http://localhost/source/prj/foo', file='foo_list1.xml')
    def test18(self):
        """test PackageUpdateState 1"""
        spkg = SourcePackage('prj', 'foo')
        path = self.fixture_file('foo')
        remote_xml = spkg.list()
        data = {'file': remote_xml.entry[0], 'added': remote_xml.entry[1]}
        uinfo = FileUpdateInfo(['file'], ['added'], [], [], [], [],
                               data, remote_xml)
        ustate = PackageUpdateState(path, uinfo=uinfo, file=' ')
        self.assertEqual(ustate.name, 'update')
        self.assertEqual(ustate.state, PackageUpdateState.STATE_DOWNLOADING)
        uinfo_new = ustate.uinfo
        self.assertEqual(uinfo_new.unchanged, uinfo.unchanged)
        self.assertEqual(uinfo_new.added, uinfo.added)
        self.assertEqual(uinfo_new.deleted, [])
        self.assertEqual(uinfo_new.modified, [])
        self.assertEqual(uinfo_new.conflicted, [])
        self.assertEqual(uinfo_new.skipped, [])
        xml = etree.tostring(uinfo_new.remote_xml, pretty_print=True)
        self.assertEqualFile(xml, 'foo_list1_ret.xml')
        self.assertEqual(ustate.filestates, {'file': ' '})
        # change state
        ustate.state = PackageUpdateState.STATE_UPDATING
        ustate = None
        # read state from file
        ustate = PackageUpdateState.read_state(path)
        self.assertIsNotNone(ustate)
        self.assertEqual(ustate.state, PackageUpdateState.STATE_UPDATING)
        uinfo_new = ustate.uinfo
        self.assertEqual(uinfo_new.unchanged, uinfo.unchanged)
        self.assertEqual(uinfo_new.added, uinfo.added)
        self.assertEqual(uinfo_new.deleted, [])
        self.assertEqual(uinfo_new.modified, [])
        self.assertEqual(uinfo_new.conflicted, [])
        self.assertEqual(uinfo_new.skipped, [])
        xml = etree.tostring(uinfo_new.remote_xml, pretty_print=True)
        self.assertEqualFile(xml, 'foo_list1_ret.xml')
        # test cleanup
        ustate = PackageUpdateState(path, uinfo=uinfo, file=' ')
        self.assertEqual(ustate.state, PackageUpdateState.STATE_DOWNLOADING)
        # test processed
        self.assertRaises(ValueError, ustate.processed, 'non_existent')
        ustate.processed('added', ' ')
        self.assertEqual(ustate.filestates, {'file': ' ', 'added': ' '})
        uinfo = ustate.uinfo
        self.assertEqual(uinfo.unchanged, ['file'])
        self.assertEqual(uinfo.added, [])
        # check if processed file was really removed
        ustate = PackageUpdateState.read_state(path)
        self.assertEqual(uinfo.unchanged, ['file'])
        self.assertEqual(uinfo.added, [])
        # test processed (remove from states)
        ustate.processed('file', None)
        self.assertEqual(ustate.filestates, {'added': ' '})
        uinfo = ustate.uinfo
        self.assertEqual(uinfo.unchanged, [])
        self.assertEqual(uinfo.added, [])

    @GET(('http://localhost/source/prj/foo/added'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='foo_added_file')
    def test19(self):
        """test _download"""
        path = self.fixture_file('foo_dl_state')
        ustate = PackageUpdateState.read_state(path)
        self.assertIsNotNone(ustate)
        uinfo = ustate.uinfo
        pkg = Package(path, finish_pending_transaction=False)
        pkg._download(ustate.location, uinfo.data, *uinfo.added)
        fname = os.path.join('foo_dl_state', '.osc', '_transaction',
                             'data', 'added')
        self.assertTrue(os.path.isfile(self.fixture_file(fname)))
        self.assertEqualFile('added file\n', fname)
        st = os.stat(self.fixture_file(fname))
        self.assertEqual(st.st_mtime, 1311512569)
        # default mode 644
        self.assertEqual(stat.S_IMODE(st.st_mode), 420)

    @GET('http://localhost/source/prj/update_1?rev=latest',
         file='update_1_files.xml')
    @GET(('http://localhost/source/prj/update_1/foo'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_1_foo')
    def test_update1(self):
        """test update"""
        path = self.fixture_file('update_1')
        pkg = Package(path)
        pkg.update()
        self._check_md5(path, 'foo', '50747782d12074c2c04ba7f90bf264c9')
        self._check_md5(path, 'foo', '50747782d12074c2c04ba7f90bf264c9',
                        data=True)
        self._check_md5(path, 'bar', '3a2c6e3cf6986d6e5af70cc467e4b29f')
        self._check_md5(path, 'bar', '3a2c6e3cf6986d6e5af70cc467e4b29f',
                        data=True)
        self._not_exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self._not_exists(path, '_transaction', store=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), ' ')
        self.assertEqual(pkg.status('foobar'), '?')

    @GET('http://localhost/source/prj/update_2?rev=latest',
         file='update_2_files.xml')
    @GET(('http://localhost/source/prj/update_2/foo'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_2_foo')
    def test_update2(self):
        """test update (conflict)"""
        path = self.fixture_file('update_2')
        pkg = Package(path)
        self.assertEqual(pkg.status('foo'), 'M')
        pkg.update()
        self._exists(path, 'foo')
        self._check_md5(path, 'foo.mine', '90aa8a29ecd8d33e7b099c0f108c026b')
        self._check_md5(path, 'foo', 'ab188d08913498abdd01479cbfd6814c',
                        data=True)
        self._check_md5(path, 'foo.revaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                        'ab188d08913498abdd01479cbfd6814c')
        self._check_md5(path, 'bar', '3a2c6e3cf6986d6e5af70cc467e4b29f')
        self._check_md5(path, 'bar', '3a2c6e3cf6986d6e5af70cc467e4b29f',
                        data=True)
        self._not_exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self._not_exists(path, '_transaction', store=True)
        self.assertEqual(pkg.status('foo'), 'C')
        self.assertEqual(pkg.status('bar'), ' ')
        self.assertEqual(pkg.status('foobar'), '?')

    @GET('http://localhost/source/prj/update_3?rev=latest',
         file='update_3_files.xml')
    @GET(('http://localhost/source/prj/update_3/foo'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_3_foo')
    def test_update3(self):
        """test update (text -> binary update)"""
        self.assertTrue(is_binaryfile(self.fixture_file('update_3_foo')))
        path = self.fixture_file('update_3')
        pkg = Package(path)
        pkg.update()
        self._check_md5(path, 'foo', '35fc275fa5646397dea2b8f061a4761f')
        self._check_md5(path, 'foo', '35fc275fa5646397dea2b8f061a4761f',
                        data=True)
        self._check_md5(path, 'bar', '3a2c6e3cf6986d6e5af70cc467e4b29f')
        self._check_md5(path, 'bar', '3a2c6e3cf6986d6e5af70cc467e4b29f',
                        data=True)
        self._not_exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self._not_exists(path, '_transaction', store=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), ' ')
        self.assertEqual(pkg.status('foobar'), '?')

    @GET('http://localhost/source/prj/update_4?rev=latest',
         file='update_4_files.xml')
    @GET(('http://localhost/source/prj/update_4/foo'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_4_foo')
    def test_update4(self):
        """test update (text -> binary update) (conflict)"""
        self.assertTrue(is_binaryfile(self.fixture_file('update_3_foo')))
        path = self.fixture_file('update_4')
        pkg = Package(path)
        pkg.update()
        self._exists(path, 'foo')
        self._check_md5(path, 'foo.mine', '90aa8a29ecd8d33e7b099c0f108c026b')
        self._check_md5(path, 'foo', '35fc275fa5646397dea2b8f061a4761f',
                        data=True)
        self._check_md5(path, 'foo.revaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                        '35fc275fa5646397dea2b8f061a4761f')
        self._check_md5(path, 'bar', '3a2c6e3cf6986d6e5af70cc467e4b29f')
        self._check_md5(path, 'bar', '3a2c6e3cf6986d6e5af70cc467e4b29f',
                        data=True)
        self._not_exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self._not_exists(path, '_transaction', store=True)
        self.assertEqual(pkg.status('foo'), 'C')
        self.assertEqual(pkg.status('bar'), ' ')
        self.assertEqual(pkg.status('foobar'), '?')

    @GET('http://localhost/source/prj/update_5?rev=latest',
         file='update_5_files.xml')
    @GET('http://localhost/source/prj/update_5?rev=latest',
         file='update_5_files.xml')
    @GET(('http://localhost/source/prj/update_5/added'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_5_added')
    @GET(('http://localhost/source/prj/update_5/asdf'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_5_asdf')
    def test_update5(self):
        """test update (adds + delete)"""
        path = self.fixture_file('update_5')
        tl = TL(abort=False)
        tl_abort = TL(abort=True)
        pkg = Package(path, transaction_listener=[tl, tl_abort])
        pkg.update()
        # first update was aborted
        tl = TL(abort=False)
        pkg = Package(path, transaction_listener=[tl])
        pkg.update()
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4')
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4',
                        data=True)
        self._check_md5(path, 'bar', '3a2c6e3cf6986d6e5af70cc467e4b29f')
        self._check_md5(path, 'bar', '3a2c6e3cf6986d6e5af70cc467e4b29f',
                        data=True)
        self._check_md5(path, 'added', '0e80600e984f2fdf3b341ebdea0b44ee')
        self._check_md5(path, 'added', '0e80600e984f2fdf3b341ebdea0b44ee',
                        data=True)
        self._check_md5(path, 'asdf', '0ca9f03c0b4cce5a5a317f297475cccf')
        self._check_md5(path, 'asdf', '0ca9f03c0b4cce5a5a317f297475cccf',
                        data=True)
        self._not_exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self._not_exists(path, '_transaction', store=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), ' ')
        self.assertEqual(pkg.status('added'), ' ')
        self.assertEqual(pkg.status('asdf'), ' ')
        self.assertEqual(pkg.status('foobar'), '?')
        # check transaction listener
        self.assertEqual(tl._begin, ['update'])
        self.assertEqual(tl._finished, ['update'])
        self.assertEqual(tl._transfer, [('download', 'added'),
                                        ('download', 'asdf')])
        self.assertEqual(set(tl._processed.keys()),
                         set(['added', 'asdf', 'foobar']))
        self.assertEqual(tl._processed['added'], ' ')
        self.assertEqual(tl._processed['asdf'], ' ')
        self.assertIsNone(tl._processed['foobar'])

    @GET('http://localhost/source/prj/update_6?rev=latest',
         file='update_6_files.xml')
    @GET(('http://localhost/source/prj/update_6/added'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_6_added')
    @GET(('http://localhost/source/prj/update_6/asdf'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_6_asdf')
    @GET('http://localhost/source/prj/update_6?rev=latest',
         file='update_6_files.xml')
    def test_update6(self):
        """test update (adds + skips + subsequent update call)"""
        class FSH(FileSkipHandler):
            def skip(self, uinfo):
                # skip all unchanged files
                return (uinfo.unchanged, [])
        path = self.fixture_file('update_6')
        pkg = Package(path, skip_handlers=[FSH()])
        pkg.update()
        self._check_md5(path, 'added', '0e80600e984f2fdf3b341ebdea0b44ee')
        self._check_md5(path, 'added', '0e80600e984f2fdf3b341ebdea0b44ee',
                        data=True)
        self._check_md5(path, 'asdf', '0ca9f03c0b4cce5a5a317f297475cccf')
        self._check_md5(path, 'asdf', '0ca9f03c0b4cce5a5a317f297475cccf',
                        data=True)
        self._not_exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self._not_exists(path, 'foo')
        self._not_exists(path, 'foo', data=True)
        # bar isn't deleted because the wc file is modified
        self._check_md5(path, 'bar', '9ed1175ea6a36a26e9a6cea4532f271c')
        self._not_exists(path, 'bar', data=True)
        self._not_exists(path, '_transaction', store=True)
        self.assertEqual(pkg.status('foo'), 'S')
        self.assertEqual(pkg.status('bar'), 'S')
        self.assertEqual(pkg.status('added'), ' ')
        self.assertEqual(pkg.status('asdf'), ' ')
        self.assertEqual(pkg.status('foobar'), '?')
        # subsequent update call
        pkg.update()

    @GET('http://localhost/source/prj/update_7?rev=latest',
         file='update_7_files.xml')
    def test_update7(self):
        """test update add (asdf already exists (state ?))"""
        path = self.fixture_file('update_7')
        pkg = Package(path)
        self.assertEqual(pkg.status('exists'), '?')
        self.assertRaises(FileConflictError, pkg.update)

    @GET('http://localhost/source/foo/status1?rev=latest',
         file='status1_list1.xml')
    def test_update8(self):
        """test update (raise FileConflictException)"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertRaises(FileConflictError, pkg.update)

    @GET('http://localhost/source/prj/update_9?rev=latest',
         file='update_9_files.xml')
    def test_update9(self):
        """test update (delete files)."""
        path = self.fixture_file('update_9')
        pkg = Package(path)
        pkg.update()
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4')
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4',
                        data=True)
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        # foobar was modified
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)

    @GET('http://localhost/source/prj/update_10?rev=latest',
         file='update_10_files.xml')
    def test_update10(self):
        """test update (delete files - bar is missing (state !))."""
        path = self.fixture_file('update_10')
        pkg = Package(path)
        self.assertEqual(pkg.status('bar'), '!')
        pkg.update()
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4')
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4',
                        data=True)
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        # foobar was modified
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), '?')
        self.assertEqual(pkg.status('foobar'), '?')

    @GET('http://localhost/source/prj/update_10?rev=latest',
         file='update_10_files1.xml')
    @GET(('http://localhost/source/prj/update_10/foo'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_3_foo')
    def test_update10_1(self):
        """test update (add - bar is missing (state !))."""
        path = self.fixture_file('update_10')
        pkg = Package(path)
        self.assertEqual(pkg.status('bar'), '!')
        pkg.update()
        self._check_md5(path, 'foo', '35fc275fa5646397dea2b8f061a4761f')
        self._check_md5(path, 'foo', '35fc275fa5646397dea2b8f061a4761f',
                        data=True)
        # bar still has state '!'
        self._not_exists(path, 'bar')
        self._exists(path, 'bar', data=True)
        # foobar was modified
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), '!')
        self.assertEqual(pkg.status('foobar'), '?')

    @GET('http://localhost/source/prj/update_10?rev=latest',
         file='update_10_files2.xml')
    @GET(('http://localhost/source/prj/update_10/foo'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_3_foo')
    @GET(('http://localhost/source/prj/update_10/bar'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_10_bar')
    def test_update10_2(self):
        """test update (bar is missing (state !) and remote bar modified)."""
        path = self.fixture_file('update_10')
        pkg = Package(path)
        self.assertEqual(pkg.status('bar'), '!')
        pkg.update()
        self._check_md5(path, 'foo', '35fc275fa5646397dea2b8f061a4761f')
        self._check_md5(path, 'foo', '35fc275fa5646397dea2b8f061a4761f',
                        data=True)
        self._check_md5(path, 'bar', '9cb33435b00b51668aaaf9e92032f2c8')
        self._check_md5(path, 'bar', '9cb33435b00b51668aaaf9e92032f2c8',
                        data=True)
        # foobar was modified
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), ' ')
        self.assertEqual(pkg.status('foobar'), '?')

    @GET('http://localhost/source/prj/update_11?rev=latest',
         file='update_11_files.xml')
    @GET(('http://localhost/source/prj/update_11/foo'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_11_foo')
    def test_update11(self):
        """test update (delete files marked for deletion)"""
        path = self.fixture_file('update_11')
        pkg = Package(path)
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), 'D')
        self.assertEqual(pkg.status('foobar'), 'D')
        pkg.update()
        # foo was merged
        self._check_md5(path, 'foo', 'a0569b11c94568c8e273e6fea90d642f')
        self._check_md5(path, 'foo', '0cd4f0c10ca24c7fbdbe9889651680b2',
                        data=True)
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        # foobar was modified before marked for deletion
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), '?')
        self.assertEqual(pkg.status('foobar'), '?')

    @GET('http://localhost/source/prj/update_12?rev=latest',
         file='update_12_files.xml')
    def test_update12(self):
        """test update (a skipped file was deleted from the server)"""
        path = self.fixture_file('update_12')
        pkg = Package(path)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), 'S')
        self.assertEqual(pkg.status('foobar'), 'D')
        pkg.update()
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4')
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4',
                        data=True)
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        # foobar was modified
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), '?')
        self.assertEqual(pkg.status('foobar'), '?')

    def test_update13(self):
        """test update (resume update, state: STATE_UPDATING)"""
        path = self.fixture_file('update_13')
        pkg = Package(path, finish_pending_transaction=False)
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), 'D')
        self.assertEqual(pkg.status('foobar'), 'D')
        pkg.update()
        # foo was merged
        self._check_md5(path, 'foo', 'a0569b11c94568c8e273e6fea90d642f')
        self._check_md5(path, 'foo', '0cd4f0c10ca24c7fbdbe9889651680b2',
                        data=True)
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        # foobar was modified before marked for deletion
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), '?')
        self.assertEqual(pkg.status('foobar'), '?')

    def test_update13_1(self):
        """test update (transaction is automatically finished)"""
        path = self.fixture_file('update_13')
        # finish pending transaction
        pkg = Package(path, finish_pending_transaction=True)
        # foo was merged
        self._check_md5(path, 'foo', 'a0569b11c94568c8e273e6fea90d642f')
        self._check_md5(path, 'foo', '0cd4f0c10ca24c7fbdbe9889651680b2',
                        data=True)
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        # foobar was modified before marked for deletion
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), '?')
        self.assertEqual(pkg.status('foobar'), '?')

    def test_update14(self):
        """test update (pending commit transaction)"""
        path = self.fixture_file('commit_6_resume')
        pkg = Package(path, finish_pending_transaction=False)
        self.assertRaises(PendingTransactionError, pkg.update)

    @GET('http://localhost/source/prj/commit_6?rev=latest',
         file='update_15_files.xml')
    def test_update15(self):
        """test update (rollback commit transaction)"""
        path = self.fixture_file('commit_6_uploading')
        pkg = Package(path, finish_pending_transaction=False)
        self._not_exists(path, 'foo')
        pkg.update()
        self._exists(path, 'foo')
        self.assertEqual(pkg.status('foo'), 'M')
        self._not_exists(path, 'some_tmp')

    @GET('http://localhost/source/prj/update_16?rev=latest',
         file='update_16_files.xml')
    @GET(('http://localhost/source/prj/update_16/file1'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='update_16_file1')
    def test_update16(self):
        """test update (file with state 'A' exists)"""
        path = self.fixture_file('update_16')
        pkg = Package(path)
        self.assertEqual(pkg.status('added'), 'A')
        self.assertEqual(pkg.status('file1'), ' ')
        pkg.update()
        self.assertEqual(pkg.status('added'), 'A')
        self.assertEqual(pkg.status('file1'), ' ')

    def test_resolved1(self):
        """test resolved"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('conflict'), 'C')
        pkg.resolved('conflict')
        self.assertEqual(pkg.status('conflict'), ' ')

    def test_resolved2(self):
        """test resolved (conflict modified)"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('conflict'), 'C')
        with open(os.path.join(path, 'conflict'), 'w') as f:
            f.write('modified and fixed')
        pkg.resolved('conflict')
        self.assertEqual(pkg.status('conflict'), 'M')

    def test_resolved3(self):
        """test resolved (raises ValueError)"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('file1'), ' ')
        self.assertRaises(ValueError, pkg.resolved, 'file1')
        self.assertEqual(pkg.status('file1'), ' ')

    def test_revert1(self):
        """test revert"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('file1'), ' ')
        pkg.revert('file1')
        self.assertEqual(pkg.status('file1'), ' ')
        self.assertEqual(pkg.status('added'), 'A')
        pkg.revert('added')
        self.assertEqual(pkg.status('added'), '?')
        # the file shouldn't be removed
        self._exists(path, 'added')
        self.assertEqual(pkg.status('modified'), 'M')
        pkg.revert('modified')
        self.assertEqual(pkg.status('modified'), ' ')
        self.assertEqual(pkg.status('missing'), '!')
        pkg.revert('missing')
        self.assertEqual(pkg.status('missing'), ' ')
        self.assertEqual(pkg.status('delete'), 'D')
        pkg.revert('delete')
        self.assertEqual(pkg.status('delete'), ' ')

    def test_revert2(self):
        """test revert (revert modified deleted file)"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('delete_mod'), 'D')
        pkg.revert('delete_mod')
        self.assertEqual(pkg.status('delete_mod'), 'M')
        # now replace the delete_mod file with the storefile
        pkg.revert('delete_mod')
        self.assertEqual(pkg.status('delete_mod'), ' ')

    def test_revert3(self):
        """test revert (raise ValueError)"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertRaises(ValueError, pkg.revert, 'conflict')
        self.assertRaises(ValueError, pkg.revert, 'unknown')
        self.assertRaises(ValueError, pkg.revert, 'nonexistent')
        self.assertRaises(ValueError, pkg.revert, 'skipped')

    def test_add1(self):
        """test add"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('unknown'), '?')
        pkg.add('unknown')
        self.assertEqual(pkg.status('unknown'), 'A')
        self._exists(path, 'unknown')
        self._not_exists(path, 'unknown', data=True)

    def test_add2(self):
        """test add (add deleted file again)"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('delete'), 'D')
        self._check_md5(path, 'delete', '2e7d76c347da6740e153d154b9064f33',
                        data=True)
        with open(os.path.join(path, 'delete'), 'w') as f:
            f.write('modified')
        pkg.add('delete')
        self.assertEqual(pkg.status('delete'), 'M')
        self._check_md5(path, 'delete', '2e7d76c347da6740e153d154b9064f33',
                        data=True)

    def test_add3(self):
        """test add already tracked file"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('added'), 'A')
        self.assertRaises(ValueError, pkg.add, 'added')
        self.assertEqual(pkg.status('modified'), 'M')
        self.assertRaises(ValueError, pkg.add, 'modified')
        # try to add non-existent file
        self.assertRaises(ValueError, pkg.add, 'nonexistent')
        # disallow path like filenames
        self._exists(path, '../update_5_files.xml')
        self.assertRaises(ValueError, pkg.add, '../update_5_files.xml')

    def test_add4(self):
        """test add (pending transaction (rollback possible))"""
        path = self.fixture_file('commit_6_uploading')
        pkg = Package(path, finish_pending_transaction=False)
        self.assertEqual(pkg.status('unversioned'), '?')
        pkg.add('unversioned')
        self.assertEqual(pkg.status('unversioned'), 'A')

    def test_add5(self):
        """test add (pending transaction (rollback not possible))"""
        path = self.fixture_file('commit_6_resume')
        pkg = Package(path, finish_pending_transaction=False)
        self.assertEqual(pkg.status('unversioned'), '?')
        self.assertRaises(PendingTransactionError, pkg.add, 'unversioned')
        self.assertEqual(pkg.status('unversioned'), '?')

    def test_remove1(self):
        """test remove unmodified file"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('file1'), ' ')
        pkg.remove('file1')
        self.assertEqual(pkg.status('file1'), 'D')
        self._not_exists(path, 'file1')
        self._exists(path, 'file1', data=True)

    def test_remove2(self):
        """test remove missing file"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('missing'), '!')
        pkg.remove('missing')
        self.assertEqual(pkg.status('missing'), 'D')
        self._not_exists(path, 'missing')
        self._exists(path, 'missing', data=True)

    def test_remove3(self):
        """test remove modified file"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('modified'), 'M')
        pkg.remove('modified')
        self.assertEqual(pkg.status('modified'), 'D')
        self._exists(path, 'modified')
        self._exists(path, 'modified', data=True)

    def test_remove4(self):
        """test remove already removed file"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('delete'), 'D')
        pkg.remove('delete')
        self.assertEqual(pkg.status('delete'), 'D')
        self._exists(path, 'delete', data=True)

    def test_remove5(self):
        """test remove added file"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('added'), 'A')
        pkg.remove('added')
        self.assertEqual(pkg.status('added'), 'D')
        self._not_exists(path, 'added')
        self._not_exists(path, 'added', data=True)

    def test_remove6(self):
        """test remove conflicted/skipped file (raises a ValueError)"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertEqual(pkg.status('conflict'), 'C')
        self.assertRaises(ValueError, pkg.remove, 'conflict')
        # hmm or should we allow to remove skipped files
        self.assertEqual(pkg.status('skipped'), 'S')
        self.assertRaises(ValueError, pkg.remove, 'skipped')

    def test_remove7(self):
        """test remove (raises a ValueError)"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        # try to remove untracked file
        self.assertEqual(pkg.status('unknown'), '?')
        self.assertRaises(ValueError, pkg.remove, 'unknown')
        self._exists(path, 'unknown')
        self.assertEqual(pkg.status('unknown'), '?')
        # try to remove non-existent file
        self.assertRaises(ValueError, pkg.remove, 'nonexistent')
        # disallow path like filenames
        self.assertRaises(ValueError, pkg.remove, '../update_7_files.xml')

    def test_remove8(self):
        """test remove (pending transaction (rollback possible))"""
        path = self.fixture_file('commit_6_uploading')
        pkg = Package(path, finish_pending_transaction=False)
        # file is already marked for deletion
        self.assertEqual(pkg.status('foobar'), 'D')
        pkg.remove('foobar')
        self.assertEqual(pkg.status('foobar'), 'D')

    def test_remove9(self):
        """test remove (pending transaction (rollback not possible))"""
        path = self.fixture_file('commit_6_resume')
        pkg = Package(path, finish_pending_transaction=False)
        self.assertEqual(pkg.status('foobar'), 'D')
        self.assertRaises(PendingTransactionError, pkg.remove, 'foobar')
        self.assertEqual(pkg.status('foobar'), 'D')

    def test_calculate_commitinfo1(self):
        """test _calculate_commitinfo"""
        path = self.fixture_file('update_2')
        pkg = Package(path)
        cinfo = pkg._calculate_commitinfo()
        self.assertEqual(cinfo.unchanged, ['bar', 'foobar'])
        self.assertEqual(cinfo.added, [])
        self.assertEqual(cinfo.deleted, [])
        self.assertEqual(cinfo.modified, ['foo'])
        self.assertEqual(cinfo.conflicted, [])

    def test_calculate_commitinfo2(self):
        """test _calculate_commitinfo (modified file)"""
        path = self.fixture_file('update_2')
        pkg = Package(path)
        cinfo = pkg._calculate_commitinfo('foo')
        self.assertEqual(cinfo.unchanged, ['bar', 'foobar'])
        self.assertEqual(cinfo.added, [])
        self.assertEqual(cinfo.deleted, [])
        self.assertEqual(cinfo.modified, ['foo'])
        self.assertEqual(cinfo.conflicted, [])

    def test_calculate_commitinfo3(self):
        """test _calculate_commitinfo (2 unchanged files)"""
        path = self.fixture_file('update_2')
        pkg = Package(path)
        cinfo = pkg._calculate_commitinfo('bar', 'foobar')
        self.assertEqual(cinfo.unchanged, ['foo', 'bar', 'foobar'])
        self.assertEqual(cinfo.added, [])
        self.assertEqual(cinfo.deleted, [])
        self.assertEqual(cinfo.modified, [])
        self.assertEqual(cinfo.conflicted, [])

    def test_calculate_commitinfo4(self):
        """test _calculate_commitinfo (missing file)"""
        path = self.fixture_file('update_10')
        pkg = Package(path)
        cinfo = pkg._calculate_commitinfo()
        self.assertEqual(cinfo.unchanged, ['foo'])
        self.assertEqual(cinfo.added, [])
        self.assertEqual(cinfo.deleted, [])
        self.assertEqual(cinfo.modified, ['foobar'])
        # bar is missing (state '!')
        self.assertEqual(cinfo.conflicted, ['bar'])

    def test_calculate_commitinfo5(self):
        """ test _calculate_commitinfo ()"""
        path = self.fixture_file('update_10')
        pkg = Package(path)
        cinfo = pkg._calculate_commitinfo('foo', 'foobar')
        # bar isn't explicitly committed (and at least one specific
        # file was specified when calling _calculate_commitinfo)
        self.assertEqual(cinfo.unchanged, ['foo', 'bar'])
        self.assertEqual(cinfo.added, [])
        self.assertEqual(cinfo.deleted, [])
        self.assertEqual(cinfo.modified, ['foobar'])
        self.assertEqual(cinfo.conflicted, [])

    def test_calculate_commitinfo6(self):
        """test _calculate_commitinfo (explicitly commit deleted files)"""
        path = self.fixture_file('update_11')
        pkg = Package(path)
        self._not_exists(path, 'bar')
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), 'D')
        self.assertEqual(pkg.status('foobar'), 'D')
        cinfo = pkg._calculate_commitinfo('bar')
        self.assertEqual(cinfo.unchanged, ['foo', 'foobar'])
        self.assertEqual(cinfo.added, [])
        self.assertEqual(cinfo.deleted, ['bar'])
        self.assertEqual(cinfo.modified, [])
        self.assertEqual(cinfo.conflicted, [])

    def test_calculate_commitinfo7(self):
        """test _calculate_commitinfo (deleted+modified files)"""
        path = self.fixture_file('update_11')
        pkg = Package(path)
        self._not_exists(path, 'bar')
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), 'D')
        self.assertEqual(pkg.status('foobar'), 'D')
        cinfo = pkg._calculate_commitinfo()
        self.assertEqual(cinfo.unchanged, [])
        self.assertEqual(cinfo.added, [])
        self.assertEqual(cinfo.deleted, ['bar', 'foobar'])
        self.assertEqual(cinfo.modified, ['foo'])
        self.assertEqual(cinfo.conflicted, [])

    def test_calculate_commitinfo8(self):
        """test _calculate_commitinfo (untracked files)"""
        path = self.fixture_file('update_1')
        pkg = Package(path)
        cinfo = pkg._calculate_commitinfo('untracked', 'nonexistent')
        self.assertEqual(cinfo.unchanged, ['foo', 'bar', 'foobar'])
        self.assertEqual(cinfo.added, [])
        self.assertEqual(cinfo.deleted, [])
        self.assertEqual(cinfo.modified, [])
        self.assertEqual(cinfo.conflicted, ['untracked', 'nonexistent'])

    def test_calculate_commitinfo9(self):
        """test _calculate_commitinfo (various states)"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        cinfo = pkg._calculate_commitinfo()
        self.assertEqual(cinfo.unchanged, ['file1', 'skipped'])
        self.assertEqual(cinfo.added, ['added', 'added2'])
        self.assertEqual(cinfo.deleted, ['delete', 'delete_mod'])
        self.assertEqual(cinfo.modified, ['modified'])
        self.assertEqual(cinfo.conflicted, ['missing', 'conflict'])

    def test_calculate_commitinfo10(self):
        """test _calculate_commitinfo (explicitly commit added file)"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        cinfo = pkg._calculate_commitinfo('added')
        # added2 isn't listed at all
        self.assertEqual(cinfo.unchanged, ['file1', 'delete', 'delete_mod',
                                           'missing', 'modified', 'skipped',
                                           'conflict'])
        self.assertEqual(cinfo.added, ['added'])
        self.assertEqual(cinfo.deleted, [])
        self.assertEqual(cinfo.modified, [])
        self.assertEqual(cinfo.conflicted, [])

    @GET('http://localhost/source/prj/update_2?rev=latest',
         file='commit_1_latest.xml')
    @POST('http://localhost/source/prj/update_2?cmd=sourcecommitfilelist',
          expfile='commit_1_lfiles.xml', file='commit_1_mfiles.xml')
    @PUT('http://localhost/source/prj/update_2/foo?rev=repository',
         expfile='commit_1_foo', text=UPLOAD_REV)
    @POST('http://localhost/source/prj/update_2?cmd=sourcecommitfilelist',
          expfile='commit_1_lfiles.xml', file='commit_1_files.xml')
    def test_commit1(self):
        """test commit (modified)"""
        path = self.fixture_file('update_2')
        pkg = Package(path)
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), ' ')
        self.assertEqual(pkg.status('foobar'), ' ')
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4',
                        data=True)
        pkg.commit()
        self._check_md5(path, 'foo', '90aa8a29ecd8d33e7b099c0f108c026b',
                        data=True)
        fname = os.path.join(path, '.osc', 'data', 'foo')
        st = os.stat(fname)
        self.assertEqual(st.st_mtime, 1311544490)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), ' ')
        self.assertEqual(pkg.status('foobar'), ' ')

    @GET('http://localhost/source/prj/update_11?rev=latest',
         file='commit_2_latest.xml')
    @POST('http://localhost/source/prj/update_11?cmd=sourcecommitfilelist',
          expfile='commit_2_lfiles.xml', file='commit_2_mfiles.xml')
    @PUT('http://localhost/source/prj/update_11/foo?rev=repository',
         expfile='commit_2_foo', text=UPLOAD_REV)
    @POST('http://localhost/source/prj/update_11?cmd=sourcecommitfilelist',
          expfile='commit_2_lfiles.xml', file='commit_2_files.xml')
    def test_commit2(self):
        """test commit (modified + deleted)"""
        path = self.fixture_file('update_11')
        pkg = Package(path)
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), 'D')
        self.assertEqual(pkg.status('foobar'), 'D')
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4',
                        data=True)
        pkg.commit()
        self._check_md5(path, 'foo', '5fb9f8bed64fb741e760b0db312b7c5a',
                        data=True)
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), '?')
        self.assertEqual(pkg.status('foobar'), '?')

    @GET('http://localhost/source/prj/update_11?rev=latest',
         file='commit_2_latest.xml')
    @GET('http://localhost/source/prj/update_11?rev=latest',
         file='commit_2_latest.xml')
    @POST('http://localhost/source/prj/update_11?cmd=sourcecommitfilelist',
          expfile='commit_3_lfiles.xml', file='commit_2_mfiles.xml')
    @PUT('http://localhost/source/prj/update_11/foo?rev=repository',
         expfile='commit_2_foo', text=UPLOAD_REV)
    @POST('http://localhost/source/prj/update_11?cmd=sourcecommitfilelist',
          expfile='commit_3_lfiles.xml', file='commit_3_files.xml')
    def test_commit3(self):
        """test commit (only commit modified file)"""
        tl = TL(abort=False)
        tl_abort = TL(abort=True)
        path = self.fixture_file('update_11')
        pkg = Package(path, transaction_listener=[tl, tl_abort])
        # commit is aborted because a transaction listener returned False
        pkg.commit('foo')
        tl = TL(abort=False)
        pkg = Package(path, transaction_listener=[tl])
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), 'D')
        self.assertEqual(pkg.status('foobar'), 'D')
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4',
                        data=True)
        pkg.commit('foo')
        self._check_md5(path, 'foo', '5fb9f8bed64fb741e760b0db312b7c5a',
                        data=True)
        self._not_exists(path, 'bar')
        self._exists(path, 'bar', data=True)
        # foobar was modified before deletion
        self._exists(path, 'foobar')
        self._exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), 'D')
        self.assertEqual(pkg.status('foobar'), 'D')
        # check transaction listener
        self.assertEqual(tl._begin, ['commit'])
        self.assertEqual(tl._finished, ['commit'])
        self.assertEqual(tl._transfer, [('upload', 'foo')])
        self.assertEqual(tl._processed.keys(), ['foo'])
        self.assertEqual(tl._processed['foo'], ' ')

    @GET('http://localhost/source/prj/update_11?rev=latest',
         file='commit_2_latest.xml')
    @POST('http://localhost/source/prj/update_11?cmd=sourcecommitfilelist',
          expfile='commit_4_lfiles.xml', file='commit_4_files.xml')
    def test_commit4(self):
        """test commit (only commit deleted file bar)"""
        path = self.fixture_file('update_11')
        pkg = Package(path)
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), 'D')
        self.assertEqual(pkg.status('foobar'), 'D')
        pkg.commit('bar')
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        # foobar was modified before deletion
        self._exists(path, 'foobar')
        self._exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), '?')
        self.assertEqual(pkg.status('foobar'), 'D')

    @GET('http://localhost/source/prj/update_11?rev=latest',
         file='commit_2_latest.xml')
    @POST('http://localhost/source/prj/update_11?cmd=sourcecommitfilelist',
          expfile='commit_4_lfiles.xml', file='commit_4_files.xml')
    def test_commit5(self):
        """test commit (only commit deleted file bar)"""
        class FCP_1(FileCommitPolicy):
            def apply(self, cinfo):
                # foobar should be treated as unchanged
                return ['foo'], []
        class FCP_2(FileCommitPolicy):
            def apply(self, cinfo):
                # foo should be treated as unchanged
                return ['foobar'], []
        path = self.fixture_file('update_11')
        pkg = Package(path, commit_policies=[FCP_1(), FCP_2()])
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), 'D')
        self.assertEqual(pkg.status('foobar'), 'D')
        # only bar is committed due to FileCommitPolicy
        pkg.commit()
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        # foobar was modified before deletion
        self._exists(path, 'foobar')
        self._exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), '?')
        self.assertEqual(pkg.status('foobar'), 'D')

    @GET('http://localhost/source/prj/commit_6?rev=latest',
         file='commit_6_latest.xml')
    @POST('http://localhost/source/prj/commit_6?cmd=sourcecommitfilelist',
          expfile='commit_6_lfiles1.xml', file='commit_6_mfiles1.xml')
    @PUT('http://localhost/source/prj/commit_6/foo?rev=repository',
         expfile='commit_6_foo', text=UPLOAD_REV)
    @PUT('http://localhost/source/prj/commit_6/added?rev=repository',
         expfile='commit_6_added', text=UPLOAD_REV)
    @POST('http://localhost/source/prj/commit_6?cmd=sourcecommitfilelist',
          expfile='commit_6_lfiles1.xml', file='commit_6_files1.xml')
    def test_commit6(self):
        """test commit (commit added, modified and deleted files)."""
        path = self.fixture_file('commit_6')
        pkg = Package(path)
        self.assertEqual(pkg.status('foo'), 'M')
        self.assertEqual(pkg.status('bar'), 'D')
        self.assertEqual(pkg.status('foobar'), 'D')
        self.assertEqual(pkg.status('missing'), '!')
        self.assertEqual(pkg.status('added'), 'A')
        self._check_md5(path, 'foo', '0e04f7f7fa4ec3fbbb907ebbe4dc9bc4',
                        data=True)
        pkg.commit('foo', 'bar', 'foobar', 'added')
        self._check_md5(path, 'foo', '5fb9f8bed64fb741e760b0db312b7c5a',
                        data=True)
        self._exists(path, 'added')
        self._exists(path, 'added', data=True)
        self._check_md5(path, 'added', '8dee900466b680b0717524878e42bf04',
                        data=True)
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        # foobar was modified before deletion
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), '?')
        self.assertEqual(pkg.status('foobar'), '?')
        self.assertEqual(pkg.status('missing'), '!')
        self.assertEqual(pkg.status('added'), ' ')

    def test_commit7(self):
        """test commit (fails because a missing file should be committed)"""
        path = self.fixture_file('commit_6')
        pkg = Package(path)
        self.assertRaises(FileConflictError, pkg.commit)

    def test_commit8(self):
        """test commit (missing and conflicted files present)"""
        path = self.fixture_file('status1')
        pkg = Package(path)
        self.assertRaises(FileConflictError, pkg.commit)

    def test_commit9(self):
        """test commit (resume commit, PackageCommitState.STATE_COMMITTING)"""
        path = self.fixture_file('commit_6_resume')
        pkg = Package(path, finish_pending_transaction=False)
        pkg.commit('foo', 'bar', 'foobar', 'added')
        self._check_md5(path, 'foo', '5fb9f8bed64fb741e760b0db312b7c5a',
                        data=True)
        self._exists(path, 'added')
        self._exists(path, 'added', data=True)
        self._check_md5(path, 'added', '8dee900466b680b0717524878e42bf04',
                        data=True)
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        # foobar was modified before deletion
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), '?')
        self.assertEqual(pkg.status('foobar'), '?')
        self.assertEqual(pkg.status('missing'), '!')
        self.assertEqual(pkg.status('added'), ' ')

    def test_commit9_1(self):
        """test commit (finish pending transaction)"""
        path = self.fixture_file('commit_6_resume')
        # finish pending transaction
        pkg = Package(path, finish_pending_transaction=True)
        self._check_md5(path, 'foo', '5fb9f8bed64fb741e760b0db312b7c5a',
                        data=True)
        self._exists(path, 'added')
        self._exists(path, 'added', data=True)
        self._check_md5(path, 'added', '8dee900466b680b0717524878e42bf04',
                        data=True)
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)
        # foobar was modified before deletion
        self._exists(path, 'foobar')
        self._not_exists(path, 'foobar', data=True)
        self.assertEqual(pkg.status('foo'), ' ')
        self.assertEqual(pkg.status('bar'), '?')
        self.assertEqual(pkg.status('foobar'), '?')
        self.assertEqual(pkg.status('missing'), '!')
        self.assertEqual(pkg.status('added'), ' ')

    def test_commit10(self):
        """test commit (pending update transaction)"""
        path = self.fixture_file('update_13')
        pkg = Package(path, finish_pending_transaction=False)
        self.assertRaises(PendingTransactionError, pkg.commit)

    def test_commit11(self):
        """test commit (finish pending commit transaction)"""
        path = self.fixture_file('commit_6_uploading')
        self._not_exists(path, 'foo')
        pkg = Package(path, finish_pending_transaction=True)
        self._exists(path, 'foo')
        self.assertEqual(pkg.status('foo'), 'M')
        self._not_exists(path, 'some_tmp')

if __name__ == '__main__':
    unittest.main()
