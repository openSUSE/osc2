import unittest

from osc.build import BuildResult
from osctest import OscTest
from httptest import GET, PUT, POST, DELETE, MockUrllib2Request

class TestBuild(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = 'test_build_fixtures'
        super(TestBuild, self).__init__(*args, **kwargs)

    @GET('http://localhost/build/test/_result', file='prj_result.xml')
    def test_buildresult1(self):
        """project result"""
        br = BuildResult('test')
        res = br.result()
        self.assertTrue(len(res.result[:]) == 2)
        self.assertEqual(res.result[0].get('project'), 'test')
        self.assertEqual(res.result[0].get('repository'), 'openSUSE_Factory')
        self.assertEqual(res.result[0].get('arch'), 'i586')
        self.assertEqual(res.result[0].get('state'), 'building')
        self.assertTrue(len(res.result[0].status[:]) == 3)
        self.assertEqual(res.result[0].status[0].get('package'), 'foo')
        self.assertEqual(res.result[0].status[0].get('code'), 'disabled')
        self.assertEqual(res.result[0].status[0].details, '')
        self.assertEqual(res.result[0].status[1].get('package'), 'bar')
        self.assertEqual(res.result[0].status[1].get('code'), 'succeeded')
        self.assertEqual(res.result[0].status[1].details, '')
        self.assertEqual(res.result[0].status[2].get('package'), 'osc')
        self.assertEqual(res.result[0].status[2].get('code'), 'building')
        self.assertEqual(res.result[0].status[2].details, 'builds on host foo')
        # x86_64
        self.assertEqual(res.result[1].get('project'), 'test')
        self.assertEqual(res.result[1].get('repository'), 'openSUSE_Factory')
        self.assertEqual(res.result[1].get('arch'), 'x86_64')
        self.assertEqual(res.result[1].get('state'), 'building')
        self.assertEqual(res.result[1].get('dirty'), 'true')
        self.assertTrue(len(res.result[1].status[:]) == 3)
        self.assertEqual(res.result[1].status[0].get('package'), 'foo')
        self.assertEqual(res.result[1].status[0].get('code'), 'disabled')
        self.assertEqual(res.result[1].status[0].details, '')
        self.assertEqual(res.result[1].status[1].get('package'), 'bar')
        self.assertEqual(res.result[1].status[1].get('code'), 'succeeded')
        self.assertEqual(res.result[1].status[1].details, '')
        self.assertEqual(res.result[1].status[2].get('package'), 'osc')
        self.assertEqual(res.result[1].status[2].get('code'), 'succeeded')
        self.assertEqual(res.result[1].status[2].details, '')

    @GET('http://localhost/build/test/_result?repository=openSUSE_Factory',
         file='prj_result.xml')
    def test_buildresult2(self):
        """project repo result"""
        br = BuildResult('test', repository='openSUSE_Factory')
        res = br.result()
        # result is the same as in test1 (so just do a small check here)
        self.assertTrue(len(res.result[:]) == 2)

    @GET('http://localhost/build/test/_result?arch=x86_64&' \
         'repository=openSUSE_Factory', file='prj_repo_arch_result.xml')
    def test_buildresult3(self):
        """project repo arch result"""
        br = BuildResult('test', repository='openSUSE_Factory', arch='x86_64')
        res = br.result()
        # result is the same as in test1 for arch x86_64 (small check here)
        self.assertTrue(len(res.result[:]) == 1)

    @GET('http://localhost/build/test/_result?package=bar',
         file='pkg_result.xml')
    def test_buildresult4(self):
        """package result"""
        br = BuildResult('test', package='bar')
        res = br.result()
        self.assertTrue(len(res.result[:]) == 2)
        self.assertEqual(res.result[0].get('project'), 'test')
        self.assertEqual(res.result[0].get('repository'), 'openSUSE_Factory')
        self.assertEqual(res.result[0].get('arch'), 'i586')
        self.assertEqual(res.result[0].get('state'), 'building')
        self.assertEqual(res.result[0].status[0].get('package'), 'bar')
        self.assertEqual(res.result[0].status[0].get('code'), 'finished')
        self.assertEqual(res.result[0].status[0].details, 'succeeded')
        # x86_64
        self.assertEqual(res.result[1].get('project'), 'test')
        self.assertEqual(res.result[1].get('repository'), 'openSUSE_Factory')
        self.assertEqual(res.result[1].get('arch'), 'x86_64')
        self.assertEqual(res.result[1].get('state'), 'building')
        self.assertEqual(res.result[1].get('dirty'), 'true')
        self.assertEqual(res.result[1].status[0].get('package'), 'bar')
        self.assertEqual(res.result[1].status[0].get('code'), 'excluded')
        self.assertEqual(res.result[1].status[0].details, '')

    @GET('http://localhost/build/test/_result?arch=x86_64&' \
         'repository=openSUSE_Factory&package=bar',
         file='pkg_repo_arch_result.xml')
    def test_buildresult5(self):
        """package repo arch result"""
        br = BuildResult('test', package='bar', repository='openSUSE_Factory',
                         arch='x86_64')
        res = br.result()
        self.assertTrue(len(res.result[:]) == 1)
        self.assertEqual(res.result[0].get('project'), 'test')
        self.assertEqual(res.result[0].get('repository'), 'openSUSE_Factory')
        self.assertEqual(res.result[0].get('arch'), 'x86_64')
        self.assertEqual(res.result[0].get('state'), 'building')
        self.assertEqual(res.result[0].get('dirty'), 'true')
        self.assertEqual(res.result[0].status[0].get('package'), 'bar')
        self.assertEqual(res.result[0].status[0].get('code'), 'excluded')
        self.assertEqual(res.result[0].status[0].details, '')
        # check unknown element
        self.assertRaises(AttributeError, res.result[0].status[0].__getattr__,
                          'asdf')

    @GET('http://localhost/build/test/openSUSE_Factory/i586/_repository',
         file='binarylist1.xml')
    def test_binarylist1(self):
        """list binaries for project repo arch"""
        br = BuildResult('test', repository='openSUSE_Factory', arch='i586')
        list = br.binarylist()
        self.assertTrue(len(list.binary[:]) == 3)
        self.assertEqual(list.binary[0].get('filename'), 'osc.rpm')
        self.assertEqual(list.binary[0].get('size'), '1294')
        self.assertEqual(list.binary[0].get('mtime'), '1305804056')
        self.assertEqual(list.binary[1].get('filename'), 'glibc.rpm')
        self.assertEqual(list.binary[1].get('size'), '12244')
        self.assertEqual(list.binary[1].get('mtime'), '1355804056')
        self.assertEqual(list.binary[2].get('filename'), 'glibc-devel.rpm')
        self.assertEqual(list.binary[2].get('size'), '122')
        self.assertEqual(list.binary[2].get('mtime'), '1355804055')

if __name__ == '__main__':
    unittest.main()
