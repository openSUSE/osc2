import os
import tempfile
import unittest

from test.osctest import OscTest
from osc2.wc.util import (WCFormatVersionError, wc_is_project, wc_is_package,
                          wc_read_project, wc_read_package, wc_read_apiurl,
                          WCLock, wc_parent, wc_init)


def suite():
    return unittest.makeSuite(TestWCUtil)


class TestWCUtil(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = os.path.join('wc', 'test_util_fixtures')
        super(TestWCUtil, self).__init__(*args, **kwargs)

    def test1(self):
        """test wc_is_project"""
        path = self.fixture_file('project')
        self.assertTrue(wc_is_project(path))

    def test2(self):
        """test wc_is_project"""
        path = self.fixture_file('package')
        self.assertFalse(wc_is_project(path))

    def test3(self):
        """test wc_is_project"""
        self.assertFalse(wc_is_project('/'))

    def test4(self):
        """test wc_is_package"""
        path = self.fixture_file('package')
        self.assertTrue(wc_is_package(path))

    def test5(self):
        """test wc_is_package"""
        path = self.fixture_file('project')
        self.assertFalse(wc_is_package(path))

    def test6(self):
        """test wc_is_package"""
        self.assertFalse(wc_is_package('/'))

    def test7(self):
        """test wc_read_project"""
        path = self.fixture_file('project')
        self.assertEqual(wc_read_project(path), 'project')

    def test8(self):
        """test wc_read_project"""
        path = self.fixture_file('package')
        self.assertEqual(wc_read_project(path), 'foobar')

    def test9(self):
        """test wc_read_project"""
        path = self.fixture_file('apiurl')
        self.assertRaises(ValueError, wc_read_project, path)

    def test10(self):
        """test wc_read_project"""
        self.assertRaises(ValueError, wc_read_project, '/')

    def test11(self):
        """test wc_read_package"""
        path = self.fixture_file('package')
        self.assertEqual(wc_read_package(path), 'package')

    def test12(self):
        """test wc_read_package"""
        path = self.fixture_file('project')
        self.assertRaises(ValueError, wc_read_package, path)

    def test13(self):
        """test wc_read_package"""
        path = self.fixture_file('apiurl')
        self.assertRaises(ValueError, wc_read_package, path)

    def test14(self):
        """test wc_read_package"""
        self.assertRaises(ValueError, wc_read_package, '/')

    def test15(self):
        """test wc_read_apiurl"""
        path = self.fixture_file('project')
        self.assertEqual(wc_read_apiurl(path), 'http://localhost')

    def test16(self):
        """test wc_read_apiurl"""
        path = self.fixture_file('package')
        self.assertEqual(wc_read_apiurl(path), 'https://localhost')

    def test17(self):
        """test wc_read_apiurl"""
        path = self.fixture_file('apiurl')
        self.assertEqual(wc_read_apiurl(path), 'http://localhost')

    def test18(self):
        """test wc_read_apiurl"""
        self.assertRaises(ValueError, wc_read_apiurl, '/')

    def test19(self):
        """test WCLock class"""
        path = self.fixture_file('lock')
        lock = os.path.join(path, '.osc', 'wc.lock')
        wc = WCLock(path)
        self.assertFalse(wc.has_lock())
        wc.lock()
        self.assertTrue(wc.has_lock())
        self.assertTrue(os.path.isfile(lock))
        wc.unlock()
        self.assertFalse(wc.has_lock())
        self.assertFalse(os.path.exists(lock))

    def test20(self):
        """test WCLock class (unlock without lock)"""
        path = self.fixture_file('lock')
        wc = WCLock(path)
        self.assertRaises(RuntimeError, wc.unlock)

    def test21(self):
        """test WCLock class (double lock)"""
        path = self.fixture_file('lock')
        lock = os.path.join(path, '.osc', 'wc.lock')
        wc = WCLock(path)
        wc.lock()
        self.assertTrue(os.path.isfile(lock))
        self.assertRaises(RuntimeError, wc.lock)
        # wc is still locked
        self.assertTrue(wc.has_lock())
        wc.unlock()
        self.assertFalse(os.path.exists(lock))

    def test22(self):
        """test wc_parent (package)"""
        path = self.fixture_file('prj1', 'added')
        self.assertTrue(os.path.isdir(path))
        par_dir = wc_parent(path)
        self.assertIsNotNone(par_dir)
        self.assertTrue(wc_is_project(par_dir))
        self.assertEqual(wc_read_project(par_dir), 'prj1')

    def test23(self):
        """test wc_parent (cwd)"""
        pkg_path = self.fixture_file('prj1', 'added')
        path = os.curdir
        cwd = os.getcwd()
        try:
            os.chdir(pkg_path)
            self.assertTrue(os.path.isdir(path))
            par_dir = wc_parent(path)
            self.assertIsNotNone(par_dir)
            self.assertTrue(wc_is_project(par_dir))
            self.assertEqual(wc_read_project(par_dir), 'prj1')
        finally:
            os.chdir(cwd)

    def test24(self):
        """test wc_parent (package/file)"""
        path = self.fixture_file('prj1', 'added', 'foo')
        self.assertTrue(os.path.isfile(path))
        par_dir = wc_parent(path)
        self.assertIsNotNone(par_dir)
        self.assertTrue(wc_is_package(par_dir))
        self.assertEqual(wc_read_package(par_dir), 'added')

    def test25(self):
        """test wc_parent (package/non_existent)"""
        path = self.fixture_file('prj1', 'added', 'non_existent')
        self.assertFalse(os.path.exists(path))
        par_dir = wc_parent(path)
        self.assertIsNotNone(par_dir)
        self.assertTrue(wc_is_package(par_dir))
        self.assertEqual(wc_read_package(par_dir), 'added')

    def test26(self):
        """test wc_parent (package - no parent)"""
        path = self.fixture_file('package')
        self.assertTrue(os.path.isdir(path))
        par_dir = wc_parent(path)
        self.assertIsNone(par_dir)

    def test27(self):
        """test wc_parent (package/non_existent - no parent)"""
        path = self.fixture_file('package', 'non_existent')
        self.assertFalse(os.path.exists(path))
        par_dir = wc_parent(path)
        self.assertIsNotNone(par_dir)
        self.assertTrue(wc_is_package(par_dir))
        self.assertEqual(wc_read_package(par_dir), 'package')

    def test28(self):
        """test wc_parent cwd (package/non_existent - no parent)"""
        pkg_path = self.fixture_file('package')
        path = 'non_existent'
        cwd = os.getcwd()
        try:
            os.chdir(pkg_path)
            self.assertFalse(os.path.exists(path))
            par_dir = wc_parent(path)
            self.assertIsNotNone(par_dir)
            self.assertTrue(wc_is_package(par_dir))
            self.assertEqual(wc_read_package(par_dir), 'package')
        finally:
            os.chdir(cwd)

    def test29(self):
        """test wc_parent (project - no parent)"""
        path = self.fixture_file('project')
        self.assertTrue(os.path.isdir(path))
        par_dir = wc_parent(path)
        self.assertIsNone(par_dir)

    def test_wc_init1(self):
        """simple init wc"""
        path = self.fixture_file('init')
        self._not_exists(path, '.osc')
        wc_init(path)
        self._exists(path, '.osc')
        storedir = self.fixture_file('init', '.osc')
        self.assertFalse(os.path.islink(storedir))
        self.assertTrue(os.path.isdir(storedir))
        self.assertEqual(sorted(os.listdir(storedir)), ['_version', 'data'])

    def test_wc_init2(self):
        """simple init wc external, empty storedir"""
        path = self.fixture_file('init')
        # we do not have to remove storedir later (cleanup happens
        # after each testcase)
        storedir = tempfile.mkdtemp(dir=self._tmp_fixtures)
        storedir_lnk = self.fixture_file(path, '.osc')
        self._not_exists(path, '.osc')
        wc_init(path, ext_storedir=storedir)
        self._exists(path, '.osc')
        self.assertTrue(os.path.islink(storedir_lnk))
        self.assertTrue(os.path.isdir(storedir_lnk))
        self.assertEqual(sorted(os.listdir(storedir)),
                         ['_version', 'data'])

    def test_wc_init3(self):
        """init wc external, non-empty storedir"""
        path = self.fixture_file('init')
        storedir = self.fixture_file('storedir_non_empty')
        storedir_lnk = self.fixture_file(path, '.osc')
        self._not_exists(path, '.osc')
        wc_init(path, ext_storedir=storedir)
        self._exists(path, '.osc')
        self.assertTrue(os.path.islink(storedir_lnk))
        self.assertTrue(os.path.isdir(storedir_lnk))
        contents = ['_apiurl', '_files', '_package', '_project', '_version',
                    'data']
        self.assertEqual(sorted(os.listdir(storedir)), contents)

    def test_wc_init4(self):
        """init wc external storedir with unsupported format"""
        path = self.fixture_file('init')
        self._not_exists(path, '.osc')
        storedir = self.fixture_file('storedir_inv_format')
        self.assertRaises(WCFormatVersionError, wc_init, path,
                          ext_storedir=storedir)
        self._not_exists(path, '.osc')

    def test_wc_init5(self):
        """init wc external storedir does not exist"""
        path = self.fixture_file('init')
        self._not_exists(path, '.osc')
        storedir = self.fixture_file('nonexistent')
        self.assertFalse(os.path.exists(storedir))
        self.assertRaises(ValueError, wc_init, path, ext_storedir=storedir)
        self._not_exists(path, '.osc')
        self.assertFalse(os.path.exists(storedir))

    def test_wc_init6(self):
        """init wc (create new directory)"""
        path = self.fixture_file('init_nonexistent')
        self.assertFalse(os.path.exists(path))
        wc_init(path)
        self.assertTrue(os.path.exists(path))

    def test_wc_init7(self):
        """init wc (create new directory, nonexistent ext storedir)"""
        path = self.fixture_file('init_nonexistent')
        self.assertFalse(os.path.exists(path))
        storedir = self.fixture_file('nonexistent')
        self.assertFalse(os.path.exists(storedir))
        self.assertRaises(ValueError, wc_init, path, ext_storedir=storedir)
        self.assertFalse(os.path.exists(path))

    def test_wc_init8(self):
        """init wc (create new directory, ext storedir invalid format)"""
        path = self.fixture_file('init_nonexistent')
        self.assertFalse(os.path.exists(path))
        storedir = self.fixture_file('storedir_inv_format')
        self.assertRaises(WCFormatVersionError, wc_init, path,
                          ext_storedir=storedir)
        self.assertFalse(os.path.exists(path))

if __name__ == '__main__':
    unittest.main()
