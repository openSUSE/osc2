import os
import unittest
import tempfile
import shutil

from osc.wc.package import Package
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

if __name__ == '__main__':
    unittest.main()
