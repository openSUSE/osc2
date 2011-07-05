import unittest

from lxml import etree

from osc.source import Project, Package
from test.osctest import OscTest
from test.httptest import GET

def suite():
    return unittest.makeSuite(TestSource)

class TestSource(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = 'test_source_fixtures'
        super(TestSource, self).__init__(*args, **kwargs)

    @GET('http://localhost/source/openSUSE%3AFactory', file='pkg_list.xml')
    def test1(self):
        """test package list"""
        Project.SCHEMA = self.fixture_file('directory.xsd')
        prj = Project('openSUSE:Factory')
        pkgs = prj.list()
        self.assertTrue(len(pkgs) == 3)
        self.assertEqual(pkgs[0].name, 'osc')
        self.assertEqual(pkgs[1].name, 'glibc')
        self.assertEqual(pkgs[2].name, 'python')

    @GET('http://localhost/source/openSUSE%3AFactory', text='<invalid />')
    def test2(self):
        """test invalid xml data (package list)"""
        Project.LIST_SCHEMA = self.fixture_file('directory.xsd')
        prj = Project('openSUSE:Factory')
        self.assertRaises(etree.DocumentInvalid, prj.list)

    @GET('http://localhost/source/openSUSE%3AFactory', file='pkg_list.xml')
    @GET('http://localhost/source/openSUSE%3AFactory/osc',
         file='file_list.xml')
    @GET('http://localhost/source/openSUSE%3AFactory/osc/osc.spec?rev=ef2',
         file='osc.spec')
    def test3(self):
        """test list's return value"""
        Project.LIST_SCHEMA = self.fixture_file('directory.xsd')
        Package.LIST_SCHEMA = self.fixture_file('directory.xsd')
        prj = Project('openSUSE:Factory')
        pkg = prj.list()[0]
        self.assertEqual(pkg.name, 'osc')
        files = pkg.list()
        self.assertTrue(len(files.entry[:]) == 2)
        self.assertEqual(files.get('name'), 'osc')
        self.assertEqual(files.get('rev'), '61')
        self.assertEqual(files.get('srcmd5'), 'fff')
        self.assertEqual(files.get('project'), 'openSUSE:Factory')
        self.assertEqual(files.entry[0].get('name'), 'osc-0.132.4.tar.gz')
        self.assertEqual(files.entry[0].get('md5'), 'abc')
        self.assertEqual(files.entry[0].get('size'), '269202')
        self.assertEqual(files.entry[0].get('mtime'), '1')
        # second entry
        self.assertEqual(files.entry[1].get('name'), 'osc.spec')
        self.assertEqual(files.entry[1].get('md5'), 'ef2')
        self.assertEqual(files.entry[1].get('size'), '3761')
        self.assertEqual(files.entry[1].get('mtime'), '14')
        # test file method
        f = files.entry[1].file()
        self.assertEqual(f.read(), '# this is\n# no spec\n')

    @GET('http://localhost/source/foo/bar', text='<foo/>')
    def test4(self):
        """test invalid xml data (file list)"""
        Project.LIST_SCHEMA = self.fixture_file('directory.xsd')
        pkg = Package('foo', 'bar')
        self.assertRaises(etree.DocumentInvalid, pkg.list)

    @GET('http://localhost/source/foo/bar?rev=fff', file='file_list.xml')
    def test5(self):
        """list a specific package revision"""
        pkg = Package('foo', 'bar')
        pkg.list(rev='fff')
        # the result was already tested in test3

    @GET('http://localhost/source/foo/bar/_history', file='pkg_history.xml')
    def test6(self):
        """test commit log"""
        pkg = Package('foo', 'bar')
        log = pkg.log()
        self.assertTrue(len(log.revision[:]) == 2)
        self.assertEqual(log.revision[0].get('rev'), '1')
        self.assertEqual(log.revision[0].get('vrev'), '1')
        self.assertEqual(log.revision[0].srcmd5, 'abc')
        self.assertEqual(log.revision[0].version, 'unknown')
        self.assertEqual(log.revision[0].time, '1308140485')
        self.assertEqual(log.revision[0].user, 'foo')
        self.assertEqual(log.revision[0].comment, 'updated pkg')
        self.assertFalse('requestid' in log.revision[0])
        # second entry
        self.assertEqual(log.revision[1].get('rev'), '2')
        self.assertEqual(log.revision[1].get('vrev'), '1')
        self.assertEqual(log.revision[1].srcmd5, 'fff')
        self.assertEqual(log.revision[1].version, 'unknown')
        self.assertEqual(log.revision[1].time, '1308140486')
        self.assertEqual(log.revision[1].user, 'foo')
        self.assertEqual(log.revision[1].comment, 'request')
        self.assertEqual(log.revision[1].requestid, '123')


if __name__ == '__main__':
    unittest.main()
