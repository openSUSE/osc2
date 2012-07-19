import unittest
from cStringIO import StringIO

from lxml import etree

from osc.build import BuildResult, BinaryList, BuildInfo, BuildDependency
from test.osctest import OscTest
from test.httptest import GET, POST


def suite():
    return unittest.makeSuite(TestBuild)


class TestBuild(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = 'test_build_fixtures'
        super(TestBuild, self).__init__(*args, **kwargs)

    def tearDown(self):
        super(TestBuild, self).tearDown()
        BuildResult.RESULT_SCHEMA = ''

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
         'package=bar&repository=openSUSE_Factory&x=y',
         file='pkg_repo_arch_result.xml')
    def test_buildresult5(self):
        """package repo arch result"""
        br = BuildResult('test', package='bar', repository='openSUSE_Factory',
                         arch='x86_64')
        res = br.result(x='y')
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

    @GET('http://localhost/build/test/_result', text='<invalid />')
    def test_buildresult6(self):
        """test validation"""
        # misuse the binarylist schema
        BuildResult.RESULT_SCHEMA = self.fixture_file('binarylist_simple.xsd')
        br = BuildResult('test')
        self.assertRaises(etree.DocumentInvalid, br.result)

    @GET('http://localhost/build/test/openSUSE_Factory/i586/_repository',
         file='binarylist1.xml')
    def test_binarylist1(self):
        """list binaries for project repo arch"""
        br = BuildResult('test', repository='openSUSE_Factory', arch='i586')
        blist = br.binarylist()
        self.assertTrue(len(blist.binary[:]) == 3)
        self.assertEqual(blist.binary[0].get('filename'), 'osc.rpm')
        self.assertEqual(blist.binary[0].get('size'), '1294')
        self.assertEqual(blist.binary[0].get('mtime'), '1305804056')
        self.assertEqual(blist.binary[1].get('filename'), 'glibc.rpm')
        self.assertEqual(blist.binary[1].get('size'), '12244')
        self.assertEqual(blist.binary[1].get('mtime'), '1355804056')
        self.assertEqual(blist.binary[2].get('filename'), 'glibc-devel.rpm')
        self.assertEqual(blist.binary[2].get('size'), '122')
        self.assertEqual(blist.binary[2].get('mtime'), '1355804055')

    @GET('http://localhost/build/test/repo/i586/_repository',
         file='binarylist1.xml')
    @GET('http://localhost/build/test/repo/i586/_repository/osc.rpm?a=b&c=d',
         text='osc.rpm')
    @GET('http://localhost/build/test/repo/i586/_repository/glibc.rpm',
         text='glibc.rpm')
    @GET('http://localhost/build/test/repo/i586/_repository/glibc-devel.rpm',
         text='glibc-devel.rpm')
    def test_binarylist2(self):
        """list binaries for project repo arch and get each binary file"""
        br = BuildResult('test', repository='repo', arch='i586')
        blist = br.binarylist()
        self.assertTrue(len(blist.binary[:]) == 3)
        self.assertEqual(blist.binary[0].get('filename'), 'osc.rpm')
        self.assertEqual(blist.binary[0].get('size'), '1294')
        self.assertEqual(blist.binary[0].get('mtime'), '1305804056')
        self.assertEqual(blist.binary[1].get('filename'), 'glibc.rpm')
        self.assertEqual(blist.binary[1].get('size'), '12244')
        self.assertEqual(blist.binary[1].get('mtime'), '1355804056')
        self.assertEqual(blist.binary[2].get('filename'), 'glibc-devel.rpm')
        self.assertEqual(blist.binary[2].get('size'), '122')
        self.assertEqual(blist.binary[2].get('mtime'), '1355804055')
        bfile = blist.binary[0].file(a='b', c='d')
        self.assertEqual(bfile.read(), 'osc.rpm')
        bfile = blist.binary[1].file()
        self.assertEqual(bfile.read(), 'glibc.rpm')
        bfile = blist.binary[2].file()
        self.assertEqual(bfile.read(), 'glibc-devel.rpm')

    @GET('http://localhost/build/test/repo/i586/osc',
         text='<invalid />')
    def test_binarylist3(self):
        """return an invalid binarylist xml (test validation)"""
        br = BuildResult('test', package='osc', repository='repo', arch='i586')
        BinaryList.SCHEMA = self.fixture_file('binarylist_simple.xsd')
        self.assertRaises(etree.DocumentInvalid, br.binarylist)

    @GET('http://localhost/build/test/repo/x86_64/_repository?view=cpio',
         file='binarylist_cpio1.cpio')
    def test_binarylist4(self):
        """test the cpio view (complete repo)"""
        br = BuildResult('test', repository='repo', arch='x86_64')
        archive = br.binarylist(view='cpio')
        it = iter(archive)
        archive_file = it.next()
        self.assertEqual(archive_file.read(), 'foo\n')
        archive_file = it.next()
        self.assertEqual(archive_file.read(), 'bar\n')
        archive_file = it.next()
        self.assertEqual(archive_file.read(), 'glibc\n')
        self.assertRaises(StopIteration, it.next)

    @GET(('http://localhost/build/test/repo/x86_64/_repository?binary=foo&'
          'binary=bar&view=cpio'),
         file='binarylist_cpio2.cpio')
    def test_binarylist5(self):
        """test the cpio view (only some binaries)"""
        br = BuildResult('test', repository='repo', arch='x86_64')
        archive = br.binarylist(view='cpio', binary=['foo', 'bar'])
        it = iter(archive)
        archive_file = it.next()
        self.assertEqual(archive_file.read(), 'foo\n')
        archive_file = it.next()
        self.assertEqual(archive_file.read(), 'bar\n')
        self.assertRaises(StopIteration, it.next)

    @GET(('http://localhost/build/test/repo/x86_64/pkg?binary=foo&'
          'binary=bar&view=cpio'),
         file='binarylist_cpio2.cpio')
    def test_binarylist6(self):
        """test the cpio view (only some binaries + specify package)"""
        br = BuildResult('test', package='pkg', repository='repo',
                         arch='x86_64')
        archive = br.binarylist(view='cpio', binary=['foo', 'bar'])
        it = iter(archive)
        archive_file = it.next()
        self.assertEqual(archive_file.read(), 'foo\n')
        archive_file = it.next()
        self.assertEqual(archive_file.read(), 'bar\n')
        self.assertRaises(StopIteration, it.next)

    @GET('http://localhost/build/test/repo/i586/osc/_log', text='logfile')
    def test_logfile1(self):
        """get the logfile"""
        br = BuildResult('test', package='osc', repository='repo', arch='i586')
        log = br.log()
        self.assertEqual(log.read(), 'logfile')
        log.seek(3)
        self.assertEqual(log.read(), 'file')

    def test_logfile2(self):
        """try to get logfile with insufficient arguments (package missing)"""
        br = BuildResult('test', repository='repo', arch='x86_64')
        self.assertRaises(ValueError, br.log)

    @GET('http://localhost/build/test/repo/x86_64/_repository/_builddepinfo?' \
         'view=pkgnames',
         file='builddepinfo.xml')
    def test_builddepinfo1(self):
        """test builddepinfo"""
        br = BuildResult('test', repository='repo', arch='x86_64')
        info = br.builddepinfo()
        self.assertTrue(len(info.package[:]) == 2)
        self.assertEqual(info.package[0].get('name'), 'osc')
        self.assertEqual(info.package[0].source, 'osc')
        self.assertEqual(info.package[0].pkgdep[0], 'python')
        self.assertEqual(info.package[0].pkgdep[1], 'python-devel')
        self.assertEqual(info.package[0].subpkg[0], 'osc')
        self.assertEqual(info.package[0].subpkg[1], 'osc-doc')
        self.assertEqual(info.package[1].get('name'), 'foo')
        self.assertEqual(info.package[1].source, 'foo')
        self.assertEqual(info.package[1].pkgdep, 'bar')
        self.assertEqual(info.package[1].subpkg, 'foo')
        self.assertEqual(info.cycle[0].package[0], 'bar')
        self.assertEqual(info.cycle[0].package[1], 'foobar')

    @GET('http://localhost/build/test/repo/x86_64/foo/_builddepinfo?' \
         'view=revpkgnames',
         file='builddepinfo_revpkgnames.xml')
    def test_builddepinfo2(self):
        """test builddepinfo (reverse=True)"""
        br = BuildResult('test', package='foo', repository='repo',
                         arch='x86_64')
        info = br.builddepinfo(reverse=True)
        self.assertEqual(info.package[0].get('name'), 'foo')
        self.assertEqual(info.package[0].source, 'foo')
        self.assertEqual(info.package[0].pkgdep, 'bar')
        self.assertEqual(info.package[0].subpkg, 'foo')
        self.assertEqual(info.cycle[0].package[0], 'bar')
        self.assertEqual(info.cycle[0].package[1], 'foobar')

    @GET('http://localhost/build/test/repo/x86_64/_repository/_builddepinfo?' \
         'view=pkgnames',
         text='<invalid />')
    def test_builddepinfo3(self):
        """test schema validation"""
        # misuse the binarylist schema
        schema_filename = 'binarylist_simple.xsd'
        BuildResult.BUILDDEPINFO_SCHEMA = self.fixture_file(schema_filename)
        br = BuildResult('test', repository='repo', arch='x86_64')
        self.assertRaises(etree.DocumentInvalid, br.builddepinfo)

    @GET(('http://localhost/build/project/openSUSE_Factory/x86_64/package/'
          '_buildinfo'),
          file='buildinfo1.xml')
    def test_buildinfo1(self):
        """test BuildInfo (simple get)"""
        binfo = BuildInfo('project', 'package', 'openSUSE_Factory', 'x86_64')
        self.assertEqual(binfo.get('project'), 'project')
        self.assertEqual(binfo.get('package'), 'package')
        self.assertEqual(binfo.get('repository'), 'openSUSE_Factory')
        self.assertEqual(binfo.arch, 'x86_64')
        self.assertEqual(binfo.file, 'package.spec')
        # in this case we can calculate it from binfo.file
        self.assertEqual(binfo.get('binarytype'), 'rpm')
        self.assertEqual(len(binfo.bdep[:]), 4)
        # test preinstall
        preinstall = list(binfo.preinstall())
        self.assertEqual(len(preinstall), 2)
        self.assertEqual(preinstall[0].get('name'), 'aaa_base')
        self.assertEqual(preinstall[0].get('version'), '12.2')
        self.assertEqual(preinstall[0].get('release'), '7.1')
        self.assertEqual(preinstall[0].get('arch'), 'x86_64')
        self.assertEqual(preinstall[0].get('project'), 'openSUSE:Factory')
        self.assertEqual(preinstall[0].get('repository'), 'snapshot')
        # second preinstall package
        self.assertEqual(preinstall[1].get('name'), 'attr')
        self.assertEqual(preinstall[1].get('version'), '2.4.46')
        self.assertEqual(preinstall[1].get('release'), '10.2')
        self.assertEqual(preinstall[1].get('arch'), 'x86_64')
        self.assertEqual(preinstall[1].get('project'), 'openSUSE:Factory')
        self.assertEqual(preinstall[1].get('repository'), 'snapshot')
        # test third bdep
        self.assertEqual(binfo.bdep[2].get('name'), 'python-devel')
        self.assertEqual(binfo.bdep[2].get('version'), '2.7.3')
        self.assertEqual(binfo.bdep[2].get('release'), '4.8')
        self.assertEqual(binfo.bdep[2].get('arch'), 'x86_64')
        self.assertEqual(binfo.bdep[2].get('project'), 'openSUSE:Factory')
        self.assertEqual(binfo.bdep[2].get('repository'), 'snapshot')
        # test 4th bdep
        self.assertEqual(binfo.bdep[3].get('name'), 'perl')
        self.assertEqual(binfo.bdep[3].get('version'), '5.16.0')
        self.assertEqual(binfo.bdep[3].get('release'), '4.8')
        self.assertEqual(binfo.bdep[3].get('arch'), 'x86_64')
        self.assertEqual(binfo.bdep[3].get('project'), 'openSUSE:Factory')
        self.assertEqual(binfo.bdep[3].get('repository'), 'snapshot')
        # test path elements
        self.assertEqual(binfo.path[0].get('project'), 'openSUSE:Tools')
        self.assertEqual(binfo.path[0].get('repository'), 'openSUSE_Factory')
        self.assertEqual(binfo.path[1].get('project'), 'openSUSE:Factory')
        self.assertEqual(binfo.path[1].get('repository'), 'snapshot')

    @GET('http://localhost/build/foo/openSUSE_Factory/x86_64/bar/_buildinfo',
         file='buildinfo2.xml')
    def test_buildinfo2(self):
        """test BuildInfo (preinstall, runscripts etc.)"""
        binfo = BuildInfo('foo', 'bar', 'openSUSE_Factory', 'x86_64')
        # check preinstall
        preinstall = list(binfo.preinstall())
        self.assertEqual(len(preinstall), 2)
        self.assertEqual(preinstall[0].get('name'), 'aaa_base')
        self.assertEqual(preinstall[1].get('name'), 'attr')
        # check noinstall
        noinstall = list(binfo.noinstall())
        self.assertEqual(len(noinstall), 4)
        self.assertEqual(noinstall[0].get('name'), 'install-initrd')
        self.assertEqual(noinstall[1].get('name'),
                         'install-initrd-branding-openSUSE')
        self.assertEqual(noinstall[2].get('name'),
                         'install-initrd-branding-SLED')
        self.assertEqual(noinstall[3].get('name'), 'installation-images')
        # check cbinstall
        cbinstall = list(binfo.cbinstall())
        self.assertEqual(len(cbinstall), 2)
        self.assertEqual(cbinstall[0].get('name'), 'foobar')
        self.assertEqual(cbinstall[1].get('name'), 'baz')
        # check cbpreinstall
        cbpreinstall = list(binfo.cbpreinstall())
        self.assertEqual(len(cbpreinstall), 2)
        self.assertEqual(cbpreinstall[0].get('name'), 'abc')
        self.assertEqual(cbpreinstall[1].get('name'), 'def')
        # check vminstall
        vminstall = list(binfo.vminstall())
        self.assertEqual(len(vminstall), 3)
        self.assertEqual(vminstall[0].get('name'), 'libsepol1')
        self.assertEqual(vminstall[1].get('name'), 'libblkid1')
        self.assertEqual(vminstall[2].get('name'), 'libuuid1')
        # check runscripts
        runscripts = list(binfo.runscripts())
        self.assertEqual(len(runscripts), 1)
        self.assertEqual(runscripts[0].get('name'), 'aaa_base')

    @POST(('http://localhost/build/foo/openSUSE_Factory/x86_64/_repository/'
           '_buildinfo'),
          file='buildinfo_uploaded_descr.xml', expfile='test.spec')
    def test_buildinfo3(self):
        """test BuildInfo (specify binarytype)"""
        fname = self.fixture_file('test.spec')
        # if no package is specified _repository is used
        binfo = BuildInfo('foo', repository='openSUSE_Factory', arch='x86_64',
                          binarytype='rpm', data=open(fname, 'r').read())
        self.assertEqual(binfo.get('binarytype'), 'rpm')
        self.assertEqual(binfo.bdep[0].get('name'), 'aaa_base')
        self.assertEqual(len(list(binfo.preinstall())), 1)
        self.assertEqual(len(list(binfo.noinstall())), 0)
        self.assertEqual(len(list(binfo.cbpreinstall())), 0)
        self.assertEqual(len(list(binfo.cbinstall())), 0)
        self.assertEqual(len(list(binfo.vminstall())), 0)
        self.assertEqual(len(list(binfo.runscripts())), 1)

    @POST('http://localhost/build/prj/repo/i586/pkg/_buildinfo',
          file='buildinfo_uploaded_descr.xml', exp='123')
    def test_buildinfo4(self):
        """test BuildInfo (invalid arguments)"""
        self.assertRaises(ValueError, BuildInfo)
        self.assertRaises(ValueError, BuildInfo, project='project')
        self.assertRaises(ValueError, BuildInfo, project='project',
                          repository='repo')
        self.assertRaises(ValueError, BuildInfo, project='project',
                          arch='i586')
        self.assertRaises(ValueError, BuildInfo, arch='i586')
        self.assertRaises(ValueError, BuildInfo, repo='repo')
        self.assertRaises(ValueError, BuildInfo, repo='repo', arch='i586')
        # if data is specified we need a binarytype (we cannot guess it because
        # we haven't enough information - ideally the binarytype is stored in
        # the buildinfo but we can also retrieve it from buildconfig)
        self.assertRaises(ValueError, BuildInfo, 'prj', 'pkg', 'repo', 'i586',
                          data='123')
        self.assertRaises(ValueError, BuildInfo, 'prj',
                          xml_data='<buildinfo />')

    @POST('http://localhost/build/foo/repo/x86_64/bar/_buildinfo',
          file='buildinfo_uploaded_descr.xml', exp='12345')
    def test_buildinfo5(self):
        """test BuildInfo (specify binarytype)"""
        binfo = BuildInfo('foo', 'bar', 'repo', 'x86_64', binarytype='rpm',
                          data='12345')
        self.assertEqual(binfo.path[1].get('project'), 'openSUSE:Factory')
        sio = StringIO()
        binfo.write_to(sio)
        self.assertEqualFile(sio.getvalue(),
                             'buildinfo_uploaded_descr_stored.xml')

    def test_buildinfo6(self):
        """test BuildInfo (from xml data)"""
        fname = self.fixture_file('buildinfo2.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        self.assertEqual(binfo.get('binarytype'), 'rpm')
        self.assertEqual(binfo.bdep[1].get('name'), 'attr')

    def test_buildinfo7(self):
        """test BuildInfo (from xml data - specify binarytype)"""
        fname = self.fixture_file('buildinfo_uploaded_descr.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read(), binarytype='rpm')
        self.assertEqual(binfo.get('binarytype'), 'rpm')
        self.assertEqual(binfo.path[1].get('project'), 'openSUSE:Factory')

    def test_buildinfo8(self):
        """test BuildInfo (from xml data - no binarytype specified)"""
        fname = self.fixture_file('buildinfo_uploaded_descr.xml')
        # cannot calculate binarytype from buildinfo
        self.assertRaises(ValueError, BuildInfo,
                          xml_data=open(fname, 'r').read())
        # the stored xml contains the binarytype attribute
        fname = self.fixture_file('buildinfo_uploaded_descr_stored.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        self.assertEqual(binfo.get('binarytype'), 'rpm')

    @GET(('http://localhost/build/openSUSE%3ATools/Debian_5.0/x86_64/osc/'
          '_buildinfo'),
          file='buildinfo_deb.xml')
    def test_buildinfo9(self):
        """test BuildInfo (deb binarytype)"""
        binfo = BuildInfo('openSUSE:Tools', 'osc', 'Debian_5.0', 'x86_64')
        self.assertEqual(binfo.file, 'osc.dsc')
        self.assertEqual(binfo.get('binarytype'), 'deb')

    def test_buildinfo10(self):
        """test BuildInfo (invalid file text)"""
        # file text has no file extension
        fname = self.fixture_file('buildinfo_invalid_file1.xml')
        self.assertRaises(ValueError, BuildInfo,
                          xml_data=open(fname, 'r').read())
        # file text has unsupported file extension
        fname = self.fixture_file('buildinfo_invalid_file2.xml')
        self.assertRaises(ValueError, BuildInfo,
                          xml_data=open(fname, 'r').read())

    def test_builddependency1(self):
        """teste BuildDependency (rpm filename)"""
        fname = self.fixture_file('buildinfo2.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        self.assertEqual(binfo.get('binarytype'), 'rpm')
        self.assertEqual(binfo.bdep[0].get('name'), 'aaa_base')
        self.assertEqual(binfo.bdep[0].get('version'), '12.2')
        self.assertEqual(binfo.bdep[0].get('release'), '7.1')
        self.assertEqual(binfo.bdep[0].get('arch'), 'x86_64')
        self.assertEqual(binfo.bdep[0].get('filename'),
                         'aaa_base-12.2-7.1.x86_64.rpm')
        self.assertEqual(binfo.bdep[7].get('name'), 'installation-images')
        self.assertEqual(binfo.bdep[7].get('version'), '13.49')
        self.assertEqual(binfo.bdep[7].get('release'), '3.6')
        self.assertEqual(binfo.bdep[7].get('arch'), 'src')
        self.assertEqual(binfo.bdep[7].get('binary'),
                         'installation-images-13.49-3.6.src.rpm')
        # binary element is present (in this case filename is not constructed
        # and the binary value is returned)
        self.assertEqual(binfo.bdep[7].get('filename'),
                         'installation-images-13.49-3.6.src.rpm')
        # test noarch
        self.assertEqual(binfo.bdep[11].get('name'), 'def')
        self.assertEqual(binfo.bdep[11].get('version'), '1.9')
        self.assertEqual(binfo.bdep[11].get('release'), '0')
        self.assertEqual(binfo.bdep[11].get('arch'), 'noarch')
        self.assertEqual(binfo.bdep[11].get('filename'),
                         'def-1.9-0.noarch.rpm')
        # raise ValueError if debfilename is invoked
        self.assertRaises(ValueError, binfo.bdep[0].debfilename)

    def test_builddependency2(self):
        """test BuildDependency (deb filename)"""
        fname = self.fixture_file('buildinfo_deb.xml')
        binfo = BuildInfo(xml_data=open(fname, 'r').read())
        self.assertEqual(binfo.get('binarytype'), 'deb')
        self.assertEqual(binfo.bdep[0].get('name'), 'bash')
        self.assertEqual(binfo.bdep[0].get('version'), '3.2')
        self.assertEqual(binfo.bdep[0].get('release'), '4')
        self.assertEqual(binfo.bdep[0].get('arch'), 'amd64')
        self.assertEqual(binfo.bdep[0].get('filename'),
                         'bash_3.2-4_amd64.deb')
        # test all arch
        self.assertEqual(binfo.bdep[2].get('name'), 'autoconf')
        self.assertEqual(binfo.bdep[2].get('version'), '2.61')
        self.assertEqual(binfo.bdep[2].get('release'), '8')
        self.assertEqual(binfo.bdep[2].get('arch'), 'all')
        self.assertEqual(binfo.bdep[2].get('filename'),
                         'autoconf_2.61-8_all.deb')
        # test without release
        self.assertEqual(binfo.bdep[3].get('name'), 'debhelper')
        self.assertEqual(binfo.bdep[3].get('version'), '7.0.15')
        self.assertIsNone(binfo.bdep[3].get('release'))
        self.assertEqual(binfo.bdep[3].get('arch'), 'all')
        self.assertEqual(binfo.bdep[3].get('filename'),
                         'debhelper_7.0.15_all.deb')
        # raise ValueError if debfilename is invoked
        self.assertRaises(ValueError, binfo.bdep[0].rpmfilename)

    def test_builddependency3(self):
        """test BuildDependency (fromdata binarytype rpm)"""
        bdep = BuildDependency.fromdata('rpm', 'i586', 'foo', '1.4', '0')
        self.assertEqual(bdep.get('binarytype'), 'rpm')
        self.assertEqual(bdep.get('arch'), 'i586')
        self.assertEqual(bdep.get('name'), 'foo')
        self.assertEqual(bdep.get('version'), '1.4')
        self.assertEqual(bdep.get('release'), '0')
        self.assertEqual(bdep.get('filename'), 'foo-1.4-0.i586.rpm')
        self.assertIsNone(bdep.get('project'))
        self.assertIsNone(bdep.get('repository'))
        # release is required for rpm
        self.assertRaises(ValueError, BuildDependency.fromdata,
                          binarytype='rpm', arch='noarch', name='bar',
                          version='3.0')
        # test project and repository
        bdep = BuildDependency.fromdata('rpm', 'noarch', 'bar', '2.7', '1',
                                        'openSUSE:Factory', 'snapshot')
        self.assertEqual(bdep.get('binarytype'), 'rpm')
        self.assertEqual(bdep.get('arch'), 'noarch')
        self.assertEqual(bdep.get('name'), 'bar')
        self.assertEqual(bdep.get('version'), '2.7')
        self.assertEqual(bdep.get('release'), '1')
        self.assertEqual(bdep.get('filename'), 'bar-2.7-1.noarch.rpm')
        self.assertEqual(bdep.get('project'), 'openSUSE:Factory')
        self.assertEqual(bdep.get('repository'), 'snapshot')

    def test_builddependency4(self):
        """test BuildDependency (fromdata binarytype deb)"""
        bdep = BuildDependency.fromdata('deb', 'amd64', 'foo', '1.4', '4')
        self.assertEqual(bdep.get('binarytype'), 'deb')
        self.assertEqual(bdep.get('arch'), 'amd64')
        self.assertEqual(bdep.get('name'), 'foo')
        self.assertEqual(bdep.get('version'), '1.4')
        self.assertEqual(bdep.get('release'), '4')
        self.assertEqual(bdep.get('filename'), 'foo_1.4-4_amd64.deb')
        self.assertIsNone(bdep.get('project'))
        self.assertIsNone(bdep.get('repository'))
        # no release is ok
        bdep = BuildDependency.fromdata('deb', 'all', 'baz', '4.2')
        self.assertEqual(bdep.get('binarytype'), 'deb')
        self.assertEqual(bdep.get('arch'), 'all')
        self.assertEqual(bdep.get('name'), 'baz')
        self.assertEqual(bdep.get('version'), '4.2')
        self.assertIsNone(bdep.get('release'))
        self.assertEqual(bdep.get('filename'), 'baz_4.2_all.deb')
        self.assertIsNone(bdep.get('project'))
        self.assertIsNone(bdep.get('repository'))
        # test project and repository
        bdep = BuildDependency.fromdata('deb', 'amd64', 'bar', '1.0.0', '0',
                                        'Debian:Etch', 'standard')
        self.assertEqual(bdep.get('binarytype'), 'deb')
        self.assertEqual(bdep.get('arch'), 'amd64')
        self.assertEqual(bdep.get('name'), 'bar')
        self.assertEqual(bdep.get('version'), '1.0.0')
        self.assertEqual(bdep.get('release'), '0')
        self.assertEqual(bdep.get('filename'), 'bar_1.0.0-0_amd64.deb')
        self.assertEqual(bdep.get('project'), 'Debian:Etch')
        self.assertEqual(bdep.get('repository'), 'standard')

if __name__ == '__main__':
    unittest.main()
