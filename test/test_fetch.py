import os
import unittest
from cStringIO import StringIO

from osc.build import BuildInfo, BuildDependency
from osc.fetch import FilenameCacheManager, NamePreferCacheManager
from test.osctest import OscTest


def suite():
    return unittest.makeSuite(TestFetch)


class TestFetch(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = 'test_fetch_fixtures'
        super(TestFetch, self).__init__(*args, **kwargs)

    def test_cachemanager1(self):
        """test cachemanager's exists method (existing cache)"""
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'aaa_base', '11.4',
                                        '54.60.1', 'openSUSE:11.4', 'standard')
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'x86_64',
                             'aaa_base-11.4-54.60.1.x86_64.rpm')
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        bdep = BuildDependency.fromdata('rpm', 'noarch', 'autoconf', '2.68',
                                        '4.1', 'openSUSE:11.4', 'standard')
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'noarch',
                             'autoconf-2.68-4.1.noarch.rpm')
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'foo', '1.2', '4',
                                        'home:Marcus_H', 'openSUSE_11.4')
        fname = os.path.join(root, 'home:Marcus_H', 'openSUSE_11.4', 'x86_64',
                             'foo-1.2-4.x86_64.rpm')
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        # also check deb binarytype
        bdep = BuildDependency.fromdata('deb', 'amd64', 'foo', '1.4', '4',
                                        'home:Marcus_H', 'Debian_5.0')
        fname = os.path.join(root, 'home:Marcus_H', 'Debian_5.0', 'amd64',
                             'foo_1.4-4_amd64.deb')
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        # deb with no release
        bdep = BuildDependency.fromdata('deb', 'amd64', 'bar', '1.0',
                                        project='home:Marcus_H',
                                        repository='Debian_5.0')
        fname = os.path.join(root, 'home:Marcus_H', 'Debian_5.0', 'amd64',
                             'bar_1.0_amd64.deb')
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))

    def test_cachemanager2(self):
        """test cachemanager's filename method (existing cache)"""
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'aaa_base', '11.4',
                                        '54.60.1', 'openSUSE:11.4', 'standard')
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'x86_64',
                             'aaa_base-11.4-54.60.1.x86_64.rpm')
        self.assertEqual(cmgr.filename(bdep), fname)
        bdep = BuildDependency.fromdata('rpm', 'noarch', 'autoconf', '2.68',
                                        '4.1', 'openSUSE:11.4', 'standard')
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'noarch',
                             'autoconf-2.68-4.1.noarch.rpm')
        self.assertEqual(cmgr.filename(bdep), fname)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'foo', '1.2', '4',
                                        'home:Marcus_H', 'openSUSE_11.4')
        fname = os.path.join(root, 'home:Marcus_H', 'openSUSE_11.4', 'x86_64',
                             'foo-1.2-4.x86_64.rpm')
        self.assertEqual(cmgr.filename(bdep), fname)
        # also check deb binarytype
        bdep = BuildDependency.fromdata('deb', 'amd64', 'foo', '1.4', '4',
                                        'home:Marcus_H', 'Debian_5.0')
        fname = os.path.join(root, 'home:Marcus_H', 'Debian_5.0', 'amd64',
                             'foo_1.4-4_amd64.deb')
        self.assertTrue(cmgr.filename(bdep), fname)
        # deb with no release
        bdep = BuildDependency.fromdata('deb', 'amd64', 'bar', '1.0',
                                        project='home:Marcus_H',
                                        repository='Debian_5.0')
        fname = os.path.join(root, 'home:Marcus_H', 'Debian_5.0', 'amd64',
                             'bar_1.0_amd64.deb')
        self.assertTrue(cmgr.filename(bdep), fname)

    def test_cachemanager3(self):
        """test cachemanager's exists + filename (non existent cache files)"""
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fname = self.fixture_file('buildinfo2.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        self.assertEqual(binfo.bdep[0].get('name'), 'aaa_base')
        self.assertFalse(cmgr.exists(binfo.bdep[0]))
        self.assertRaises(ValueError, cmgr.filename, binfo.bdep[0])

    def test_cachemanager4(self):
        """test cachemanager's remove method (existing cache)"""
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'foo', '1.2', '4',
                                        'home:Marcus_H', 'openSUSE_11.4')
        fname = os.path.join(root, 'home:Marcus_H', 'openSUSE_11.4', 'x86_64',
                             'foo-1.2-4.x86_64.rpm')
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        cmgr.remove(bdep)
        self.assertFalse(os.path.exists(fname))
        self.assertFalse(cmgr.exists(bdep))
        # check if directory structure was removed
        fname = os.path.join(root, 'home:Marcus_H', 'openSUSE_11.4', 'x86_64')
        self.assertFalse(os.path.exists(fname))
        fname = os.path.join(root, 'home:Marcus_H', 'openSUSE_11.4')
        self.assertFalse(os.path.exists(fname))
        # other repos in the project are not touched
        fname = os.path.join(root, 'home:Marcus_H', 'Debian_5.0')
        self.assertTrue(os.path.exists(fname))

    def test_cachemanager5(self):
        """test cachemanager's remove method (whole prj) (existing cache)"""
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'aaa_base', '11.4',
                                        '54.60.1', 'openSUSE:11.4', 'standard')
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'x86_64',
                             'aaa_base-11.4-54.60.1.x86_64.rpm')
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        cmgr.remove(bdep)
        self.assertFalse(os.path.exists(fname))
        self.assertFalse(cmgr.exists(bdep))
        # remove last package
        bdep = BuildDependency.fromdata('rpm', 'noarch', 'autoconf', '2.68',
                                        '4.1', 'openSUSE:11.4', 'standard')
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'noarch',
                             'autoconf-2.68-4.1.noarch.rpm')
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        cmgr.remove(bdep)
        self.assertFalse(os.path.exists(fname))
        self.assertFalse(cmgr.exists(bdep))
        # check if the complete project was removed
        fname = os.path.join(root, 'openSUSE:11.4')
        self.assertFalse(os.path.exists(fname))

    def test_cachemanager6(self):
        """test cachemanager's remove method (non existent cache file)"""
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'non_existent',
                                        '0.99', '0', 'openSUSE:11.4',
                                        'standard')
        self.assertRaises(ValueError, cmgr.remove, bdep)

    def test_cachemanager7(self):
        """test cachemanager's write method (existing cache, existing prpa)"""
        fname = self.fixture_file('cache_write')
        sio = StringIO(open(fname, 'r').read())
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        # existing prpa
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'x86_64')
        self.assertTrue(os.path.exists(fname))
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'foobar', '0.1', '0',
                                        'openSUSE:11.4', 'standard')
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'x86_64',
                             'foobar-0.1-0.x86_64.rpm')
        self.assertFalse(os.path.exists(fname))
        self.assertFalse(cmgr.exists(bdep))
        cmgr.write(bdep, sio)
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        self.assertEqual(cmgr.filename(bdep), fname)
        # check file contents
        self.assertEqualFile(sio.getvalue(), fname)

    def test_cachemanager8(self):
        """test cachemanager's write method (existing cache, existing prp)"""
        # nearly identical to test_cachemanager7 but only prp exists
        # (arch dir has to be created)
        fname = self.fixture_file('cache_write')
        sio = StringIO(open(fname, 'r').read())
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        # existing prp
        fname = os.path.join(root, 'openSUSE:11.4', 'standard')
        self.assertTrue(os.path.exists(fname))
        # arch does not exist
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'i586')
        self.assertFalse(os.path.exists(fname))
        bdep = BuildDependency.fromdata('rpm', 'i586', 'foobar', '0.1', '0',
                                        'openSUSE:11.4', 'standard')
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'i586',
                             'foobar-0.1-0.i586.rpm')
        self.assertFalse(os.path.exists(fname))
        self.assertFalse(cmgr.exists(bdep))
        cmgr.write(bdep, sio)
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        self.assertEqual(cmgr.filename(bdep), fname)
        # check file contents
        self.assertEqualFile(sio.getvalue(), fname)

    def test_cachemanager9(self):
        """test cachemanager's write method (existing cache, non ex. prj)"""
        fname = self.fixture_file('cache_write')
        sio = StringIO(open(fname, 'r').read())
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        # project does not exist
        fname = os.path.join(root, 'openSUSE:Factory')
        self.assertFalse(os.path.exists(fname))
        bdep = BuildDependency.fromdata('rpm', 'i586', 'foobar', '0.1', '0',
                                        'openSUSE:Factory', 'standard')
        fname = os.path.join(root, 'openSUSE:Factory', 'standard', 'i586',
                             'foobar-0.1-0.i586.rpm')
        self.assertFalse(os.path.exists(fname))
        self.assertFalse(cmgr.exists(bdep))
        cmgr.write(bdep, sio)
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        self.assertEqual(cmgr.filename(bdep), fname)
        # check file contents
        self.assertEqualFile(sio.getvalue(), fname)

    def test_cachemanager10(self):
        """test cachemanager's write method (non existent cache)"""
        sio = StringIO('some data')
        root = self.fixture_file('non_existent_cache')
        cmgr = FilenameCacheManager(root)
        # cache dir does not exist
        self.assertFalse(os.path.exists(root))
        # no release
        bdep = BuildDependency.fromdata('deb', 'all', 'foo', '0.9',
                                        project='Debian:5.0',
                                        repository='standard')
        fname = os.path.join(root, 'Debian:5.0', 'standard', 'all',
                             'foo_0.9_all.deb')
        self.assertFalse(os.path.exists(fname))
        self.assertFalse(cmgr.exists(bdep))
        cmgr.write(bdep, sio)
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        self.assertEqual(cmgr.filename(bdep), fname)
        # check file contents
        self.assertEqualFile(sio.getvalue(), fname)

    def test_cachemanager11(self):
        """test cachemanager's write method (existing bdep)"""
        sio = StringIO('foobar')
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'aaa_base', '11.4',
                                        '54.60.1', 'openSUSE:11.4', 'standard')
        self.assertTrue(cmgr.exists(bdep))
        self.assertRaises(ValueError, cmgr.write, bdep, sio)

    def test_cachemanager12(self):
        """test cachemanager's write method (write from filename)"""
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        bdep = BuildDependency.fromdata('deb', 'amd64', 'xyz', '1.4',
                                        '1', 'Debian:Etch', 'standard')
        fname = os.path.join(root, 'Debian:Etch', 'standard', 'amd64',
                             'xyz_1.4-1_amd64.deb')
        self.assertFalse(os.path.exists(fname))
        self.assertFalse(cmgr.exists(bdep))
        source = self.fixture_file('cache_write')
        cmgr.write(bdep, source)
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(cmgr.exists(bdep))
        # check file contents
        self.assertEqualFile(open(source, 'r').read(), fname)

    def test_cachemanager13(self):
        """test cachemanager invalid cache dir"""
        # we should not build as root...
        self.assertFalse(os.access('/', os.W_OK))
        self.assertRaises(ValueError, FilenameCacheManager, '/')
        # root is a filename
        root = self.fixture_file('cache_write')
        self.assertTrue(os.path.isfile(root))
        self.assertRaises(ValueError, FilenameCacheManager, root)

    def test_prefer_cachemanager1(self):
        """test NamePreferCacheManager (simple check)"""
        # this is identical to test_cachemanager2
        root = self.fixture_file('cache')
        cmgr = NamePreferCacheManager(root)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'aaa_base', '11.4',
                                        '54.60.1', 'openSUSE:11.4', 'standard')
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'x86_64',
                             'aaa_base-11.4-54.60.1.x86_64.rpm')
        self.assertEqual(cmgr.filename(bdep), fname)
        bdep = BuildDependency.fromdata('rpm', 'noarch', 'autoconf', '2.68',
                                        '4.1', 'openSUSE:11.4', 'standard')
        fname = os.path.join(root, 'openSUSE:11.4', 'standard', 'noarch',
                             'autoconf-2.68-4.1.noarch.rpm')
        self.assertEqual(cmgr.filename(bdep), fname)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'foo', '1.2', '4',
                                        'home:Marcus_H', 'openSUSE_11.4')
        fname = os.path.join(root, 'home:Marcus_H', 'openSUSE_11.4', 'x86_64',
                             'foo-1.2-4.x86_64.rpm')
        self.assertEqual(cmgr.filename(bdep), fname)
        # also check deb binarytype
        bdep = BuildDependency.fromdata('deb', 'amd64', 'foo', '1.4', '4',
                                        'home:Marcus_H', 'Debian_5.0')
        fname = os.path.join(root, 'home:Marcus_H', 'Debian_5.0', 'amd64',
                             'foo_1.4-4_amd64.deb')
        self.assertTrue(cmgr.filename(bdep), fname)
        # deb with no release
        bdep = BuildDependency.fromdata('deb', 'amd64', 'bar', '1.0',
                                        project='home:Marcus_H',
                                        repository='Debian_5.0')
        fname = os.path.join(root, 'home:Marcus_H', 'Debian_5.0', 'amd64',
                             'bar_1.0_amd64.deb')
        self.assertTrue(cmgr.filename(bdep), fname)

    def test_prefer_cachemanager2(self):
        """test NamePreferCacheManager exists + filename (with prefers)"""
        root = self.fixture_file('cache')
        autoconf_fname = self.fixture_file('autoconf.rpm')
        bar_fname = self.fixture_file('bar.rpm')
        cmgr = NamePreferCacheManager(root, autoconf=autoconf_fname,
                                      bar=bar_fname)
        bdep = BuildDependency.fromdata('rpm', 'noarch', 'autoconf', '2.68',
                                        '4.1', 'openSUSE:11.4', 'standard')
        # bdep exists
        self.assertTrue(cmgr.exists(bdep))
        self.assertEqual(cmgr.filename(bdep), autoconf_fname)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'bar', '2.00',
                                        '0', 'openSUSE:11.4', 'standard')
        # bar did not exist in the cache before
        self.assertTrue(cmgr.exists(bdep))
        self.assertEqual(cmgr.filename(bdep), bar_fname)

    def test_prefer_cachemanager3(self):
        """test NamePreferCacheManager remove (do not remove prefers)"""
        root = self.fixture_file('cache')
        bar_fname = self.fixture_file('bar.rpm')
        cmgr = NamePreferCacheManager(root, bar=bar_fname)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'bar', '2.00',
                                        '0', 'openSUSE:11.4', 'standard')
        self.assertTrue(cmgr.exists(bdep))
        self.assertTrue(os.path.exists(bar_fname))
        cmgr.remove(bdep)
        # path still exists
        self.assertTrue(os.path.exists(bar_fname))
        # bar is not available in the cache anymore
        self.assertFalse(cmgr.exists(bdep))

    def test_prefer_cachemanager4(self):
        """test NamePreferCacheManager's write method (write preferred bdep)"""
        sio = StringIO('foobar')
        root = self.fixture_file('cache')
        bar_fname = self.fixture_file('bar.rpm')
        cmgr = NamePreferCacheManager(root, bar=bar_fname)
        bdep = BuildDependency.fromdata('rpm', 'x86_64', 'bar', '1.4',
                                        '0', 'openSUSE:11.4', 'standard')
        self.assertTrue(cmgr.exists(bdep))
        # bar is a preferred package
        self.assertRaises(ValueError, cmgr.write, bdep, sio)

if __name__ == '__main__':
    unittest.main()
