import os
import unittest
from cStringIO import StringIO

from osc.build import BuildInfo, BuildDependency
from osc.fetch import (FilenameCacheManager, NamePreferCacheManager,
                       BuildDependencyFetcher, BuildDependencyFetchError,
                       FetchListener)
from test.osctest import OscTest
from test.httptest import GET


def suite():
    return unittest.makeSuite(TestFetch)


class TestFetchListener(FetchListener):
    def __init__(self):
        self._pre_fetch = []
        self._post_fetch = []

    def pre(self, binfo, finfo):
        self._finfo = finfo

    def post(self, fetch_results):
        self._fetch_results = fetch_results

    def pre_fetch(self, bdep, fr):
        self._pre_fetch.append(bdep)

    def post_fetch(self, bdep, fr):
        self._post_fetch.append(bdep)


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

    def test_calculate_fetchinfo1(self):
        """test _calculate_fetchinfo"""
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        instimg_bdep = binfo.bdep[2]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache_factory')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        finfo = fetcher._calculate_fetchinfo(binfo)
        self.assertTrue(len(finfo.missing) == 4)
        self.assertEqual(finfo.missing[0], instimg_bdep)
        self.assertEqual(finfo.missing[1], ksc_bdep)
        self.assertEqual(finfo.missing[2], kscsrc_bdep)
        self.assertEqual(finfo.missing[3], mc_bdep)
        self.assertTrue(len(finfo.available) == 2)
        self.assertEqual(finfo.available[0], attr_bdep)
        self.assertEqual(finfo.available[1], python_bdep)

    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'snapshot/x86_64/aaa_base-12.2-7.1.x86_64.rpm'),
         text='some data')
    def test__fetch1(self):
        """test the _fetch method (exists on mirror)"""
        fname = self.fixture_file('buildinfo_fetch1.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        bdep = binfo.bdep[0]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertFalse(cmgr.exists(bdep))
        fr = fetcher._fetch(binfo, bdep)
        self.assertEqual(fr.bdep, bdep)
        self.assertTrue(fr.available)
        url = ('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
               'snapshot/x86_64/aaa_base-12.2-7.1.x86_64.rpm')
        self.assertEqual(fr.mirror_urls, [url])
        self.assertTrue(cmgr.exists(bdep))
        fname = os.path.join(root, 'openSUSE:Factory', 'snapshot', 'x86_64',
                             'aaa_base-12.2-7.1.x86_64.rpm')
        self.assertEqualFile('some data', fname)

    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'snapshot/x86_64/aaa_base-12.2-7.1.x86_64.rpm'),
         code=404, text='not found')
    def test__fetch2(self):
        """test the _fetch method (does not exist on mirror)"""
        fname = self.fixture_file('buildinfo_fetch1.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        bdep = binfo.bdep[0]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertFalse(cmgr.exists(bdep))
        # package was not available on the mirror
        fr = fetcher._fetch(binfo, bdep)
        self.assertEqual(fr.bdep, bdep)
        self.assertFalse(fr.available)
        url = ('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
               'snapshot/x86_64/aaa_base-12.2-7.1.x86_64.rpm')
        self.assertEqual(fr.mirror_urls, [url])
        self.assertFalse(cmgr.exists(bdep))

    @GET('http://foo/path/aaa_base-12.2-7.1.x86_64.rpm?foo=bar',
         text='foobar')
    def test__fetch3(self):
        """test the _fetch method (pass url_builder to __init__)"""
        def url_builder(binfo, bdep):
            host = 'http://foo'
            path = '/path/' + bdep.get('filename')
            return host, path, {'foo': 'bar'}

        fname = self.fixture_file('buildinfo_fetch1.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        bdep = binfo.bdep[0]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr, url_builder=[url_builder])
        self.assertFalse(cmgr.exists(bdep))
        fr = fetcher._fetch(binfo, bdep)
        self.assertEqual(fr.bdep, bdep)
        self.assertTrue(fr.available)
        url = 'http://foo/path/aaa_base-12.2-7.1.x86_64.rpm?foo=bar'
        self.assertEqual(fr.mirror_urls, [url])
        self.assertTrue(cmgr.exists(bdep))
        fname = os.path.join(root, 'openSUSE:Factory', 'snapshot', 'x86_64',
                             'aaa_base-12.2-7.1.x86_64.rpm')
        self.assertEqualFile('foobar', fname)

    @GET('http://foo/path/aaa_base-12.2-7.1.x86_64.rpm?foo=bar',
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'snapshot/x86_64/aaa_base-12.2-7.1.x86_64.rpm'),
         text='some pkg data')
    def test__fetch4(self):
        """test the _fetch method (url from url_builder returns 404)"""
        def url_builder(binfo, bdep):
            host = 'http://foo'
            path = '/path/' + bdep.get('filename')
            return host, path, {'foo': 'bar'}

        fname = self.fixture_file('buildinfo_fetch1.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        bdep = binfo.bdep[0]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr, url_builder=[url_builder])
        self.assertFalse(cmgr.exists(bdep))
        fr = fetcher._fetch(binfo, bdep)
        self.assertEqual(fr.bdep, bdep)
        self.assertTrue(fr.available)
        urls = ['http://foo/path/aaa_base-12.2-7.1.x86_64.rpm?foo=bar',
                ('http://download.opensuse.org/repositories/openSUSE%3A/'
                 'Factory/snapshot/x86_64/aaa_base-12.2-7.1.x86_64.rpm')]
        self.assertEqual(fr.mirror_urls, urls)
        self.assertTrue(cmgr.exists(bdep))
        fname = os.path.join(root, 'openSUSE:Factory', 'snapshot', 'x86_64',
                             'aaa_base-12.2-7.1.x86_64.rpm')
        self.assertEqualFile('some pkg data', fname)

    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'snapshot/x86_64/aaa_base-12.2-7.1.x86_64.rpm'),
         text='some pkg data')
    def test__fetch5(self):
        """test the _fetch method (file already exists in cache)"""
        # even if the file exists in the cache it is fetched
        # and as a result a ValueError is raised by the cache manager
        fname = self.fixture_file('buildinfo_fetch1.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        bdep = binfo.bdep[0]
        root = self.fixture_file('cache_factory')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertTrue(cmgr.exists(bdep))
        with self.assertRaises(ValueError) as cm:
            fetcher._fetch(binfo, bdep)
        # it still exists in the cache
        self.assertTrue(cmgr.exists(bdep))

    def test__fetch6(self):
        """test the _fetch method (binfo has no downloadurl element)"""
        fname = self.fixture_file('buildinfo_fetch_no_downloadurl.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        bdep = binfo.bdep[0]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        self.assertFalse(cmgr.exists(bdep))
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        fr = fetcher._fetch(binfo, bdep)
        self.assertEqual(fr.bdep, bdep)
        self.assertFalse(fr.available)
        self.assertEqual(fr.mirror_urls, [])
        self.assertFalse(cmgr.exists(bdep))

    def test_fetch_append_cpio1(self):
        """test _append_cpio (simple)"""
        fname = self.fixture_file('buildinfo_fetch1.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertTrue(len(fetcher._cpio_todo.keys()) == 0)
        fetcher._append_cpio(binfo.arch, binfo.bdep[0])
        self.assertTrue(len(fetcher._cpio_todo.keys()) == 1)
        key = 'openSUSE:Factory/snapshot/x86_64/_repository'
        self.assertTrue(key in fetcher._cpio_todo)
        self.assertEqual(fetcher._cpio_todo[key], [binfo.bdep[0]])

    def test_fetch_append_cpio2(self):
        """test _append_cpio (multiple files)"""
        fname = self.fixture_file('buildinfo_fetch1.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[1]
        perl_bdep = binfo.bdep[3]
        def_bdep = binfo.bdep[11]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertTrue(len(fetcher._cpio_todo.keys()) == 0)
        fetcher._append_cpio(binfo.arch, attr_bdep)
        fetcher._append_cpio(binfo.arch, perl_bdep)
        fetcher._append_cpio(binfo.arch, def_bdep)
        self.assertTrue(len(fetcher._cpio_todo.keys()) == 2)
        key = 'openSUSE:Factory/snapshot/x86_64/_repository'
        self.assertTrue(key in fetcher._cpio_todo)
        self.assertEqual(fetcher._cpio_todo[key], [attr_bdep, perl_bdep])
        # def pkg is in the standard repo
        key = 'openSUSE:Factory/standard/x86_64/_repository'
        self.assertTrue(key in fetcher._cpio_todo)
        self.assertEqual(fetcher._cpio_todo[key], [def_bdep])

    def test_fetch_append_cpio3(self):
        """test _append_cpio (with/without repoarch, package)"""
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        instimg_bdep = binfo.bdep[2]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertTrue(len(fetcher._cpio_todo.keys()) == 0)
        # append bdeps
        fetcher._append_cpio(binfo.arch, attr_bdep)
        fetcher._append_cpio(binfo.arch, python_bdep)
        fetcher._append_cpio(binfo.arch, instimg_bdep)
        fetcher._append_cpio(binfo.arch, ksc_bdep)
        fetcher._append_cpio(binfo.arch, kscsrc_bdep)
        fetcher._append_cpio(binfo.arch, mc_bdep)
        self.assertTrue(len(fetcher._cpio_todo.keys()) == 4)
        # factory _repository
        key = 'openSUSE:Factory/standard/x86_64/_repository'
        self.assertTrue(key in fetcher._cpio_todo)
        self.assertEqual(fetcher._cpio_todo[key], [attr_bdep, python_bdep])
        # factory ksc pkg (with repoarch)
        key = 'openSUSE:Factory/standard/i586/844-ksc-pcf'
        self.assertTrue(key in fetcher._cpio_todo)
        self.assertEqual(fetcher._cpio_todo[key], [ksc_bdep, kscsrc_bdep])
        # factory mc pkg
        key = 'openSUSE:Factory/standard/x86_64/mc'
        self.assertTrue(key in fetcher._cpio_todo)
        self.assertEqual(fetcher._cpio_todo[key], [mc_bdep])
        # prj instimg pkg
        key = 'prj/repo/x86_64/installation-images'
        self.assertTrue(key in fetcher._cpio_todo)
        self.assertEqual(fetcher._cpio_todo[key], [instimg_bdep])

    @GET(('http://localhost/build/openSUSE%3AFactory/snapshot/x86_64/'
          '_repository?binary=aaa_base&view=cpio'),
         file='fetch_cpio1.cpio')
    def test_fetch_cpio1(self):
        """test _fetch_cpio (single file)"""
        fname = self.fixture_file('buildinfo_fetch1.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        bdep = binfo.bdep[0]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertFalse(cmgr.exists(bdep))
        fetcher._append_cpio(binfo.arch, bdep)
        fetcher._fetch_cpio()
        self.assertTrue(cmgr.exists(bdep))
        fname = os.path.join(root, 'openSUSE:Factory', 'snapshot', 'x86_64',
                             'aaa_base-12.2-7.1.x86_64.rpm')
        self.assertEqualFile('aaa_base rpm file\n', fname)

    @GET(('http://localhost/build/openSUSE%3AFactory/snapshot/x86_64/'
          '_repository?binary=attr&binary=perl&view=cpio'),
         file='fetch_cpio2_snapshot.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          '_repository?binary=def&view=cpio'),
         file='fetch_cpio2_standard.cpio')
    def test_fetch_cpio2(self):
        """test _fetch_cpio (multiple files (one package is noarch))"""
        fname = self.fixture_file('buildinfo_fetch1.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[1]
        perl_bdep = binfo.bdep[3]
        def_bdep = binfo.bdep[11]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertFalse(cmgr.exists(attr_bdep))
        self.assertFalse(cmgr.exists(perl_bdep))
        self.assertFalse(cmgr.exists(def_bdep))
        # append bdeps
        fetcher._append_cpio(binfo.arch, attr_bdep)
        fetcher._append_cpio(binfo.arch, perl_bdep)
        fetcher._append_cpio(binfo.arch, def_bdep)
        fetcher._fetch_cpio()
        # check attr
        self.assertTrue(cmgr.exists(attr_bdep))
        fname = os.path.join(root, 'openSUSE:Factory', 'snapshot', 'x86_64',
                             'attr-2.4.46-10.2.x86_64.rpm')
        self.assertEqualFile('attr rpm file\n', fname)
        self.assertTrue(cmgr.exists(attr_bdep))
        # check perl
        fname = os.path.join(root, 'openSUSE:Factory', 'snapshot', 'x86_64',
                             'perl-5.16.0-4.8.x86_64.rpm')
        self.assertEqualFile('perl rpm file\n', fname)
        self.assertTrue(cmgr.exists(perl_bdep))
        # check def
        fname = os.path.join(root, 'openSUSE:Factory', 'standard', 'noarch',
                             'def-1.9-0.noarch.rpm')
        self.assertEqualFile('def rpm file\n', fname)
        self.assertTrue(cmgr.exists(def_bdep))
        # check test results
        self.assertTrue(len(fetcher.fetch_results) == 3)
        self.assertEqual(fetcher.fetch_results[0].bdep, attr_bdep)
        self.assertEqual(fetcher.fetch_results[0].mirror_urls, [])
        self.assertFalse(fetcher.fetch_results[0].mirror_match)
        self.assertEqual(fetcher.fetch_results[1].bdep, perl_bdep)
        self.assertEqual(fetcher.fetch_results[1].mirror_urls, [])
        self.assertFalse(fetcher.fetch_results[1].mirror_match)
        self.assertEqual(fetcher.fetch_results[2].bdep, def_bdep)
        self.assertEqual(fetcher.fetch_results[2].mirror_urls, [])
        self.assertFalse(fetcher.fetch_results[2].mirror_match)

    @GET(('http://localhost/build/openSUSE%3AFactory/standard/i586/'
          '844-ksc-pcf?binary=844-ksc-pcf-19990207-789.1.noarch.rpm'
          '&binary=844-ksc-pcf-19990207-789.1.src.rpm&view=cpio'),
         file='fetch_cpio3_ksc.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          '_repository?binary=attr&binary=python-devel&view=cpio'),
         file='fetch_cpio3_repository.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          'mc?binary=mc-4.8.1.4-1.1.src.rpm&view=cpio'),
         file='fetch_cpio3_mc.cpio')
    @GET(('http://localhost/build/prj/repo/x86_64/installation-images'
          '?binary=installation-images-13.49-3.6.src.rpm&view=cpio'),
         file='fetch_cpio3_inst_images.cpio')
    def test_fetch_cpio3(self):
        """test _fetch_cpio (multiple projects and repos)"""
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        instimg_bdep = binfo.bdep[2]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertFalse(cmgr.exists(attr_bdep))
        self.assertFalse(cmgr.exists(python_bdep))
        self.assertFalse(cmgr.exists(instimg_bdep))
        self.assertFalse(cmgr.exists(ksc_bdep))
        self.assertFalse(cmgr.exists(kscsrc_bdep))
        self.assertFalse(cmgr.exists(mc_bdep))
        # append bdeps
        fetcher._append_cpio(binfo.arch, attr_bdep)
        fetcher._append_cpio(binfo.arch, python_bdep)
        fetcher._append_cpio(binfo.arch, instimg_bdep)
        fetcher._append_cpio(binfo.arch, ksc_bdep)
        fetcher._append_cpio(binfo.arch, kscsrc_bdep)
        fetcher._append_cpio(binfo.arch, mc_bdep)
        fetcher._fetch_cpio()
        # just check for existence
        self.assertTrue(cmgr.exists(attr_bdep))
        self.assertTrue(cmgr.exists(python_bdep))
        self.assertTrue(cmgr.exists(instimg_bdep))
        self.assertTrue(cmgr.exists(ksc_bdep))
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        self.assertTrue(cmgr.exists(mc_bdep))

    @GET(('http://localhost/build/openSUSE%3AFactory/standard/i586/'
          '844-ksc-pcf?binary=844-ksc-pcf-19990207-789.1.noarch.rpm'
          '&binary=844-ksc-pcf-19990207-789.1.src.rpm&view=cpio'),
         file='fetch_cpio3_ksc.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          '_repository?binary=attr&binary=python-devel&view=cpio'),
         file='fetch_cpio4_repository_errors.cpio')
    def test_fetch_cpio4(self):
        """test _fetch_cpio (with .errors file)"""
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertFalse(cmgr.exists(attr_bdep))
        self.assertFalse(cmgr.exists(python_bdep))
        self.assertFalse(cmgr.exists(ksc_bdep))
        self.assertFalse(cmgr.exists(kscsrc_bdep))
        self.assertFalse(cmgr.exists(mc_bdep))
        # append bdeps
        fetcher._append_cpio(binfo.arch, attr_bdep)
        fetcher._append_cpio(binfo.arch, python_bdep)
        fetcher._append_cpio(binfo.arch, ksc_bdep)
        fetcher._append_cpio(binfo.arch, kscsrc_bdep)
        fetcher._append_cpio(binfo.arch, mc_bdep)
        with self.assertRaises(BuildDependencyFetchError) as cm:
            fetcher._fetch_cpio()
        self.assertTrue(len(cm.exception.bdeps) == 1)
        self.assertEqual(cm.exception.bdeps[0].bdep, attr_bdep)
        self.assertEqual(cm.exception.bdeps[0].mirror_urls, [])
        self.assertEqual(cm.exception.errors, 'attr: not available')
        # failed to fetch this package
        self.assertFalse(cmgr.exists(attr_bdep))
        # python bdep exists
        self.assertTrue(cmgr.exists(python_bdep))
        self.assertTrue(cmgr.exists(ksc_bdep))
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        # we did not fetch this package
        self.assertFalse(cmgr.exists(mc_bdep))

    @GET(('http://localhost/build/openSUSE%3AFactory/standard/i586/'
          '844-ksc-pcf?binary=844-ksc-pcf-19990207-789.1.noarch.rpm'
          '&binary=844-ksc-pcf-19990207-789.1.src.rpm&view=cpio'),
         file='fetch_cpio3_ksc.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          '_repository?binary=attr&binary=python-devel&view=cpio'),
         file='fetch_cpio4_repository_errors.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          'mc?binary=mc-4.8.1.4-1.1.src.rpm&view=cpio'),
         file='fetch_cpio3_mc.cpio')
    def test_fetch_cpio5(self):
        """test _fetch_cpio (with .errors file, defer_error=True)"""
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertFalse(cmgr.exists(attr_bdep))
        self.assertFalse(cmgr.exists(python_bdep))
        self.assertFalse(cmgr.exists(ksc_bdep))
        self.assertFalse(cmgr.exists(kscsrc_bdep))
        self.assertFalse(cmgr.exists(mc_bdep))
        # append bdeps
        fetcher._append_cpio(binfo.arch, attr_bdep)
        fetcher._append_cpio(binfo.arch, python_bdep)
        fetcher._append_cpio(binfo.arch, ksc_bdep)
        fetcher._append_cpio(binfo.arch, kscsrc_bdep)
        fetcher._append_cpio(binfo.arch, mc_bdep)
        with self.assertRaises(BuildDependencyFetchError) as cm:
            fetcher._fetch_cpio(defer_error=True)
        self.assertTrue(len(cm.exception.bdeps) == 1)
        self.assertEqual(cm.exception.bdeps[0].bdep, attr_bdep)
        self.assertEqual(cm.exception.bdeps[0].mirror_urls, [])
        self.assertEqual(cm.exception.errors, 'attr: not available')
        # failed to fetch this package
        self.assertFalse(cmgr.exists(attr_bdep))
        # python bdep exists
        self.assertTrue(cmgr.exists(python_bdep))
        self.assertTrue(cmgr.exists(ksc_bdep))
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        # this package was fetched due to defer_error=True
        self.assertTrue(cmgr.exists(mc_bdep))

    @GET(('http://localhost/build/openSUSE%3AFactory/standard/i586/'
          '844-ksc-pcf?binary=844-ksc-pcf-19990207-789.1.noarch.rpm'
          '&binary=844-ksc-pcf-19990207-789.1.src.rpm&view=cpio'),
         file='fetch_cpio6_ksc_missing.cpio')
    def test_fetch_cpio6(self):
        """test _fetch_cpio (missing file for a specific package)"""
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertFalse(cmgr.exists(attr_bdep))
        self.assertFalse(cmgr.exists(python_bdep))
        self.assertFalse(cmgr.exists(ksc_bdep))
        self.assertFalse(cmgr.exists(kscsrc_bdep))
        self.assertFalse(cmgr.exists(mc_bdep))
        # append bdeps
        fetcher._append_cpio(binfo.arch, attr_bdep)
        fetcher._append_cpio(binfo.arch, python_bdep)
        fetcher._append_cpio(binfo.arch, ksc_bdep)
        fetcher._append_cpio(binfo.arch, kscsrc_bdep)
        fetcher._append_cpio(binfo.arch, mc_bdep)
        with self.assertRaises(BuildDependencyFetchError) as cm:
            fetcher._fetch_cpio()
        self.assertTrue(len(cm.exception.bdeps) == 1)
        self.assertEqual(cm.exception.bdeps[0].bdep, ksc_bdep)
        self.assertEqual(cm.exception.bdeps[0].mirror_urls, [])
        self.assertEqual(cm.exception.errors, '')
        # this package is missing
        self.assertFalse(cmgr.exists(ksc_bdep))
        # kscsrc exists
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        # these packages were not fetched
        self.assertFalse(cmgr.exists(attr_bdep))
        self.assertFalse(cmgr.exists(python_bdep))
        self.assertFalse(cmgr.exists(mc_bdep))

    @GET(('http://localhost/build/openSUSE%3AFactory/standard/i586/'
          '844-ksc-pcf?binary=844-ksc-pcf-19990207-789.1.noarch.rpm'
          '&binary=844-ksc-pcf-19990207-789.1.src.rpm&view=cpio'),
         file='fetch_cpio6_ksc_missing.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          '_repository?binary=attr&binary=python-devel&view=cpio'),
         file='fetch_cpio3_repository.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          'mc?binary=mc-4.8.1.4-1.1.src.rpm&view=cpio'),
         file='fetch_cpio3_mc.cpio')
    def test_fetch_cpio7(self):
        """test _fetch_cpio (missing file for a package - defer_error=True)"""
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertFalse(cmgr.exists(attr_bdep))
        self.assertFalse(cmgr.exists(python_bdep))
        self.assertFalse(cmgr.exists(ksc_bdep))
        self.assertFalse(cmgr.exists(kscsrc_bdep))
        self.assertFalse(cmgr.exists(mc_bdep))
        # append bdeps
        fetcher._append_cpio(binfo.arch, attr_bdep)
        fetcher._append_cpio(binfo.arch, python_bdep)
        fetcher._append_cpio(binfo.arch, ksc_bdep)
        fetcher._append_cpio(binfo.arch, kscsrc_bdep)
        fetcher._append_cpio(binfo.arch, mc_bdep)
        with self.assertRaises(BuildDependencyFetchError) as cm:
            fetcher._fetch_cpio(defer_error=True)
        self.assertTrue(len(cm.exception.bdeps) == 1)
        self.assertEqual(cm.exception.bdeps[0].bdep, ksc_bdep)
        self.assertEqual(cm.exception.bdeps[0].mirror_urls, [])
        self.assertEqual(cm.exception.errors, '')
        # this package is missing
        self.assertFalse(cmgr.exists(ksc_bdep))
        # kscsrc exists
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        # these packages were fetched due to defer_error=True
        self.assertTrue(cmgr.exists(attr_bdep))
        self.assertTrue(cmgr.exists(python_bdep))
        self.assertTrue(cmgr.exists(mc_bdep))

    @GET(('http://localhost/build/openSUSE%3AFactory/standard/i586/'
          '844-ksc-pcf?binary=844-ksc-pcf-19990207-789.1.noarch.rpm'
          '&binary=844-ksc-pcf-19990207-789.1.src.rpm&view=cpio'),
         file='fetch_cpio6_ksc_missing.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          '_repository?binary=attr&binary=python-devel&view=cpio'),
         file='fetch_cpio4_repository_errors.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          'mc?binary=mc-4.8.1.4-1.1.src.rpm&view=cpio'),
         file='fetch_cpio3_mc.cpio')
    def test_fetch_cpio8(self):
        """test _fetch_cpio (multiple files missing - defer_error=True)"""
        # this is basically a mixture of case 5 and 7
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        self.assertFalse(cmgr.exists(attr_bdep))
        self.assertFalse(cmgr.exists(python_bdep))
        self.assertFalse(cmgr.exists(ksc_bdep))
        self.assertFalse(cmgr.exists(kscsrc_bdep))
        self.assertFalse(cmgr.exists(mc_bdep))
        # append bdeps
        fetcher._append_cpio(binfo.arch, attr_bdep)
        fetcher._append_cpio(binfo.arch, python_bdep)
        fetcher._append_cpio(binfo.arch, ksc_bdep)
        fetcher._append_cpio(binfo.arch, kscsrc_bdep)
        fetcher._append_cpio(binfo.arch, mc_bdep)
        with self.assertRaises(BuildDependencyFetchError) as cm:
            fetcher._fetch_cpio(defer_error=True)
        self.assertTrue(len(cm.exception.bdeps) == 2)
        self.assertEqual(cm.exception.bdeps[0].bdep, ksc_bdep)
        self.assertEqual(cm.exception.bdeps[0].mirror_urls, [])
        self.assertEqual(cm.exception.bdeps[1].bdep, attr_bdep)
        self.assertEqual(cm.exception.bdeps[1].mirror_urls, [])
        self.assertEqual(cm.exception.errors, 'attr: not available')
        # these packages are missing
        self.assertFalse(cmgr.exists(attr_bdep))
        self.assertFalse(cmgr.exists(ksc_bdep))
        # the rest exists
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        self.assertTrue(cmgr.exists(python_bdep))
        self.assertTrue(cmgr.exists(mc_bdep))

    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/x86_64/attr-2.4.46-10.2.x86_64.rpm'),
         text='attr rpm file')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/x86_64/python-devel-2.7.3-4.8.x86_64.rpm'),
         text='python-devel rpm file')
    @GET(('http://download.opensuse.org/repositories/prj/repo/src/'
          'installation-images-13.49-3.6.src.rpm'),
         text='installation-images rpm file')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/noarch/844-ksc-pcf-19990207-789.1.noarch.rpm'),
         text='844-ksc-pcf rpm file')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/src/844-ksc-pcf-19990207-789.1.src.rpm'),
         text='844-ksc-pcf src rpm file')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/src/mc-4.8.1.4-1.1.src.rpm'),
         text='mc src rpm file')
    def test_fetch1(self):
        """test fetch (all bdeps are available on the mirrors)"""
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        instimg_bdep = binfo.bdep[2]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        fetcher.fetch(binfo)
        # check if bdeps exist
        self.assertTrue(cmgr.exists(attr_bdep))
        self.assertTrue(cmgr.exists(python_bdep))
        self.assertTrue(cmgr.exists(ksc_bdep))
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        self.assertTrue(cmgr.exists(mc_bdep))

    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/x86_64/attr-2.4.46-10.2.x86_64.rpm'),
         text='attr rpm file')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/x86_64/python-devel-2.7.3-4.8.x86_64.rpm'),
         text='python-devel rpm file')
    @GET(('http://download.opensuse.org/repositories/prj/repo/src/'
          'installation-images-13.49-3.6.src.rpm'),
         text='installation-images rpm file')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/noarch/844-ksc-pcf-19990207-789.1.noarch.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/src/844-ksc-pcf-19990207-789.1.src.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/src/mc-4.8.1.4-1.1.src.rpm'),
         text='mc src rpm file')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/i586/'
          '844-ksc-pcf?binary=844-ksc-pcf-19990207-789.1.noarch.rpm'
          '&binary=844-ksc-pcf-19990207-789.1.src.rpm&view=cpio'),
         file='fetch_cpio3_ksc.cpio')
    def test_fetch2(self):
        """test fetch (not all bdeps are available on the mirrors)"""
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        instimg_bdep = binfo.bdep[2]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        fetcher.fetch(binfo)
        # check if bdeps exist
        self.assertTrue(cmgr.exists(attr_bdep))
        self.assertTrue(cmgr.exists(python_bdep))
        self.assertTrue(cmgr.exists(ksc_bdep))
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        self.assertTrue(cmgr.exists(mc_bdep))
        # check some values of the fetch results
        self.assertTrue(len(fetcher.fetch_results) == 6)
        self.assertEqual(fetcher.fetch_results[0].bdep, attr_bdep)
        self.assertTrue(fetcher.fetch_results[0].mirror_match)
        self.assertEqual(fetcher.fetch_results[1].bdep, python_bdep)
        self.assertTrue(fetcher.fetch_results[1].mirror_match)
        self.assertEqual(fetcher.fetch_results[2].bdep, instimg_bdep)
        self.assertTrue(fetcher.fetch_results[2].mirror_match)
        self.assertEqual(fetcher.fetch_results[3].bdep, ksc_bdep)
        self.assertFalse(fetcher.fetch_results[3].mirror_match)
        self.assertEqual(fetcher.fetch_results[4].bdep, kscsrc_bdep)
        self.assertFalse(fetcher.fetch_results[4].mirror_match)
        self.assertEqual(fetcher.fetch_results[5].bdep, mc_bdep)
        self.assertTrue(fetcher.fetch_results[5].mirror_match)

    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/x86_64/attr-2.4.46-10.2.x86_64.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/x86_64/python-devel-2.7.3-4.8.x86_64.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/prj/repo/src/'
          'installation-images-13.49-3.6.src.rpm'),
         text='installation-images rpm file')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/noarch/844-ksc-pcf-19990207-789.1.noarch.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/src/844-ksc-pcf-19990207-789.1.src.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/src/mc-4.8.1.4-1.1.src.rpm'),
         text='mc src rpm file')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/i586/'
          '844-ksc-pcf?binary=844-ksc-pcf-19990207-789.1.noarch.rpm'
          '&binary=844-ksc-pcf-19990207-789.1.src.rpm&view=cpio'),
         file='fetch_cpio6_ksc_missing.cpio')
    def test_fetch3(self):
        """test fetch (some bdeps cannot be fetched)"""
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        instimg_bdep = binfo.bdep[2]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        with self.assertRaises(BuildDependencyFetchError) as cm:
            fetcher.fetch(binfo)
        self.assertTrue(len(cm.exception.bdeps) == 1)
        self.assertEqual(cm.exception.bdeps[0].bdep, ksc_bdep)
        urls = [('http://download.opensuse.org/repositories/openSUSE%3A/'
                 'Factory/standard/noarch/844-ksc-pcf-19990207-789.1.noarch'
                 '.rpm')]
        self.assertEqual(cm.exception.bdeps[0].mirror_urls, urls)
        self.assertEqual(cm.exception.errors, '')
        # check if bdeps exist
        self.assertFalse(cmgr.exists(attr_bdep))
        self.assertFalse(cmgr.exists(python_bdep))
        self.assertFalse(cmgr.exists(ksc_bdep))
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        self.assertTrue(cmgr.exists(mc_bdep))

    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/x86_64/attr-2.4.46-10.2.x86_64.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/x86_64/python-devel-2.7.3-4.8.x86_64.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/prj/repo/src/'
          'installation-images-13.49-3.6.src.rpm'),
         text='installation-images rpm file')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/noarch/844-ksc-pcf-19990207-789.1.noarch.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/src/844-ksc-pcf-19990207-789.1.src.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/src/mc-4.8.1.4-1.1.src.rpm'),
         text='mc src rpm file')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/i586/'
          '844-ksc-pcf?binary=844-ksc-pcf-19990207-789.1.noarch.rpm'
          '&binary=844-ksc-pcf-19990207-789.1.src.rpm&view=cpio'),
         file='fetch_cpio6_ksc_missing.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          '_repository?binary=attr&binary=python-devel&view=cpio'),
         file='fetch_cpio4_repository_errors.cpio')
    def test_fetch4(self):
        """test fetch (some bdeps cannot be fetched - defer_error=True)"""
        # similar to test_fetch3 (but this time with defer_error=True)
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        instimg_bdep = binfo.bdep[2]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        with self.assertRaises(BuildDependencyFetchError) as cm:
            fetcher.fetch(binfo, defer_error=True)
        self.assertTrue(len(cm.exception.bdeps) == 2)
        self.assertEqual(cm.exception.bdeps[0].bdep, ksc_bdep)
        urls = [('http://download.opensuse.org/repositories/openSUSE%3A/'
                 'Factory/standard/noarch/844-ksc-pcf-19990207-789.1.noarch'
                 '.rpm')]
        self.assertEqual(cm.exception.bdeps[0].mirror_urls, urls)
        self.assertEqual(cm.exception.bdeps[1].bdep, attr_bdep)
        urls = [('http://download.opensuse.org/repositories/openSUSE%3A/'
                 'Factory/standard/x86_64/attr-2.4.46-10.2.x86_64.rpm')]
        self.assertEqual(cm.exception.bdeps[1].mirror_urls, urls)
        self.assertEqual(cm.exception.errors, 'attr: not available')
        # check if bdeps exist
        self.assertFalse(cmgr.exists(attr_bdep))
        self.assertTrue(cmgr.exists(python_bdep))
        self.assertFalse(cmgr.exists(ksc_bdep))
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        self.assertTrue(cmgr.exists(mc_bdep))

    @GET(('http://download.opensuse.org/repositories/prj/repo/src/'
          'installation-images-13.49-3.6.src.rpm'),
         text='installation-images rpm file')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/noarch/844-ksc-pcf-19990207-789.1.noarch.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/src/844-ksc-pcf-19990207-789.1.src.rpm'),
         code=404, text='not found')
    @GET(('http://download.opensuse.org/repositories/openSUSE%3A/Factory/'
          'standard/src/mc-4.8.1.4-1.1.src.rpm'),
         text='mc src rpm file')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/i586/'
          '844-ksc-pcf?binary=844-ksc-pcf-19990207-789.1.noarch.rpm'
          '&binary=844-ksc-pcf-19990207-789.1.src.rpm&view=cpio'),
         file='fetch_cpio3_ksc.cpio')
    def test_fetch5(self):
        """test fetch (test pre, post, pre_fetch, post_fetch hooks)"""
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        instimg_bdep = binfo.bdep[2]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache_factory')
        cmgr = FilenameCacheManager(root)
        listener = TestFetchListener()
        fetcher = BuildDependencyFetcher(cmgr=cmgr, listener=[listener])
        fetcher.fetch(binfo)
        # check if bdeps exist
        self.assertTrue(cmgr.exists(attr_bdep))
        self.assertTrue(cmgr.exists(python_bdep))
        self.assertTrue(cmgr.exists(ksc_bdep))
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        self.assertTrue(cmgr.exists(mc_bdep))
        # check listener
        # pre
        finfo = listener._finfo
        self.assertTrue(len(finfo.missing) == 4)
        self.assertEqual(finfo.missing[0], instimg_bdep)
        self.assertEqual(finfo.missing[1], ksc_bdep)
        self.assertEqual(finfo.missing[2], kscsrc_bdep)
        self.assertEqual(finfo.missing[3], mc_bdep)
        self.assertTrue(len(finfo.available) == 2)
        self.assertEqual(finfo.available[0], attr_bdep)
        self.assertEqual(finfo.available[1], python_bdep)
        # pre_fetch
        bdeps = [instimg_bdep, ksc_bdep, kscsrc_bdep, mc_bdep, ksc_bdep,
                 kscsrc_bdep]
        self.assertEqual(listener._pre_fetch, bdeps)
        # post_fetch (pre and post fetch do the same)
        self.assertEqual(listener._post_fetch, bdeps)
        # post
        self.assertTrue(len(listener._fetch_results) == 4)

    @GET(('http://localhost/build/openSUSE%3AFactory/standard/i586/'
          '844-ksc-pcf?binary=844-ksc-pcf-19990207-789.1.noarch.rpm'
          '&binary=844-ksc-pcf-19990207-789.1.src.rpm&view=cpio'),
         file='fetch_cpio3_ksc.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          '_repository?binary=attr&binary=python-devel&view=cpio'),
         file='fetch_cpio3_repository.cpio')
    @GET(('http://localhost/build/openSUSE%3AFactory/standard/x86_64/'
          'mc?binary=mc-4.8.1.4-1.1.src.rpm&view=cpio'),
         file='fetch_cpio3_mc.cpio')
    @GET(('http://localhost/build/prj/repo/x86_64/installation-images'
          '?binary=installation-images-13.49-3.6.src.rpm&view=cpio'),
         file='fetch_cpio3_inst_images.cpio')
    def test_fetch6(self):
        """test fetch (use_mirror=False)"""
        # this is basically test_fetch_cpio3
        fname = self.fixture_file('buildinfo_fetch3.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        attr_bdep = binfo.bdep[0]
        python_bdep = binfo.bdep[1]
        instimg_bdep = binfo.bdep[2]
        ksc_bdep = binfo.bdep[3]
        kscsrc_bdep = binfo.bdep[4]
        mc_bdep = binfo.bdep[5]
        root = self.fixture_file('cache')
        cmgr = FilenameCacheManager(root)
        fetcher = BuildDependencyFetcher(cmgr=cmgr)
        fetcher.fetch(binfo, use_mirrors=False)
        # just check for existence
        self.assertTrue(cmgr.exists(attr_bdep))
        self.assertTrue(cmgr.exists(python_bdep))
        self.assertTrue(cmgr.exists(instimg_bdep))
        self.assertTrue(cmgr.exists(ksc_bdep))
        self.assertTrue(cmgr.exists(kscsrc_bdep))
        self.assertTrue(cmgr.exists(mc_bdep))

if __name__ == '__main__':
    unittest.main()
