import os
import unittest
import tempfile
import shutil

from osc.wc.package import Package, FileSkipHandler
from osc.wc.util import WCInconsistentError
from test.osctest import OscTest
from test.httptest import GET

def suite():
    return unittest.makeSuite(TestPackage)

class TestPackage(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = 'wc/test_package_fixtures'
        super(TestPackage, self).__init__(*args, **kwargs)

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

    @GET('http://localhost/source/prj/foo', file='foo_list2.xml')
    def test11(self):
        """test _calculate_updateinfo 2"""
        path = self.fixture_file('foo')
        pkg = Package(path)
        uinfo = pkg._calculate_updateinfo()
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
        self.assertEqual(uinfo.unchanged, ['conflict'])
        self.assertEqual(uinfo.added, [])
        self.assertEqual(uinfo.deleted, ['file1', 'delete', 'delete_mod'])
        self.assertEqual(uinfo.modified, ['modified'])
        self.assertEqual(uinfo.conflicted, ['added', 'missing'])
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
        self.assertEqual(uinfo.unchanged, ['conflict'])
        self.assertEqual(uinfo.added, [])
        self.assertEqual(uinfo.deleted, ['file1', 'delete', 'delete_mod'])
        self.assertEqual(uinfo.modified, [])
        self.assertEqual(uinfo.conflicted, ['added', 'missing'])
        self.assertEqual(uinfo.skipped, ['skipped', 'modified'])
        # FSH_1 and FSH_2
        uinfo = pkg._calculate_updateinfo()
        pkg.skip_handlers.append(FSH_2())
        pkg._calculate_skips(uinfo)
        self.assertEqual(uinfo.unchanged, [])
        self.assertEqual(uinfo.added, ['skipped'])
        self.assertEqual(uinfo.deleted, ['file1', 'delete', 'delete_mod'])
        self.assertEqual(uinfo.modified, [])
        self.assertEqual(uinfo.conflicted, ['added', 'missing'])
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
        self.assertEqual(uinfo.unchanged, ['conflict'])
        self.assertEqual(uinfo.added, [])
        self.assertEqual(uinfo.deleted, ['file1', 'delete', 'delete_mod'])
        self.assertEqual(uinfo.modified, ['modified'])
        self.assertEqual(uinfo.conflicted, ['added', 'missing', 'skipped'])
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

if __name__ == '__main__':
    unittest.main()
