import os
import unittest

from osc2.oscargs import OscArgs
from test.osctest import OscTest


def suite():
    return unittest.makeSuite(TestOscArgs)


class Sub(OscArgs):
    def unresolved(self, info, name):
        info.add(name, None)


class TestOscArgs(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = os.path.join('wc', 'test_util_fixtures')
        super(TestOscArgs, self).__init__(*args, **kwargs)

    def test1(self):
        """test simple"""
        oargs = OscArgs('api://project/package')
        args = 'http://localhost://foo/bar'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'http://localhost')
        self.assertEqual(info.project, 'foo')
        self.assertEqual(info.package, 'bar')
        # error
        self.assertRaises(ValueError, oargs.resolve,
                          'http://localhost://project/package/')
        self.assertRaises(ValueError, oargs.resolve,
                          'http://localhost://project/')

    def test2(self):
        """test optional args"""
        oargs = OscArgs('api://project/package?')
        args = 'http://localhost://foo'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'http://localhost')
        self.assertEqual(info.project, 'foo')
        self.assertFalse(hasattr(info, 'package'))
        # this time with package
        args = 'http://localhost://foo/bar'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'http://localhost')
        self.assertEqual(info.project, 'foo')
        self.assertEqual(info.package, 'bar')
        # test with trailing slash
        args = 'http://localhost://foo/'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'http://localhost')
        self.assertEqual(info.project, 'foo')
        self.assertFalse(hasattr(info, 'package'))
        # error
        self.assertRaises(ValueError, oargs.resolve, 'http://localhost://')
        self.assertRaises(ValueError, oargs.resolve,
                          'http://localhost://project/package/')

    def test3(self):
        """test multiple optional args"""
        oargs = OscArgs('api://project?/package?')
        args = 'http://localhost://'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'http://localhost')
        self.assertFalse(hasattr(info, 'project'))
        self.assertFalse(hasattr(info, 'package'))
        # api://project
        args = 'http://localhost://foobar'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'http://localhost')
        self.assertEqual(info.project, 'foobar')
        self.assertFalse(hasattr(info, 'package'))
        # api://project/package
        args = 'http://localhost://foobar/somepkg'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'http://localhost')
        self.assertEqual(info.project, 'foobar')
        self.assertEqual(info.package, 'somepkg')
        # leave out project and package (pathological case)
        args = 'http://localhost:///'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'http://localhost')
        self.assertFalse(hasattr(info, 'project'))
        self.assertFalse(hasattr(info, 'package'))
        # error
        self.assertRaises(ValueError, oargs.resolve, 'foo')
        # error: leave out project and package but append '/'
        self.assertRaises(ValueError, oargs.resolve, 'http://localhost:////')

    def test4(self):
        """test some "pathological" cases.
        They are supported but won't be used in osc (so far).
        """
        oargs = OscArgs('api://project?/package')
        args = 'obs://openSUSE:Factory/osc'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'openSUSE:Factory')
        self.assertEqual(info.package, 'osc')
        # leave out project
        args = 'obs:///osc'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertFalse(hasattr(info, 'project'))
        self.assertEqual(info.package, 'osc')
        # error
        self.assertRaises(ValueError, oargs.resolve, 'obs://')
        self.assertRaises(ValueError, oargs.resolve, 'obs://project')
        self.assertRaises(ValueError, oargs.resolve, 'obs://project/')

    def test5(self):
        """no api"""
        oargs = OscArgs('repository?/arch?')
        args = 'repo/arch'
        info = oargs.resolve(args)
        self.assertEqual(info.repository, 'repo')
        self.assertEqual(info.arch, 'arch')
        # no arch
        args = 'repo'
        info = oargs.resolve(args)
        self.assertEqual(info.repository, 'repo')
        self.assertFalse(hasattr(info, 'arch'))
        # no arch but with trailing slash
        args = 'repo/'
        info = oargs.resolve(args)
        self.assertEqual(info.repository, 'repo')
        self.assertFalse(hasattr(info, 'arch'))
        # no repo but arch
        args = '/x86_64'
        info = oargs.resolve(args)
        self.assertFalse(hasattr(info, 'repository'))
        self.assertEqual(info.arch, 'x86_64')
        # no repo and no arch
        args = ''
        info = oargs.resolve(args)
        self.assertFalse(hasattr(info, 'repository'))
        self.assertFalse(hasattr(info, 'arch'))
        # error trailing slash
        self.assertRaises(ValueError, oargs.resolve, '/i586/')

    def test6(self):
        """test > 2 components"""
        oargs = OscArgs('foo/bar/baz')
        args = 'a/b/c'
        info = oargs.resolve(args)
        self.assertEqual(info.foo, 'a')
        self.assertEqual(info.bar, 'b')
        self.assertEqual(info.baz, 'c')
        # error
        self.assertRaises(ValueError, oargs.resolve, 'a/b/c/')
        self.assertRaises(ValueError, oargs.resolve, 'a/b//')
        self.assertRaises(ValueError, oargs.resolve, '/b//')
        self.assertRaises(ValueError, oargs.resolve, '///')

    def test7(self):
        """test > 2 components (optional)"""
        oargs = OscArgs('foo?/bar?/baz')
        args = 'a/b/c'
        info = oargs.resolve(args)
        self.assertEqual(info.foo, 'a')
        self.assertEqual(info.bar, 'b')
        self.assertEqual(info.baz, 'c')
        # leave out foo
        args = '/b/c'
        info = oargs.resolve(args)
        self.assertFalse(hasattr(info, 'foo'))
        self.assertEqual(info.bar, 'b')
        self.assertEqual(info.baz, 'c')
        # leave out foo and bar
        args = '//c'
        info = oargs.resolve(args)
        self.assertFalse(hasattr(info, 'foo'))
        self.assertFalse(hasattr(info, 'bar'))
        self.assertEqual(info.baz, 'c')
        # leave out bar only
        args = 'a//c'
        info = oargs.resolve(args)
        self.assertEqual(info.foo, 'a')
        self.assertFalse(hasattr(info, 'bar'))
        self.assertEqual(info.baz, 'c')
        # error
        self.assertRaises(ValueError, oargs.resolve, '/a/b/c')
        self.assertRaises(ValueError, oargs.resolve, 'c')

    def test8(self):
        """test multiple entries"""
        oargs = OscArgs('api://project/package?', 'repository?/arch?')
        args = ('http://localhost://prj', 'repo')
        info = oargs.resolve(*args)
        self.assertEqual(info.project, 'prj')
        self.assertFalse(hasattr(info, 'package'))
        self.assertEqual(info.repository, 'repo')
        self.assertFalse(hasattr(info, 'arch'))
        # no repo and arch
        args = ('obs://prj/pkg', '')
        info = oargs.resolve(*args)
        self.assertEqual(info.project, 'prj')
        self.assertEqual(info.package, 'pkg')
        self.assertFalse(hasattr(info, 'repository'))
        self.assertFalse(hasattr(info, 'arch'))
        # error
        self.assertRaises(ValueError, oargs.resolve, '', 'repo/arch')

    def test9(self):
        """test multiple entries (all components optional)"""
        oargs = OscArgs('foo?/bar?', 'x?/y?')
        args = ('a/b', 'c/d')
        info = oargs.resolve(*args)
        self.assertEqual(info.foo, 'a')
        self.assertEqual(info.bar, 'b')
        self.assertEqual(info.x, 'c')
        self.assertEqual(info.y, 'd')
        # leave out x and y
        args = ('a/b', '')
        info = oargs.resolve(*args)
        self.assertEqual(info.foo, 'a')
        self.assertEqual(info.bar, 'b')
        self.assertFalse(hasattr(info, 'x'))
        self.assertFalse(hasattr(info, 'y'))
        # leave out foo and bar (just use '/')
        args = ('/', 'c/d')
        info = oargs.resolve(*args)
        self.assertFalse(hasattr(info, 'foo'))
        self.assertFalse(hasattr(info, 'bar'))
        self.assertEqual(info.x, 'c')
        self.assertEqual(info.y, 'd')
        # leave out foo and bar
        args = ('', 'c/d')
        info = oargs.resolve(*args)
        self.assertFalse(hasattr(info, 'foo'))
        self.assertFalse(hasattr(info, 'bar'))
        self.assertEqual(info.x, 'c')
        self.assertEqual(info.y, 'd')
        # leave out everything
        args = ('', '')
        info = oargs.resolve(*args)
        self.assertFalse(hasattr(info, 'foo'))
        self.assertFalse(hasattr(info, 'bar'))
        self.assertFalse(hasattr(info, 'x'))
        self.assertFalse(hasattr(info, 'y'))
        # error
        self.assertRaises(ValueError, oargs.resolve, 'a', 'c', 'f')

    def test10(self):
        """test project with project and package wc"""
        oargs = OscArgs('api://project', path=self.fixture_file('project'))
        args = 'obs://openSUSE:Factory'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'openSUSE:Factory')
        # empty args
        args = ''
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'http://localhost')
        self.assertEqual(info.project, 'project')
        # error (package wc)
        path = self.fixture_file('package')
        self.assertRaises(ValueError, oargs.resolve, '', path=path)
        # error
        self.assertRaises(ValueError, oargs.resolve, 'obs://')

    def test11(self):
        """test project package with project and package wc"""
        oargs = OscArgs('api://project/package',
                        path=self.fixture_file('package'))
        args = 'obs://openSUSE:Factory/osc'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'openSUSE:Factory')
        self.assertEqual(info.package, 'osc')
        # empty args
        args = ''
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'https://localhost')
        self.assertEqual(info.project, 'foobar')
        self.assertEqual(info.package, 'package')
        # error (project wc)
        path = self.fixture_file('project')
        self.assertRaises(ValueError, oargs.resolve, '', path=path)
        # error
        self.assertRaises(ValueError, oargs.resolve, 'obs://project')

    def test12(self):
        """test project package with wc (package optional)"""
        oargs = OscArgs('api://project/package?',
                        path=self.fixture_file('package'))
        args = 'obs://openSUSE:Factory/osc'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'openSUSE:Factory')
        self.assertEqual(info.package, 'osc')
        # empty args
        args = ''
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'https://localhost')
        self.assertEqual(info.project, 'foobar')
        self.assertEqual(info.package, 'package')
        # leave out package
        args = 'obs://openSUSE:Factory'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'openSUSE:Factory')
        self.assertFalse(hasattr(info, 'package'))
        # error (project wc)
        # disable this behaviour for now (needs further thinking)
        # path = self.fixture_file('project')
        # self.assertRaises(ValueError, oargs.resolve, '', path=path)
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'openSUSE:Factory')
        self.assertFalse(hasattr(info, 'package'))

    def test13(self):
        """test project with wc and multiple entries"""
        path = self.fixture_file('project')
        oargs = OscArgs('api://project?', 'api(tgt)://tgt_project', path=path)
        args = ('obs://foo', 'local://bar')
        info = oargs.resolve(*args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'foo')
        self.assertEqual(info.tgt_apiurl, 'local')
        self.assertEqual(info.tgt_project, 'bar')
        # leave out project
        args = ('obs://', 'local://bar')
        info = oargs.resolve(*args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertFalse(hasattr(info, 'project'))
        self.assertEqual(info.tgt_apiurl, 'local')
        self.assertEqual(info.tgt_project, 'bar')
        # read apiurl+project from project wc
        args = ('', 'local://bar')
        info = oargs.resolve(*args)
        self.assertEqual(info.apiurl, 'http://localhost')
        self.assertEqual(info.project, 'project')
        self.assertEqual(info.tgt_apiurl, 'local')
        self.assertEqual(info.tgt_project, 'bar')
        # error: use package wc
        path = self.fixture_file('package')
        self.assertRaises(ValueError, oargs.resolve, 'local://bar', path=path)
        # error: '' do not match second entry
        self.assertRaises(ValueError, oargs.resolve, '', '')

    def test14(self):
        """test name clashes/wrong usage (ignore name clashes)"""
        path = self.fixture_file('project')
        oargs = OscArgs('api://project?', 'api://project/tgt_package',
                        path=path)
        args = ('obs://openSUSE:Factory', 'local://prj/pkg')
        info = oargs.resolve(*args)
        self.assertEqual(info.apiurl, 'local')
        self.assertEqual(info.project, 'prj')
        self.assertEqual(info.tgt_package, 'pkg')
        # empty args - 2nd entry has a project component
        # so its also resolved via the project wc
        args = ('', '')
        info = oargs.resolve(*args)
        self.assertEqual(info.apiurl, 'http://localhost')
        self.assertEqual(info.project, 'project')
        self.assertFalse(hasattr(info, 'package'))

    def test15(self):
        """test subclassing 1"""
        oargs = Sub('api://project/package?')
        args = 'obs://foo/bar'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'foo')
        self.assertEqual(info.package, 'bar')
        # leave out package
        args = 'obs://foo'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'foo')
        self.assertIsNone(info.package)

    def test16(self):
        """test subclassing 2"""
        oargs = Sub('api://project?/package?')
        args = 'obs://foo/bar'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'foo')
        self.assertEqual(info.package, 'bar')
        # leave out project and package
        args = 'obs://'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertIsNone(info.project)
        self.assertIsNone(info.package)

    def test17(self):
        """test @ separator"""
        oargs = OscArgs('api://project/package@rev')
        args = 'api://prj/pkg@123'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'api')
        self.assertEqual(info.project, 'prj')
        self.assertEqual(info.package, 'pkg')
        self.assertEqual(info.rev, '123')

    def test18(self):
        """test @ separator (optional)"""
        oargs = OscArgs('api://project/package@rev?')
        args = 'api://prj/pkg'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'api')
        self.assertEqual(info.project, 'prj')
        self.assertEqual(info.package, 'pkg')
        self.assertFalse(hasattr(info, 'rev'))
        # this time with rev
        args = 'api://prj/pkg@123'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'api')
        self.assertEqual(info.project, 'prj')
        self.assertEqual(info.package, 'pkg')
        self.assertEqual(info.rev, '123')

    def test19(self):
        """test @ separator (pathological cases)"""
        oargs = OscArgs('api://project/package?@rev?')
        args = 'api://prj/pkg'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'api')
        self.assertEqual(info.project, 'prj')
        self.assertEqual(info.package, 'pkg')
        self.assertFalse(hasattr(info, 'rev'))
        # this time with rev
        args = 'api://prj/pkg@123'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'api')
        self.assertEqual(info.project, 'prj')
        self.assertEqual(info.package, 'pkg')
        self.assertEqual(info.rev, '123')
        # now leave out package
        args = 'api://prj/@123'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'api')
        self.assertEqual(info.project, 'prj')
        self.assertFalse(hasattr(info, 'package'))
        self.assertEqual(info.rev, '123')

    def test20(self):
        """test mix between @ and / separators"""
        oargs = OscArgs('foo/bar@baz')
        args = 'foo@bar/baz'
        self.assertRaises(ValueError, oargs.resolve, args)
        args = 'foo/bar/baz'
        self.assertRaises(ValueError, oargs.resolve, args)
        args = 'foo@bar@baz'
        self.assertRaises(ValueError, oargs.resolve, args)

    def test21(self):
        """test mix between @ and / separators"""
        oargs = OscArgs('foo@bar/baz@foobar')
        args = 'x@y/z@w'
        info = oargs.resolve(args)
        self.assertEqual(info.foo, 'x')
        self.assertEqual(info.bar, 'y')
        self.assertEqual(info.baz, 'z')
        self.assertEqual(info.foobar, 'w')

    def test22(self):
        """test wc path entry (prj/pkg/file)"""
        oargs = OscArgs('wc_path')
        args = self.fixture_file('prj1', 'added', 'foo')
        info = oargs.resolve(args)
        project_path = self.fixture_file('prj1')
        package_path = self.fixture_file('prj1', 'added')
        self.assertEqual(info.path.project, 'prj1')
        self.assertEqual(info.path.project_path, project_path)
        self.assertEqual(info.path.package, 'added')
        self.assertEqual(info.path.package_path, package_path)
        self.assertEqual(info.path.filename, 'foo')
        self.assertEqual(info.path.filename_path, args)
        # get objects
        prj = info.path.project_obj()
        self.assertIsNotNone(prj)
        self.assertEqual(prj.apiurl, 'http://apiurl')
        pkg = info.path.package_obj()
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.name, 'added')

    def test23(self):
        """test wc path entry (prj/pkg/non_existent)"""
        oargs = OscArgs('wc_path')
        args = self.fixture_file('prj1', 'added', 'non_existent')
        info = oargs.resolve(args)
        project_path = self.fixture_file('prj1')
        package_path = self.fixture_file('prj1', 'added')
        self.assertEqual(info.path.project, 'prj1')
        self.assertEqual(info.path.project_path, project_path)
        self.assertEqual(info.path.package, 'added')
        self.assertEqual(info.path.package_path, package_path)
        self.assertEqual(info.path.filename, 'non_existent')
        self.assertEqual(info.path.filename_path, args)
        # get objects
        # pass some useless/erroneous arguments
        prj = info.path.project_obj(transaction_listener=[None])
        self.assertIsNotNone(prj)
        self.assertEqual(prj.apiurl, 'http://apiurl')
        # pass some useless/erroneous arguments
        self.assertEqual(prj.notifier.listener, [None])
        pkg = info.path.package_obj(skip_handlers=['skip'])
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.name, 'added')
        self.assertEqual(pkg.skip_handlers, ['skip'])

    def test23_1(self):
        """test wc path entry (prj/nonexistent)"""
        oargs = OscArgs('wc_path')
        path = self.fixture_file('prj1')
        self._not_exists(path, 'nonexistent')
        args = self.fixture_file('prj1', 'nonexistent')
        info = oargs.resolve(args)
        self.assertEqual(info.path.project, 'prj1')
        self.assertEqual(info.path.project_path, path)
        self.assertEqual(info.path.package, 'nonexistent')
        self.assertEqual(info.path.package_path, args)
        self.assertIsNone(info.path.filename)
        self.assertIsNone(info.path.filename_path)
        # get objects
        self.assertIsNotNone(info.path.project_obj())
        # package is None, because it does not exists/is no wc
        self.assertIsNone(info.path.package_obj())

    def test23_2(self):
        """test wc path entry to nonexistent pkg with trailing slash"""
        oargs = OscArgs('wc_path')
        path = self.fixture_file('prj1')
        self._not_exists(path, 'nonexistent')
        args = self.fixture_file('prj1', 'nonexistent') + '/'
        info = oargs.resolve(args)
        self.assertEqual(info.path.project, 'prj1')
        self.assertEqual(info.path.project_path, path)
        self.assertEqual(info.path.package, 'nonexistent')
        exp = self.fixture_file('prj1', 'nonexistent')
        self.assertEqual(info.path.package_path, exp)
        self.assertIsNone(info.path.filename)
        self.assertIsNone(info.path.filename_path)

    def test24(self):
        """test wc path entry (prj/pkg)"""
        oargs = OscArgs('wc_path')
        args = self.fixture_file('prj1', 'added')
        info = oargs.resolve(args)
        project_path = self.fixture_file('prj1')
        self.assertEqual(info.path.project, 'prj1')
        self.assertEqual(info.path.project_path, project_path)
        self.assertEqual(info.path.package, 'added')
        self.assertEqual(info.path.package_path, args)
        self.assertIsNone(info.path.filename)
        self.assertIsNone(info.path.filename_path)
        # get objects
        prj = info.path.project_obj()
        self.assertIsNotNone(prj)
        self.assertEqual(prj.apiurl, 'http://apiurl')
        pkg = info.path.package_obj()
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.name, 'added')

    def test25(self):
        """test wc path entry (cwd: package - no filename)"""
        oargs = OscArgs('wc_path')
        path = self.fixture_file('prj1', 'added')
        cwd = os.getcwd()
        args = ''
        try:
            os.chdir(path)
            info = oargs.resolve(args)
            project_path = self.fixture_file('prj1')
            self.assertEqual(info.path.project, 'prj1')
            self.assertEqual(info.path.project_path, project_path)
            self.assertEqual(info.path.package, 'added')
            self.assertEqual(info.path.package_path, path)
            self.assertIsNone(info.path.filename)
            self.assertIsNone(info.path.filename_path)
            # get objects
            prj = info.path.project_obj()
            self.assertIsNotNone(prj)
            self.assertEqual(prj.apiurl, 'http://apiurl')
            pkg = info.path.package_obj()
            self.assertIsNotNone(pkg)
            self.assertEqual(pkg.name, 'added')
        finally:
            os.chdir(cwd)

    def test26(self):
        """test wc path entry (cwd: package - filename)"""
        oargs = OscArgs('wc_path')
        path = self.fixture_file('prj1', 'added')
        cwd = os.getcwd()
        args = 'foo'
        try:
            os.chdir(path)
            info = oargs.resolve(args)
            project_path = self.fixture_file('prj1')
            self.assertEqual(info.path.project, 'prj1')
            self.assertEqual(info.path.project_path, project_path)
            self.assertEqual(info.path.package, 'added')
            self.assertEqual(info.path.package_path, path)
            self.assertEqual(info.path.filename, 'foo')
            self.assertEqual(info.path.filename_path, args)
            # get objects
            prj = info.path.project_obj()
            self.assertIsNotNone(prj)
            self.assertEqual(prj.apiurl, 'http://apiurl')
            pkg = info.path.package_obj()
            self.assertIsNotNone(pkg)
            self.assertEqual(pkg.name, 'added')
        finally:
            os.chdir(cwd)

    def test27(self):
        """test wc path entry (prj) (different name)"""
        oargs = OscArgs('wc_foo')
        args = self.fixture_file('prj1')
        info = oargs.resolve(args)
        self.assertEqual(info.foo.project, 'prj1')
        self.assertEqual(info.foo.project_path, args)
        self.assertIsNone(info.foo.package)
        self.assertIsNone(info.foo.package_path)
        self.assertIsNone(info.foo.filename)
        self.assertIsNone(info.foo.filename_path)
        # get objects
        prj = info.foo.project_obj()
        self.assertIsNotNone(prj)
        self.assertEqual(prj.apiurl, 'http://apiurl')
        self.assertIsNone(info.foo.package_obj())

    def test28(self):
        """test wc path entry (package - no parent)"""
        oargs = OscArgs('wc_path')
        args = self.fixture_file('package', 'non_existent')
        info = oargs.resolve(args)
        package_path = self.fixture_file('package')
        self.assertIsNone(info.path.project)
        self.assertIsNone(info.path.project_path)
        self.assertEqual(info.path.package, 'package')
        self.assertEqual(info.path.package_path, package_path)
        self.assertEqual(info.path.filename, 'non_existent')
        self.assertEqual(info.path.filename_path, args)
        # get objects
        self.assertIsNone(info.path.project_obj())
        pkg = info.path.package_obj()
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.name, 'package')

    def test29(self):
        """test wc path (raise ValueError)"""
        oargs = OscArgs('wc_path')
        self.assertRaises(ValueError, oargs.resolve, os.curdir)
        self.assertRaises(ValueError, oargs.resolve, '/')
        # illegal name
        self.assertRaises(ValueError, OscArgs, 'wc_')

    def test30(self):
        """test plain entry"""
        oargs = OscArgs('plain_arg')
        args = 'some_argument'
        info = oargs.resolve(args)
        self.assertEqual(info.arg, 'some_argument')

    def test31(self):
        """test plain entry (api syntax has to be ignored)"""
        oargs = OscArgs('plain_argument')
        args = 'api://project/package'
        info = oargs.resolve(args)
        self.assertEqual(info.argument, 'api://project/package')

    def test32(self):
        """test plain entry (separators have to be ignored)"""
        oargs = OscArgs('plain_xyz')
        args = 'repo/arch'
        info = oargs.resolve(args)
        self.assertEqual(info.xyz, 'repo/arch')

    def test33(self):
        """test combination with a component entry"""
        oargs = OscArgs('api://project', 'plain_foo')
        args = ('api://foo', 'api://bar/x')
        info = oargs.resolve(*args)
        self.assertEqual(info.apiurl, 'api')
        self.assertEqual(info.project, 'foo')
        self.assertEqual(info.foo, 'api://bar/x')

    def test34(self):
        """test illegal name for a plain entry"""
        self.assertRaises(ValueError, OscArgs, 'plain_')

    def test35(self):
        """specify the same oargs multiple times (solve name clashes)"""
        oargs = OscArgs('foo', 'foo', 'bar', 'foo', ignore_clashes=False)
        args = ('foo1', 'foo2', 'bar1', 'foo3')
        info = oargs.resolve(*args)
        # foo is expected multiple times => use list
        self.assertEqual(info.foo, ['foo1', 'foo2', 'foo3'])
        # bar is expected only once => no list
        self.assertEqual(info.bar, 'bar1')

    def test36(self):
        """specify the same oargs multiple times (mix entry types)"""
        oargs = OscArgs('plain_foo', 'foo', 'api://project', 'api://project',
                        ignore_clashes=False)
        args = ('foo/bar', 'xyz', 'api://abc', 'obs://prj')
        info = oargs.resolve(*args)
        self.assertEqual(info.foo, ['foo/bar', 'xyz'])
        self.assertEqual(info.apiurl, ['api', 'obs'])
        self.assertEqual(info.project, ['abc', 'prj'])

    def test37(self):
        """specify the same oargs multiple times (optional args)"""
        oargs = OscArgs('repo/arch?', 'repo/arch', ignore_clashes=False)
        args = ('repo_only', 'some_repo/x86_64')
        info = oargs.resolve(*args)
        # hopefully nobody is using it this way (examining the results
        # is difficult/ambiguous - see test38 how it should be used)
        self.assertEqual(info.repo, ['repo_only', 'some_repo'])
        # arch was only specified once (by the user!) => no list
        self.assertEqual(info.arch, 'x86_64')

    def test38(self):
        """specify the same oargs multiple times (optional args - Sub class)"""
        # similar to test37
        oargs = Sub('repo/arch?', 'repo/arch', ignore_clashes=False)
        args = ('repo_only', 'some_repo/x86_64')
        info = oargs.resolve(*args)
        self.assertEqual(info.repo, ['repo_only', 'some_repo'])
        # arch is a list
        self.assertEqual(info.arch, [None, 'x86_64'])

    def test_alternative1(self):
        """test a simple alternative"""
        oargs = OscArgs('api://project|repo', ignore_clashes=False)
        args = 'api://abc'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'api')
        self.assertEqual(info.project, 'abc')
        self.assertFalse(hasattr(info, 'repo'))

    def test_alternative2(self):
        """test a simple alternative (alternative matches)"""
        oargs = OscArgs('api://project|repo')
        args = 'openSUSE_Factory'
        info = oargs.resolve(args)
        self.assertEqual(info.repo, 'openSUSE_Factory')
        self.assertFalse(hasattr(info, 'apiurl'))
        self.assertFalse(hasattr(info, 'project'))

    def test_alternative3(self):
        """test multiple alternatives"""
        # actually, no clash occurs, but having clash support
        # enabled might catch some (unexpected) glitches
        oargs = OscArgs('api://project/package|repo/arch|repo',
                        ignore_clashes=False)
        # match first alternative
        args = 'obs://foo/bar'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'foo')
        self.assertEqual(info.package, 'bar')
        self.assertFalse(hasattr(info, 'repo'))
        self.assertFalse(hasattr(info, 'arch'))
        # match second alternative
        args = 'openSUSE_Factory/x86_64'
        info = oargs.resolve(args)
        self.assertEqual(info.repo, 'openSUSE_Factory')
        self.assertEqual(info.arch, 'x86_64')
        self.assertFalse(hasattr(info, 'apiurl'))
        self.assertFalse(hasattr(info, 'project'))
        self.assertFalse(hasattr(info, 'package'))
        # match third alternative
        args = 'openSUSE_Factory'
        info = oargs.resolve(args)
        self.assertEqual(info.repo, 'openSUSE_Factory')
        self.assertFalse(hasattr(info, 'apiurl'))
        self.assertFalse(hasattr(info, 'project'))
        self.assertFalse(hasattr(info, 'package'))
        self.assertFalse(hasattr(info, 'arch'))

    def test_alternative4(self):
        """test ambiguous alternatives (first match (left to right) wins)"""
        oargs = OscArgs('repo/arch?|repository')
        # specify repo/arch
        args = 'openSUSE_Factory/x86_64'
        info = oargs.resolve(args)
        self.assertEqual(info.repo, 'openSUSE_Factory')
        self.assertEqual(info.arch, 'x86_64')
        self.assertFalse(hasattr(info, 'repository'))
        # specify repo only (first match (from left to right wins))
        args = 'openSUSE_Factory'
        info = oargs.resolve(args)
        self.assertEqual(info.repo, 'openSUSE_Factory')
        self.assertFalse(hasattr(info, 'arch'))
        self.assertFalse(hasattr(info, 'repository'))

    def test_alternative5(self):
        """test ambiguous alternatives (see previous testcase)"""
        oargs = OscArgs('repository|repo/arch?')
        # specify repo only
        args = 'openSUSE_Factory'
        info = oargs.resolve(args)
        self.assertEqual(info.repository, 'openSUSE_Factory')
        self.assertFalse(hasattr(info, 'repo'))
        self.assertFalse(hasattr(info, 'arch'))
        # specify repo/arch
        args = 'openSUSE_Factory/x86_64'
        info = oargs.resolve(args)
        self.assertEqual(info.repo, 'openSUSE_Factory')
        self.assertEqual(info.arch, 'x86_64')
        self.assertFalse(hasattr(info, 'repository'))

    def test_alternative6(self):
        """apiurl and wc_path alternatives"""
        oargs = OscArgs('api://project/package|wc_path')
        # specify apiurl
        args = 'obs://foo/bar'
        info = oargs.resolve(args)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'foo')
        self.assertEqual(info.package, 'bar')
        self.assertFalse(hasattr(info, 'path'))
        # specify wc path
        args = self.fixture_file('prj1', 'added')
        info = oargs.resolve(args)
        project_path = self.fixture_file('prj1')
        self.assertEqual(info.path.project, 'prj1')
        self.assertEqual(info.path.project_path, project_path)
        self.assertEqual(info.path.package, 'added')
        self.assertEqual(info.path.package_path, args)
        self.assertIsNone(info.path.filename)
        self.assertIsNone(info.path.filename_path)
        self.assertFalse(hasattr(info, 'apiurl'))
        self.assertFalse(hasattr(info, 'project'))
        self.assertFalse(hasattr(info, 'package'))
        # specify no args and cwd is a project
        path = self.fixture_file('prj1')
        cwd = os.getcwd()
        args = ''
        try:
            os.chdir(path)
            info = oargs.resolve(args)
            project_path = self.fixture_file('prj1')
            self.assertEqual(info.path.project, 'prj1')
            self.assertEqual(info.path.project_path, project_path)
            self.assertIsNone(info.path.package)
            self.assertIsNone(info.path.package_path)
            self.assertIsNone(info.path.filename)
            self.assertIsNone(info.path.filename_path)
            self.assertFalse(hasattr(info, 'apiurl'))
            self.assertFalse(hasattr(info, 'project'))
            self.assertFalse(hasattr(info, 'package'))
        finally:
            os.chdir(cwd)

    def test_alternative7(self):
        """test api and wc_path alternatives (resolve with path)"""
        oargs = OscArgs('api://project/package|wc_path')
        # specify empty args
        path = self.fixture_file('prj1', 'added')
        args = ''
        info = oargs.resolve(args, path=path)
        self.assertEqual(info.project, 'prj1')
        self.assertEqual(info.package, 'added')
        self.assertFalse(hasattr(info, 'path'))
        # specify filename
        args = self.fixture_file('prj1', 'added', 'foo')
        info = oargs.resolve(args, path=path)
        self.assertEqual(info.path.project, 'prj1')
        self.assertEqual(info.path.package, 'added')
        self.assertEqual(info.path.package_path, path)
        self.assertEqual(info.path.filename, 'foo')
        self.assertEqual(info.path.filename_path, args)
        self.assertFalse(hasattr(info, 'apiurl'))
        self.assertFalse(hasattr(info, 'project'))
        self.assertFalse(hasattr(info, 'package'))
        # read project from (wc_path) from cwd
        cwd = os.getcwd()
        path = self.fixture_file('prj1')
        try:
            os.chdir(path)
            args = ''
            info = oargs.resolve(args, path=path)
            self.assertEqual(info.path.project, 'prj1')
            self.assertEqual(info.path.project_path, path)
            self.assertFalse(hasattr(info, 'apiurl'))
            self.assertFalse(hasattr(info, 'project'))
            self.assertFalse(hasattr(info, 'package'))
        finally:
            os.chdir(cwd)
        # specify package via wc_path
        args = path = self.fixture_file('prj1', 'added')
        info = oargs.resolve(args, path=path)
        self.assertEqual(info.path.project, 'prj1')
        self.assertEqual(info.path.package, 'added')
        self.assertEqual(info.path.package_path, path)
        self.assertIsNone(info.path.filename)
        self.assertFalse(hasattr(info, 'apiurl'))
        self.assertFalse(hasattr(info, 'project'))
        self.assertFalse(hasattr(info, 'package'))

    def test_alternative8(self):
        """test wc_path and api alternatives (see also previous testcase)"""
        oargs = OscArgs('wc_path|api://project/package?')
        # read package from cwd
        path = self.fixture_file('prj1', 'added')
        cwd = os.getcwd()
        try:
            os.chdir(path)
            args = ''
            info = oargs.resolve(args, path=path)
            self.assertEqual(info.path.project, 'prj1')
            self.assertEqual(info.path.package, 'added')
            self.assertEqual(info.path.package_path, path)
            self.assertFalse(hasattr(info, 'apiurl'))
            self.assertFalse(hasattr(info, 'project'))
            self.assertFalse(hasattr(info, 'package'))
        finally:
            os.chdir(cwd)
        # read project from from path (wc_path)
        args = path = self.fixture_file('prj1')
        info = oargs.resolve(args, path=path)
        self.assertEqual(info.path.project, 'prj1')
        self.assertEqual(info.path.project_path, path)
        self.assertFalse(hasattr(info, 'apiurl'))
        self.assertFalse(hasattr(info, 'project'))
        self.assertFalse(hasattr(info, 'package'))
        # read project from path (via apiurl)
        path = self.fixture_file('prj1')
        args = ''
        info = oargs.resolve(args, path=path)
        self.assertEqual(info.apiurl, 'http://apiurl')
        self.assertEqual(info.project, 'prj1')
        self.assertFalse(hasattr(info, 'package'))
        self.assertFalse(hasattr(info, 'path'))
        # specify via apiurl
        args = 'obs://foo/bar'
        path = self.fixture_file('prj1', 'added')
        info = oargs.resolve(args, path=path)
        self.assertEqual(info.apiurl, 'obs')
        self.assertEqual(info.project, 'foo')
        self.assertEqual(info.package, 'bar')
        self.assertFalse(hasattr(info, 'path'))

    def test_alternative_illegal(self):
        """test illegal alternative entries"""
        self.assertRaises(ValueError, OscArgs, '|')
        self.assertRaises(ValueError, OscArgs, '||')
        self.assertRaises(ValueError, OscArgs, 'a|')

if __name__ == '__main__':
    unittest.main()
