import os
import unittest

from test.osctest import OscTest
from osc.wc.util import (wc_is_project, wc_is_package, wc_read_project,
                         wc_read_package, wc_read_apiurl, WCLock)


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

if __name__ == '__main__':
    unittest.main()
