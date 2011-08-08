import os
import unittest
import tempfile
import shutil

from osc.wc.base import FileConflictError
from osc.wc.project import Project
from osc.wc.util import WCInconsistentError
from test.osctest import OscTest
from test.httptest import GET, PUT, POST, DELETE
from test.wc.test_package import TL, UPLOAD_REV


def suite():
    return unittest.makeSuite(TestProject)


class TestProject(OscTest):

    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = 'wc/test_project_fixtures'
        super(TestProject, self).__init__(*args, **kwargs)

    def test1(self):
        """init a project dir"""
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp()
            prj = Project.init(tmpdir, 'openSUSE:Tools',
                               'https://api.opensuse.org')
            prj_fname = os.path.join(tmpdir, '.osc', '_project')
            self.assertTrue(os.path.exists(prj_fname))
            self.assertEqual(open(prj_fname, 'r').read(), 'openSUSE:Tools\n')
            pkgs_fname = os.path.join(tmpdir, '.osc', '_packages')
            self.assertTrue(os.path.exists(pkgs_fname))
            self.assertEqual(open(pkgs_fname, 'r').read(), '<packages/>\n')
            apiurl_fname = os.path.join(tmpdir, '.osc', '_apiurl')
            self.assertTrue(os.path.exists(apiurl_fname))
            self.assertEqual(open(apiurl_fname, 'r').read(),
                            'https://api.opensuse.org\n')
            data_dir = os.path.join(tmpdir, '.osc', 'data')
            self.assertTrue(os.path.exists(data_dir))
            self.assertEqual(prj.name, 'openSUSE:Tools')
            self.assertEqual(prj.apiurl, 'https://api.opensuse.org')
            self.assertTrue(len(prj.packages()) == 0)
        finally:
            if tmpdir is not None:
                shutil.rmtree(tmpdir)

    def test2(self):
        """init existing wc"""
        path = self.fixture_file('prj1')
        self.assertRaises(ValueError, Project.init, path,
                          'foo', 'http://localhost')

    def test3(self):
        """read project"""
        path = self.fixture_file('prj1')
        prj = Project(path)
        self.assertEqual(prj.name, 'prj1')
        self.assertEqual(prj.apiurl, 'http://apiurl')
        self.assertTrue(len(prj.packages()) == 2)

    def test4(self):
        """read invalid project (missing storefiles)"""
        path = self.fixture_file('inv1')
        self.assertRaises(WCInconsistentError, Project, path)

    def test5(self):
        """read invalid project (corrupt xml)"""
        path = self.fixture_file('inv2')
        self.assertRaises(WCInconsistentError, Project, path)

    def test6(self):
        """test _status"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        self.assertEqual(prj._status('foo'), ' ')
        self.assertEqual(prj._status('bar'), 'A')
        self.assertEqual(prj._status('abc'), 'D')
        self.assertEqual(prj._status('xxx'), '!')
        # del is not ! because it's also marked for deletion
        self.assertEqual(prj._status('del'), 'D')
        self.assertEqual(prj._status('asdf'), '?')

    @GET('http://localhost/source/prj2', file='prj2_list1.xml')
    def test7(self):
        """test _calculate_updateinfo"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        uinfo = prj._calculate_updateinfo()
        self.assertEqual(uinfo.candidates, ['foo', 'abc'])
        self.assertEqual(uinfo.added, ['osc'])
        self.assertEqual(uinfo.deleted, ['del', 'foo_modified'])
        self.assertEqual(uinfo.conflicted, ['xxx'])

    @GET('http://localhost/source/prj2', file='prj2_list2.xml')
    def test8(self):
        """test _calculate_updateinfo 2"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        uinfo = prj._calculate_updateinfo()
        self.assertEqual(uinfo.candidates, ['foo', 'foo_modified'])
        self.assertEqual(uinfo.added, ['osc'])
        self.assertEqual(uinfo.deleted, ['abc', 'xxx', 'del'])
        # local state: A
        self.assertEqual(uinfo.conflicted, ['bar'])

    @GET('http://localhost/source/prj2', file='prj2_list2.xml')
    def test8_1(self):
        """test _calculate_updateinfo 3 (specify packages)"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        uinfo = prj._calculate_updateinfo('foo', 'osc', 'del')
        self.assertEqual(uinfo.candidates, ['foo'])
        self.assertEqual(uinfo.added, ['osc'])
        self.assertEqual(uinfo.deleted, ['del'])
        # no conflicts because bar shouldn't be added/updated
        self.assertEqual(uinfo.conflicted, [])

    @GET('http://localhost/source/prj2', text='<directory count="0"/>')
    def test9(self):
        """test _calculate_updateinfo 3 (empty package list)"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        self.assertEqual(prj._status('bar'), 'A')
        uinfo = prj._calculate_updateinfo()
        self.assertEqual(uinfo.candidates, [])
        self.assertEqual(uinfo.added, [])
        self.assertEqual(uinfo.deleted, ['foo', 'abc', 'xxx', 'del',
                                         'foo_modified'])
        self.assertEqual(uinfo.conflicted, [])

    def test10(self):
        """test add"""
        path = self.fixture_file('project')
        pkg_path = os.path.join(path, 'added')
        os.mkdir(pkg_path)
        prj = Project(path)
        prj.add('added')
        self.assertEqual(prj._status('added'), 'A')
        self.assertTrue(os.path.islink(os.path.join(pkg_path, '.osc')))

    def test11(self):
        """add already existing package"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        self.assertRaises(ValueError, prj.add, 'bar')

    def test12(self):
        """add untracked pkg"""
        path = self.fixture_file('project')
        prj = Project(path)
        self.assertRaises(ValueError, prj.add, 'untracked_pkg')

    def test13(self):
        """add non-existent package"""
        path = self.fixture_file('project')
        prj = Project(path)
        self.assertRaises(ValueError, prj.add, 'nonexistent')

    def test14(self):
        """do not add deleted package"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        self.assertEqual(prj._status('abc'), 'D')
        pkg_dir = self.fixture_file('prj2', 'abc')
        shutil.rmtree(pkg_dir)
        os.mkdir(pkg_dir)
        self.assertEqual(prj._status('abc'), 'D')
        self.assertRaises(ValueError, prj.add, 'abc')
        self.assertEqual(prj._status('abc'), 'D')

    def test15(self):
        """test remove"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        # delete foo
        self.assertEqual(prj._status('foo'), ' ')
        prj.remove('foo')
        self.assertEqual(prj._status('foo'), 'D')
        self.assertTrue(os.path.exists(self.fixture_file('prj2', 'foo')))
        # delete xxx
        self.assertEqual(prj._status('xxx'), '!')
        prj.remove('xxx')
        self.assertEqual(prj._status('foo'), 'D')
        # delete bar
        self.assertEqual(prj._status('bar'), 'A')
        prj.remove('bar')
        self.assertEqual(prj._status('bar'), '?')
        # TODO: uncomment me later
        # self.assertFalse(os.path.exists(self.fixture_file('prj2', 'bar')))

    def test16(self):
        """delete untracked package"""
        path = self.fixture_file('project')
        prj = Project(path)
        self.assertRaises(ValueError, prj.remove, 'untracked_pkg')

    def test17(self):
        """delete non-existent package"""
        path = self.fixture_file('project')
        prj = Project(path)
        self.assertRaises(ValueError, prj.remove, 'nonexistent')

    @GET('http://localhost/source/prj2', file='prj2_list2.xml')
    @GET('http://localhost/source/prj2/foo?rev=latest',
         file='foo_list1.xml')
    @GET(('http://localhost/source/prj2/foo/added'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='foo_added_file')
    def test_update1(self):
        """test update"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        self.assertEqual(prj._status('foo'), ' ')
        prj.update('foo')
        self.assertEqual(prj._status('foo'), ' ')

    @GET('http://localhost/source/prj2', file='prj2_list3.xml')
    def test_update2(self):
        """test update (delete package; local state 'D')"""
        path = self.fixture_file('prj2')
        self._exists(path, 'abc')
        self._exists(path, 'abc', 'modified')
        self._exists(path, 'abc', 'untracked')
        self._exists(path, 'abc', '.osc')
        self._exists(path, '.osc', 'data', 'abc')
        prj = Project(path)
        self.assertEqual(prj._status('abc'), 'D')
        prj.update('abc')
        self.assertEqual(prj._status('abc'), '?')
        self._exists(path, 'abc')
        self._exists(path, 'abc', 'modified')
        self._exists(path, 'abc', 'untracked')
        self._not_exists(path, 'abc', '.osc')
        self._not_exists(path, '.osc', 'data', 'abc')

    @GET('http://localhost/source/prj2', file='prj2_list3.xml')
    def test_update3(self):
        """test update (delete package; local state '!')"""
        path = self.fixture_file('prj2')
        self._not_exists(path, 'xxx')
        prj = Project(path)
        prj.update('xxx')
        self.assertEqual(prj._status('xxx'), '?')
        self._not_exists(path, '.osc', 'data', 'xxx')

    @GET('http://localhost/source/prj2', file='prj2_list3.xml')
    def test_update4(self):
        """test update (delete package: local state ' ')"""
        path = self.fixture_file('prj2')
        tl = TL(abort=False)
        self._exists(path, 'foo')
        self._exists(path, '.osc', 'data', 'foo')
        prj = Project(path, transaction_listener=[tl])
        self.assertEqual(prj._status('foo'), ' ')
        prj.update('foo')
        self.assertEqual(prj._status('foo'), '?')
        self._not_exists(path, 'foo')
        self._not_exists(path, '.osc', 'data', 'foo')
        # check transaction listener
        self.assertEqual(tl._begin, ['prj_update', 'update'])
        self.assertEqual(tl._finished, ['update', 'prj_update'])
        self.assertEqual(tl._transfer, [])
        self.assertEqual(tl._processed.keys(), ['file'])
        self.assertEqual(tl._processed['file'], None)

    @GET('http://apiurl/source/prj1', file='prj1_list.xml')
    @GET('http://apiurl/source/prj1', file='prj1_list.xml')
    @GET('http://apiurl/source/prj1/foo?rev=latest', file='foo_list2.xml')
    @GET(('http://apiurl/source/prj1/foo/file'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaf'), file='foo_file')
    def test_update5(self):
        """test update (add package)"""
        path = self.fixture_file('prj1')
        tl = TL(abort=False)
        tl_abort = TL(abort=True)
        prj = Project(path, transaction_listener=[tl, tl_abort])
        self._not_exists(path, 'foo')
        self.assertEqual(prj._status('foo'), '?')
        prj.update('foo')
        # no abort this time
        tl = TL(abort=False)
        prj = Project(path, transaction_listener=[tl])
        self._not_exists(path, 'foo')
        self.assertEqual(prj._status('foo'), '?')
        prj.update('foo')
        self.assertEqual(prj._status('foo'), ' ')
        self._exists(path, 'foo')
        self._exists(path, 'foo', 'file')
        self._exists(path, '.osc', 'data', 'foo')
        # check transaction listener
        self.assertEqual(tl._begin, ['prj_update', 'update'])
        self.assertEqual(tl._finished, ['update', 'prj_update'])
        self.assertEqual(tl._transfer, [('download', 'file')])
        self.assertEqual(tl._processed.keys(), ['file'])
        self.assertEqual(tl._processed['file'], ' ')
 
    def test_update6(self):
        """test update (finish pending add transaction)"""
        path = self.fixture_file('prj1_update_resume')
        prj = Project(path, finish_pending_transaction=False)
        self._not_exists(path, 'foo')
        self.assertEqual(prj._status('foo'), '?')
        prj.update('foo')
        self.assertEqual(prj._status('foo'), ' ')
        self._exists(path, 'foo')
        self._exists(path, 'foo', 'file')
        self._exists(path, '.osc', 'data', 'foo')

    def test_update7(self):
        """test update (finish pending add transaction auto)"""
        path = self.fixture_file('prj1_update_resume')
        self._not_exists(path, 'foo')
        prj = Project(path, finish_pending_transaction=True)
        self.assertEqual(prj._status('foo'), ' ')
        self._exists(path, 'foo')
        self._exists(path, 'foo', 'file')
        self._exists(path, '.osc', 'data', 'foo')

    @GET('http://localhost/source/prj3', file='prj2_list3.xml')
    def test_update8(self):
        """test update (package with a conflicted file)"""
        path = self.fixture_file('prj3')
        prj = Project(path)
        pkg = prj.package('conflict')
        self.assertEqual(pkg.status('conflict'), 'C')
        self.assertEqual(prj._status('conflict'), ' ')
        # Note: package conflict would be deleted (if update were possible)
        self.assertRaises(FileConflictError, prj.update, 'conflict')
        self.assertEqual(prj._status('conflict'), ' ')
        pkg = prj.package('conflict')
        self.assertEqual(pkg.status('conflict'), 'C')

    def test_commitinfo1(self):
        """test commitinfo (complete project)"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        self.assertEqual(prj._status('foo'), ' ')
        self.assertEqual(prj._status('bar'), 'A')
        self.assertEqual(prj._status('abc'), 'D')
        self.assertEqual(prj._status('xxx'), '!')
        self.assertEqual(prj._status('del'), 'D')
        cinfo = prj._calculate_commitinfo()
        self.assertEqual(cinfo.unchanged, ['foo'])
        self.assertEqual(cinfo.added, ['bar'])
        self.assertEqual(cinfo.deleted, ['abc', 'del'])
        self.assertEqual(cinfo.modified, ['foo_modified'])
        self.assertEqual(cinfo.conflicted, ['xxx'])

    def test_commitinfo2(self):
        """test commitinfo (only specified packages)"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        self.assertEqual(prj._status('foo'), ' ')
        self.assertEqual(prj._status('foo_modified'), ' ')
        cinfo = prj._calculate_commitinfo('foo', 'foo_modified')
        self.assertEqual(cinfo.unchanged, ['foo'])
        self.assertEqual(cinfo.added, [])
        self.assertEqual(cinfo.deleted, [])
        self.assertEqual(cinfo.modified, ['foo_modified'])
        self.assertEqual(cinfo.conflicted, [])

    @GET('http://localhost/source/prj2/foo_modified?rev=latest',
         file='commit_1_latest.xml')
    @POST('http://localhost/source/prj2/foo_modified?cmd=commitfilelist',
          expfile='commit_1_lfiles.xml', file='commit_1_mfiles.xml')
    @PUT('http://localhost/source/prj2/foo_modified/file?rev=repository',
         expfile='commit_1_file', text=UPLOAD_REV)
    @POST('http://localhost/source/prj2/foo_modified?cmd=commitfilelist',
          expfile='commit_1_lfiles.xml', file='commit_1_files.xml')
    def test_commit1(self):
        """test commit (local state: ' ')"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        pkg = prj.package('foo_modified')
        self.assertEqual(pkg.status('file'), 'M')
        self.assertEqual(prj._status('foo'), ' ')
        prj.commit('foo_modified')
        self.assertEqual(prj._status('foo'), ' ')
        pkg = prj.package('foo_modified')
        self.assertEqual(pkg.status('file'), ' ')

    @GET('http://localhost/source/prj2/bar/_meta', text='<OK/>', code=404)
    @PUT('http://localhost/source/prj2/bar/_meta', text='<OK/>',
         expfile='commit_2_meta.xml')
    @GET('http://localhost/source/prj2/bar?rev=latest',
         file='commit_2_latest.xml')
    @POST('http://localhost/source/prj2/bar?cmd=commitfilelist',
          expfile='commit_2_lfiles.xml', file='commit_2_mfiles.xml')
    @PUT('http://localhost/source/prj2/bar/add?rev=repository',
         expfile='commit_2_add', text=UPLOAD_REV)
    @POST('http://localhost/source/prj2/bar?cmd=commitfilelist',
          expfile='commit_2_lfiles.xml', file='commit_2_files.xml')
    def test_commit2(self):
        """test commit (local state: 'A')"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        pkg = prj.package('bar')
        self.assertEqual(pkg.status('add'), 'A')
        self.assertEqual(prj._status('bar'), 'A')
        prj.commit('bar')
        self.assertEqual(prj._status('bar'), ' ')
        pkg = prj.package('bar')
        self.assertEqual(pkg.status('add'), ' ')
        self._exists(path, '.osc', 'data', 'bar')

    @DELETE('http://localhost/source/prj2/abc', text='<ok/>')
    def test_commit3(self):
        """test commit (local state: 'D')"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        pkg = prj.package('abc')
        self.assertEqual(pkg.status('modified'), 'D')
        self.assertEqual(pkg.status('untracked'), '?')
        self.assertEqual(prj._status('abc'), 'D')
        prj.commit('abc')
        self.assertEqual(prj._status('abc'), '?')
        self._exists(path, 'abc')
        self._exists(path, 'abc', 'modified')
        self._exists(path, 'abc', 'untracked')
        self._not_exists(path, 'abc', '.osc')
        self._not_exists(path, '.osc', 'data', 'abc')

    @GET('http://localhost/source/prj2/bar/_meta', file='commit_2_meta.xml')
    @GET('http://localhost/source/prj2/bar?rev=latest',
         file='commit_2_latest.xml')
    @POST('http://localhost/source/prj2/bar?cmd=commitfilelist',
          expfile='commit_2_lfiles.xml', file='commit_2_mfiles.xml')
    @PUT('http://localhost/source/prj2/bar/add?rev=repository',
         expfile='commit_2_add', text=UPLOAD_REV)
    @POST('http://localhost/source/prj2/bar?cmd=commitfilelist',
          expfile='commit_2_lfiles.xml', file='commit_2_files.xml')
    def test_commit4(self):
        """test commit (same as test_commit4 but remote package exists)"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        pkg = prj.package('bar')
        self.assertEqual(pkg.status('add'), 'A')
        self.assertEqual(prj._status('bar'), 'A')
        prj.commit('bar')
        self.assertEqual(prj._status('bar'), ' ')
        pkg = prj.package('bar')
        self.assertEqual(pkg.status('add'), ' ')
        self._exists(path, '.osc', 'data', 'bar')

    def test_commit5(self):
        """test commit (finish pending transaction (delete))"""
        path = self.fixture_file('prj2_commit_resume')
        prj = Project(path, finish_pending_transaction=False)
        self.assertEqual(prj._status('abc'), 'D')
        prj.commit('abc')
        self.assertEqual(prj._status('abc'), '?')

    def test_commit6(self):
        """test commit (package with a conflicted file)"""
        path = self.fixture_file('prj3')
        prj = Project(path)
        pkg = prj.package('conflict')
        self.assertEqual(pkg.status('conflict'), 'C')
        self.assertEqual(prj._status('conflict'), ' ')
        self.assertRaises(FileConflictError, prj.commit, 'conflict')
        self.assertEqual(prj._status('conflict'), ' ')
        pkg = prj.package('conflict')
        self.assertEqual(pkg.status('conflict'), 'C')

    @GET('http://apiurl/source/prj1/added/_meta', text='<OK/>', code=404)
    @PUT('http://apiurl/source/prj1/added/_meta', text='<OK/>',
         expfile='commit_7_meta.xml')
    @GET('http://apiurl/source/prj1/added?rev=latest',
         text='<directory name="added"/>')
    @POST('http://apiurl/source/prj1/added?cmd=commitfilelist',
          expfile='commit_7_lfiles.xml', file='commit_7_mfiles.xml')
    @PUT('http://apiurl/source/prj1/added/foo?rev=repository',
         expfile='commit_7_foo', text=UPLOAD_REV)
    @POST('http://apiurl/source/prj1/added?cmd=commitfilelist',
          expfile='commit_7_lfiles.xml', file='commit_7_files.xml')
    def test_commit7(self):
        """test commit (local state: 'A')"""
        path = self.fixture_file('prj1')
        prj = Project(path)
        pkg = prj.package('added')
        self.assertEqual(pkg.status('foo'), 'A')
        self.assertEqual(prj._status('added'), 'A')
        prj.commit('added')
        self.assertEqual(prj._status('added'), ' ')
        pkg = prj.package('added')
        self.assertEqual(pkg.status('foo'), ' ')
        self._exists(path, '.osc', 'data', 'added')

    @DELETE('http://apiurl/source/prj1/missing', text='<ok/>')
    def test_commit8(self):
        """test commit delete (local state: 'D' (wc doesn't exist))"""
        path = self.fixture_file('prj1')
        prj = Project(path)
        self._not_exists(path, 'missing')
        self._exists(path, '.osc', 'data', 'missing')
        self.assertEqual(prj._status('missing'), 'D')
        prj.commit('missing')
        self.assertEqual(prj._status('missing'), '?')
        self._not_exists(path, '.osc', 'data', 'missing')

if __name__ == '__main__':
    unittest.main()
