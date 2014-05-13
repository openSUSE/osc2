import os
import unittest

from osc2.wc.convert import convert_package, convert_project
from osc2.wc.project import Project
from osc2.wc.package import Package
from osc2.wc.util import WCInconsistentError, WCFormatVersionError
from test.osctest import OscTest
from test.httptest import GET


def suite():
    return unittest.makeSuite(TestConvert)


class TestConvert(OscTest):

    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = os.path.join('wc', 'test_convert_fixtures')
        super(TestConvert, self).__init__(*args, **kwargs)

    def test_package1(self):
        """test package convert (added package)"""
        path = self.fixture_file('convert_1')
        self.assertRaises(WCFormatVersionError, Package, path)
        self.assertRaises(WCInconsistentError, Package, path,
                          verify_format=False)
        convert_package(path)
        pkg = Package(path)
        self.assertEqual(pkg.files(), ['add'])
        self.assertEqual(pkg.status('add'), 'A')
        self._exists(path, 'data', store=True)
        self._exists(path, '_version', store=True)
        self._not_exists(path, '_osclib_version', store=True)
        self._not_exists(path, '_to_be_added', store=True)

    def test_package2(self):
        """test package convert (various states)"""
        path = self.fixture_file('convert_2')
        self.assertRaises(WCFormatVersionError, Package, path)
        self.assertRaises(WCInconsistentError, Package, path,
                          verify_format=False)
        convert_package(path)
        pkg = Package(path)
        self.assertEqual(pkg.files(), ['conflict', 'missing', 'deleted'])
        self.assertEqual(pkg.status('conflict'), 'C')
        self.assertEqual(pkg.status('missing'), '!')
        self.assertEqual(pkg.status('deleted'), 'D')
        self._exists(path, 'data', store=True)
        self._exists(path, '_version', store=True)
        self._not_exists(path, '_osclib_version', store=True)
        self._not_exists(path, '_to_be_deleted', store=True)
        self._not_exists(path, '_in_conflict', store=True)

    @GET(('http://localhost/source/prj/convert_2_inv/deleted'
          '?rev=e0bb02d0f5f092ad542e7921f95d81d0'),
         file='convert_2_inv_deleted')
    def test_package3(self):
        """test package convert (deleted storefile missing)"""
        path = self.fixture_file('convert_2_inv')
        self.assertRaises(WCFormatVersionError, Package, path)
        self.assertRaises(WCInconsistentError, Package, path,
                          verify_format=False)
        convert_package(path)
        pkg = Package(path)
        self.assertEqual(pkg.files(), ['conflict', 'missing', 'deleted'])
        self.assertEqual(pkg.status('conflict'), 'C')
        self.assertEqual(pkg.status('missing'), '!')
        self.assertEqual(pkg.status('deleted'), 'D')
        self._exists(path, 'data', store=True)
        self._exists(path, '_version', store=True)
        self._not_exists(path, '_osclib_version', store=True)

    def test_project1(self):
        """test project convert"""
        path = self.fixture_file('project_1')
        self.assertRaises(WCFormatVersionError, Project, path)
        self.assertRaises(WCInconsistentError, Project, path,
                          verify_format=False)
        self._not_exists(path, 'data', store=True)
        convert_project(path)
        self._exists(path, 'data', store=True)
        self._exists(path, 'foo', data=True)
        self._exists(path, 'added', data=True)
        self._exists(path, 'deleted', data=True)
        os.path.islink(os.path.join(path, 'foo', '.osc'))
        os.path.islink(os.path.join(path, 'added', '.osc'))
        os.path.islink(os.path.join(path, 'deleted', '.osc'))
        prj = Project(path)
        pkg = prj.package('foo')
        self.assertEqual(pkg.files(), ['file', 'deleted', 'modified',
                                       'added', 'added2'])
        pkg = prj.package('added')
        self.assertEqual(pkg.files(), ['add'])
        pkg = prj.package('deleted')
        self.assertEqual(pkg.files(), ['deleted'])

if __name__ == '__main__':
    unittest.main()
