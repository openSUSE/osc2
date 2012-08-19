import os
import unittest
import tempfile
import shutil

from osc.wc.base import FileConflictError, TransactionListener
from osc.wc.project import Project
from osc.wc.util import WCInconsistentError
from test.osctest import OscTest
from test.httptest import GET, PUT, POST, DELETE
from test.wc.test_package import TL, UPLOAD_REV


def suite():
    return unittest.makeSuite(TestProject)


class ProjectTL(TransactionListener):
    """Avoids package name and filename clashes"""

    def __init__(self, abort=False):
        self._begin = []
        self._finished = []
        self._transfer = []
        self._processed = {}
        self._abort = abort
        self._prefix = []

    def begin(self, name, uinfo):
        self._begin.append(name)
        self._prefix.insert(0, name)
        return not self._abort

    def finished(self, name, aborted=False, abort_reason=''):
        self._prefix.pop(0)
        self._finished.append(name)

    def transfer(self, transfer_type, filename):
        self._transfer.append((transfer_type, filename))

    def processed(self, filename, new_state, old_state):
        key = "%s:%s" % (self._prefix[0], filename)
        self._processed[key] = (new_state, old_state)


class TestProject(OscTest):

    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = os.path.join('wc', 'test_project_fixtures')
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
            self.assertTrue(len(prj.notifier.listener) == 0)
        finally:
            if tmpdir is not None:
                shutil.rmtree(tmpdir)

    def test1_2(self):
        """init (pass additional arguments to the Project's __init__ method)"""
        # nearly identical to test1
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp()
            prj = Project.init(tmpdir, 'openSUSE:Tools',
                               'https://api.opensuse.org',
                               transaction_listener=[None])
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
            self.assertTrue(len(prj.notifier.listener) == 1)
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
        """read invalid project (missing _project)"""
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
        self.assertEqual(uinfo.name, 'prj2')

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
        """test add (no files)"""
        path = self.fixture_file('project')
        pkg_path = os.path.join(path, 'added')
        os.mkdir(pkg_path)
        open(os.path.join(pkg_path, 'foo'), 'w').close()
        open(os.path.join(pkg_path, 'bar'), 'w').close()
        prj = Project(path)
        prj.add('added', no_files=True)
        self.assertEqual(prj._status('added'), 'A')
        self.assertTrue(os.path.islink(os.path.join(pkg_path, '.osc')))
        pkg = prj.package('added')
        self.assertEqual(pkg.status('foo'), '?')
        self.assertEqual(pkg.status('bar'), '?')

    def test10_1(self):
        """test add (specific file)"""
        path = self.fixture_file('project')
        pkg_path = os.path.join(path, 'added')
        os.mkdir(pkg_path)
        open(os.path.join(pkg_path, 'foo'), 'w').close()
        open(os.path.join(pkg_path, 'bar'), 'w').close()
        prj = Project(path)
        prj.add('added', 'foo')
        self.assertEqual(prj._status('added'), 'A')
        self.assertTrue(os.path.islink(os.path.join(pkg_path, '.osc')))
        pkg = prj.package('added')
        self.assertEqual(pkg.status('foo'), 'A')
        self.assertEqual(pkg.status('bar'), '?')

    def test10_2(self):
        """test add (all files)"""
        path = self.fixture_file('project')
        pkg_path = os.path.join(path, 'added')
        os.mkdir(pkg_path)
        open(os.path.join(pkg_path, 'foo'), 'w').close()
        open(os.path.join(pkg_path, 'bar'), 'w').close()
        prj = Project(path)
        prj.add('added')
        self.assertEqual(prj._status('added'), 'A')
        self.assertTrue(os.path.islink(os.path.join(pkg_path, '.osc')))
        pkg = prj.package('added')
        self.assertEqual(pkg.status('foo'), 'A')
        self.assertEqual(pkg.status('bar'), 'A')

    def test10_3(self):
        """test add (all files)"""
        path = self.fixture_file('project')
        pkg_path = os.path.join(path, 'added')
        os.mkdir(pkg_path)
        open(os.path.join(pkg_path, 'foo'), 'w').close()
        open(os.path.join(pkg_path, 'bar'), 'w').close()
        prj = Project(path)
        self.assertRaises(ValueError, prj.add, 'added', 'foo', no_files=True)

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
        self.assertEqual(prj._status('xxx'), 'D')
        # delete bar
        self.assertEqual(prj._status('bar'), 'A')
        prj.remove('bar')
        self.assertEqual(prj._status('bar'), '?')

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

    def test18(self):
        """test remove (also check if the files were removed)"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        self.assertEqual(prj._status('bar'), 'A')
        prj.remove('bar')
        self.assertEqual(prj._status('bar'), '?')
        self._not_exists(path, 'bar')
        self._not_exists(path, 'bar', data=True)

    def test19(self):
        """test remove (all files removed)"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        pkg = prj.package('foo')
        self.assertEqual(pkg.status('file'), ' ')
        self.assertEqual(prj._status('foo'), ' ')
        self._exists(path, 'foo', 'file')
        prj.remove('foo')
        self._exists(path, 'foo')
        self._not_exists(path, 'foo', 'file')
        self.assertEqual(prj._status('foo'), 'D')
        pkg = prj.package('foo')
        self.assertEqual(pkg.status('file'), 'D')

    def test20(self):
        """test remove (remove package with conflicts)"""
        path = self.fixture_file('prj3')
        prj = Project(path)
        self.assertRaises(FileConflictError, prj.remove, 'conflict')

    @GET('http://localhost/source/prj2', file='prj2_list2.xml')
    @GET('http://localhost/source/prj2/foo?foo=bar&rev=latest',
         file='foo_list1.xml')
    @GET(('http://localhost/source/prj2/foo/added'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='foo_added_file')
    def test_update1(self):
        """test update"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        self.assertEqual(prj._status('foo'), ' ')
        prj.update('foo', foo='bar')
        self.assertEqual(prj._status('foo'), ' ')
        fname = os.path.join('prj2', '.osc', '_transaction')
        self.assertFalse(os.path.exists(self.fixture_file(fname)))

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
        # it is ok to use the simple TL class because we have no
        # duplicate keys (for instance a package and a file with the same name)
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
        keys = tl._processed.keys()
        keys.sort()
        self.assertEqual(keys, ['file', 'foo'])
        self.assertEqual(tl._processed['file'], (None, ' '))
        self.assertEqual(tl._processed['foo'], (None, ' '))

    @GET('http://apiurl/source/prj1', file='prj1_list.xml')
    @GET('http://apiurl/source/prj1', file='prj1_list.xml')
    @GET('http://apiurl/source/prj1/foo?rev=latest', file='foo_list2.xml')
    @GET(('http://apiurl/source/prj1/foo/file'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaf'), file='foo_file')
    def test_update5(self):
        """test update (add package)"""
        path = self.fixture_file('prj1')
        # it is ok to use the simple TL class because we have no
        # duplicate keys (for instance a package and a file with the same name)
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
        keys = tl._processed.keys()
        keys.sort()
        self.assertEqual(keys, ['file', 'foo'])
        self.assertEqual(tl._processed['file'], (' ', None))
        self.assertEqual(tl._processed['foo'], (' ', None))

    def test_update6(self):
        """test update (finish pending add transaction)"""
        path = self.fixture_file('prj1_update_resume')
        fname = os.path.join('prj1_update_resume', '.osc', '_transaction')
        self.assertTrue(os.path.exists(self.fixture_file(fname)))
        prj = Project(path, finish_pending_transaction=False)
        self._not_exists(path, 'foo')
        self.assertEqual(prj._status('foo'), '?')
        prj.update('foo')
        self.assertEqual(prj._status('foo'), ' ')
        self._exists(path, 'foo')
        self._exists(path, 'foo', 'file')
        self._exists(path, '.osc', 'data', 'foo')
        self.assertFalse(os.path.exists(self.fixture_file(fname)))

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

    @GET('http://localhost/source/prj2', file='prj2_list4.xml')
    @GET('http://localhost/source/prj2/add?rev=latest', file='add_list1.xml')
    @GET(('http://localhost/source/prj2/add/file'
          '?rev=daaaaaaaaaaaaaaaaaaaaaaaaaaaaaaf'), file='foo_file')
    @GET('http://localhost/source/prj2/foo?rev=latest',
         file='foo_list1.xml')
    @GET(('http://localhost/source/prj2/foo/added'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='foo_added_file')
    def test_update9(self):
        """test update (with project transaction_listener)"""
        path = self.fixture_file('prj2')
        tl = ProjectTL()
        prj = Project(path, transaction_listener=[tl])
        self.assertEqual(prj._status('add'), '?')
        self.assertEqual(prj._status('abc'), 'D')
        self.assertEqual(prj._status('foo'), ' ')
        prj.update('foo', 'abc', 'add')
        # check status after update
        self.assertEqual(prj._status('add'), ' ')
        self.assertEqual(prj._status('foo'), ' ')
        self.assertEqual(prj._status('abc'), '?')
        fname = os.path.join('prj2', '.osc', '_transaction')
        self.assertFalse(os.path.exists(self.fixture_file(fname)))
        # check transaction listener
        keys = tl._processed.keys()
        keys.sort()
        self.assertEqual(keys, ['prj_update:abc', 'prj_update:add',
                                'prj_update:foo', 'update:added',
                                'update:dummy', 'update:file', 'update:foo',
                                'update:modified'])
        self.assertEqual(tl._begin, ['prj_update', 'update', 'update',
                                     'update'])
        self.assertEqual(tl._finished, ['update', 'update', 'update',
                                        'prj_update'])
        self.assertEqual(tl._transfer, [('download', 'file'),
                                        ('download', 'added')])
        self.assertEqual(tl._processed['update:file'], (' ', None))
        self.assertEqual(tl._processed['prj_update:add'], (' ', None))
        # file belong to package foo
        self.assertEqual(tl._processed['update:added'], (' ', None))
        self.assertEqual(tl._processed['prj_update:foo'], (' ', ' '))
        # files belong to package abc
        self.assertEqual(tl._processed['update:dummy'], (None, 'D'))
        self.assertEqual(tl._processed['update:foo'], (None, 'D'))
        self.assertEqual(tl._processed['update:modified'], (None, 'D'))
        self.assertEqual(tl._processed['prj_update:abc'], (None, 'D'))

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
        self.assertEqual(cinfo.name, 'prj2')

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
    @PUT('http://localhost/source/prj2/foo_modified/add?rev=repository',
         expfile='commit_1_add', text=UPLOAD_REV)
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
        self.assertEqual(pkg.status('add'), 'A')
        self.assertEqual(prj._status('foo'), ' ')
        prj.commit('foo_modified')
        self.assertEqual(prj._status('foo'), ' ')
        pkg = prj.package('foo_modified')
        self.assertEqual(pkg.status('file'), ' ')
        self.assertEqual(pkg.status('add'), ' ')

    @GET('http://localhost/source/prj2/bar/_meta', text='<OK/>', code=404)
    @PUT('http://localhost/source/prj2/bar/_meta', text='<OK/>',
         expfile='commit_2_meta.xml')
    @GET('http://localhost/source/prj2/bar?rev=latest',
         file='commit_2_latest.xml')
    @POST('http://localhost/source/prj2/bar?cmd=commitfilelist',
          expfile='commit_2_lfiles.xml', file='commit_2_mfiles.xml')
    @PUT('http://localhost/source/prj2/bar/add?rev=repository',
         expfile='commit_2_add', text=UPLOAD_REV)
    @PUT('http://localhost/source/prj2/bar/add2?rev=repository',
         expfile='commit_2_add2', text=UPLOAD_REV)
    @POST('http://localhost/source/prj2/bar?cmd=commitfilelist',
          expfile='commit_2_lfiles.xml', file='commit_2_files.xml')
    def test_commit2(self):
        """test commit (local state: 'A')"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        pkg = prj.package('bar')
        self.assertEqual(pkg.status('add'), 'A')
        self.assertEqual(pkg.status('add2'), 'A')
        self.assertEqual(prj._status('bar'), 'A')
        prj.commit('bar')
        self.assertEqual(prj._status('bar'), ' ')
        pkg = prj.package('bar')
        self.assertEqual(pkg.status('add'), ' ')
        self.assertEqual(pkg.status('add2'), ' ')
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
    @PUT('http://localhost/source/prj2/bar/add2?rev=repository',
         expfile='commit_2_add2', text=UPLOAD_REV)
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
        tl = TL(abort=False)
        tl_abort = TL(abort=True)
        prj = Project(path, transaction_listener=[tl, tl_abort])
        pkg = prj.package('added')
        self.assertEqual(pkg.status('foo'), 'A')
        self.assertEqual(prj._status('added'), 'A')
        prj.commit('added')
        # this time no abort
        tl = TL(abort=False)
        prj = Project(path, transaction_listener=[tl])
        pkg = prj.package('added')
        self.assertEqual(pkg.status('foo'), 'A')
        self.assertEqual(prj._status('added'), 'A')
        prj.commit('added')
        self.assertEqual(prj._status('added'), ' ')
        pkg = prj.package('added')
        self.assertEqual(pkg.status('foo'), ' ')
        self._exists(path, '.osc', 'data', 'added')
        # check transaction listener
        self.assertEqual(tl._begin, ['prj_commit', 'commit'])
        self.assertEqual(tl._finished, ['commit', 'prj_commit'])
        self.assertEqual(tl._transfer, [('upload', 'foo')])
        self.assertEqual(set(tl._processed.keys()),
                         set(['foo', 'added']))
        self.assertEqual(tl._processed['foo'], (' ', 'A'))
        self.assertEqual(tl._processed['added'], (' ', 'A'))

    @DELETE('http://apiurl/source/prj1/missing', text='<ok/>')
    def test_commit8(self):
        """test commit delete (local state: 'D' (wc doesn't exist))"""
        path = self.fixture_file('prj1')
        tl = TL(abort=False)
        prj = Project(path, transaction_listener=[tl])
        self._not_exists(path, 'missing')
        self._exists(path, '.osc', 'data', 'missing')
        self.assertEqual(prj._status('missing'), 'D')
        prj.commit('missing')
        self.assertEqual(prj._status('missing'), '?')
        self._not_exists(path, '.osc', 'data', 'missing')
        # check transaction listener
        self.assertEqual(tl._begin, ['prj_commit'])
        self.assertEqual(tl._finished, ['prj_commit'])
        self.assertEqual(tl._transfer, [])
        self.assertEqual(tl._processed.keys(), ['missing'])
        self.assertEqual(tl._processed['missing'], (None, 'D'))

    @GET('http://localhost/source/prj2/foo_modified?rev=latest',
         file='commit_1_latest.xml')
    @POST(('http://localhost/source/prj2/foo_modified?cmd=commitfilelist'
           '&comment=foo+bar'), expfile='commit_9_lfiles.xml',
           file='commit_9_mfiles.xml')
    @PUT('http://localhost/source/prj2/foo_modified/file?rev=repository',
         expfile='commit_1_file', text=UPLOAD_REV)
    @POST(('http://localhost/source/prj2/foo_modified?cmd=commitfilelist'
           '&comment=foo+bar'), expfile='commit_9_lfiles.xml',
           file='commit_9_files.xml')
    def test_commit9(self):
        """test commit (specify file + comment; local state ' ')"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        pkg = prj.package('foo_modified')
        self.assertEqual(pkg.status('file'), 'M')
        self.assertEqual(pkg.status('add'), 'A')
        self.assertEqual(prj._status('foo'), ' ')
        todo = {'foo_modified': ['file']}
        prj.commit(package_filenames=todo, comment='foo bar')
        self.assertEqual(prj._status('foo'), ' ')
        pkg = prj.package('foo_modified')
        self.assertEqual(pkg.status('file'), ' ')
        self.assertEqual(pkg.status('add'), 'A')

    @GET('http://localhost/source/prj2/bar/_meta', text='<OK/>', code=404)
    @PUT('http://localhost/source/prj2/bar/_meta', text='<OK/>',
         expfile='commit_2_meta.xml')
    @GET('http://localhost/source/prj2/bar?rev=latest',
         file='commit_2_latest.xml')
    @POST('http://localhost/source/prj2/bar?cmd=commitfilelist&comment=foo',
          expfile='commit_10_lfiles.xml', file='commit_10_mfiles.xml')
    @PUT('http://localhost/source/prj2/bar/add?rev=repository',
         expfile='commit_2_add', text=UPLOAD_REV)
    @POST('http://localhost/source/prj2/bar?cmd=commitfilelist&comment=foo',
          expfile='commit_10_lfiles.xml', file='commit_10_files.xml')
    def test_commit10(self):
        """test commit (specify file + comment; local state 'A')"""
        path = self.fixture_file('prj2')
        prj = Project(path)
        pkg = prj.package('bar')
        self.assertEqual(pkg.status('add'), 'A')
        self.assertEqual(pkg.status('add2'), 'A')
        self.assertEqual(prj._status('bar'), 'A')
        todo = {'bar': ['add']}
        prj.commit(package_filenames=todo, comment='foo')
        self.assertEqual(prj._status('bar'), ' ')
        pkg = prj.package('bar')
        self.assertEqual(pkg.status('add'), ' ')
        self.assertEqual(pkg.status('add2'), 'A')
        self._exists(path, '.osc', 'data', 'bar')

    def test_commit11(self):
        """test commit (package in *packages and package_filenames)"""
        path = self.fixture_file('prj2')
        todo = {'bar': ['add']}
        prj = Project(path)
        self.assertRaises(ValueError, prj.commit, 'bar',
                          package_filenames=todo)

    def test_repair1(self):
        """test repair (missing _project and storefile)"""
        path = self.fixture_file('inv1')
        self._not_exists(path, '_project', store=True)
        self.assertRaises(WCInconsistentError, Project, path)
        self.assertRaises(ValueError, Project.repair, path)
        Project.repair(path, project='inv1')
        self.assertEqual(Project.wc_check(path), ([], '', []))
        self._exists(path, '_project', store=True)
        prj = Project(path)
        self.assertEqual(prj.name, 'inv1')

    @GET('http://localhost/source/inv3/conflict?rev=latest',
         file='conflict_files.xml')
    @GET(('http://localhost/source/inv3/conflict/foo'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='conflict_foo')
    @GET(('http://localhost/source/inv3/conflict/bar'
          '?rev=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'), file='conflict_bar')
    def test_repair2(self):
        """test repair (missing pkg data; state ' ')"""
        path = self.fixture_file('inv3')
        self._not_exists(path, 'conflict', data=True)
        self.assertRaises(WCInconsistentError, Project, path)
        Project.repair(path)
        self.assertEqual(Project.wc_check(path), ([], '', []))
        self._exists(path, 'conflict', data=True)
        prj = Project(path)
        self.assertEqual(prj._status('conflict'), ' ')
        self.assertIsNotNone(prj.package('conflict'))

    def test_repair3(self):
        """test repair (invalid _packages xml)"""
        path = self.fixture_file('inv4')
        self.assertRaises(WCInconsistentError, Project, path)
        self.assertRaises(ValueError, Project.repair, path)
        Project.repair(path, added='A', missing=' ')
        self.assertEqual(Project.wc_check(path), ([], '', []))

    def test_repair4(self):
        """test repair (wc + pkg data missing)"""
        # remove package from _packages in this case
        path = self.fixture_file('inv5')
        self.assertRaises(WCInconsistentError, Project, path)
        Project.repair(path)
        self.assertEqual(Project.wc_check(path), ([], '', []))
        prj = Project(path)
        self.assertEqual(prj._status('missing'), '?')
        self.assertEqual(prj._status('added'), 'A')

if __name__ == '__main__':
    unittest.main()
