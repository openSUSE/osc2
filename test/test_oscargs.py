import os
import unittest

from osc.oscargs import OscArgs
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
        path = self.fixture_file('project')
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
        """test name clashes/wrong usage"""
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

if __name__ == '__main__':
    unittest.main()
