import os
import unittest
from tempfile import NamedTemporaryFile

from lxml import etree

from osc.builder import (Builder, su_cmd, sudo_cmd, hostarch, can_build,
                         build_helper)
from test.osctest import OscTest


def suite():
    return unittest.makeSuite(TestBuilder)


class TestBuilder(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = 'test_builder_fixtures'
        super(TestBuilder, self).__init__(*args, **kwargs)

    def test_builder1(self):
        """test options 1"""
        builder = Builder()
        builder.jobs = 2
        builder.debug = True
        builder.no_init = True
        builder.root = '/var/tmp/build-root'
        exp_opts = ['--debug', '--jobs', '2', '--no-init',
                    '--root', '/var/tmp/build-root']
        self.assertEqual(builder.opts(), exp_opts)

    def test_builder2(self):
        """test options 1 (via set)"""
        builder = Builder()
        builder.set('jobs', 2)
        builder.set('debug', True)
        builder.set('no_init', True)
        builder.set('root', '/var/tmp/build-root')
        exp_opts = ['--debug', '--jobs', '2', '--no-init',
                    '--root', '/var/tmp/build-root']
        self.assertEqual(builder.opts(), exp_opts)

    def test_builder3(self):
        """test multiple options"""
        builder = Builder()
        builder.without = 'feat1'
        builder.without += 'abc'
        builder.rsync_src = '/path/to/src'
        builder.without += 'feat2'
        exp_opts = ['--rsync-src', '/path/to/src', '--without', 'feat1',
                    '--without', 'abc', '--without', 'feat2']
        self.assertEqual(builder.opts(), exp_opts)

    def test_builder4(self):
        """test multiple options (via set)"""
        builder = Builder()
        builder.set('without', 'feat1')
        builder.set('without', 'abc', append=True)
        builder.set('rsync_src', '/path/to/src')
        builder.set('without', 'feat2', append=True)
        exp_opts = ['--rsync-src', '/path/to/src', '--without', 'feat1',
                    '--without', 'abc', '--without', 'feat2']
        self.assertEqual(builder.opts(), exp_opts)

    def test_builder5(self):
        """test multiple options (no append)"""
        builder = Builder()
        builder.foo = 'bar'
        builder.foo += 'xyz'
        builder.foo = 'foobar'
        builder.bar = 42
        exp_opts = ['--bar', '42', '--foo', 'foobar']
        self.assertEqual(builder.opts(), exp_opts)

    def test_builder6(self):
        """test multiple options (no append via set)"""
        builder = Builder()
        builder.set('foo', 'bar')
        builder.set('foo', 'xyz', append=True)
        builder.set('foo', 'foobar')
        builder.set('bar', 42)
        exp_opts = ['--bar', '42', '--foo', 'foobar']
        self.assertEqual(builder.opts(), exp_opts)

    def test_builder7(self):
        """test multiple options (lists)"""
        builder = Builder()
        builder.foo = 'bar'
        builder.foo += ['x', 'y', 'z']
        builder.z = True
        builder.foo += 'a'
        exp_opts = ['--foo', 'bar', '--foo', 'x', '--foo', 'y',
                    '--foo', 'z', '--foo', 'a', '--z']
        self.assertEqual(builder.opts(), exp_opts)

    def test_builder8(self):
        """test multiple options (lists via set)"""
        builder = Builder()
        builder.set('foo', 'bar')
        builder.set('foo', ['x', 'y', 'z'], append=True)
        builder.set('z', True)
        builder.set('foo', 'a', append=True)
        exp_opts = ['--foo', 'bar', '--foo', 'x', '--foo', 'y',
                    '--foo', 'z', '--foo', 'a', '--z']
        self.assertEqual(builder.opts(), exp_opts)

    def test_builder9(self):
        """test unset option (set to None)"""
        builder = Builder()
        builder.abc = 'def'
        builder.test = 'test123'
        builder.jobs = 42
        builder.abc = None
        builder.jobs = None
        self.assertEqual(builder.opts(), ['--test', 'test123'])

    def test_builder10(self):
        """test unset option (set to None via set)"""
        builder = Builder()
        builder.abc = 'def'
        builder.test = 'test123'
        builder.jobs = 42
        builder.set('abc', None)
        builder.set('jobs', None)
        self.assertEqual(builder.opts(), ['--test', 'test123'])

    def test_builder11(self):
        """test unset option (set to None via del)"""
        builder = Builder()
        builder.abc = 'def'
        builder.test = 'test123'
        builder.jobs = 42
        del builder.abc
        del builder.jobs
        self.assertEqual(builder.opts(), ['--test', 'test123'])

    def test_builder12(self):
        """test constructor parameters"""
        builder = Builder(rpmlist='/path/to/rpmlist', jobs=2,
                          root='/var/tmp/build-root', arch='x86_64',
                          config='/path/to/buildconfig')
        # overwrite jobs
        builder.jobs = 3
        exp_opts = ['--arch', 'x86_64', '--config', '/path/to/buildconfig',
                    '--jobs', '3', '--root', '/var/tmp/build-root',
                    '--rpmlist', '/path/to/rpmlist']
        self.assertEqual(builder.opts(), exp_opts)

    def test_builder13(self):
        """test cmd construction (with su (default))"""
        builder = Builder(arch='x86_64', root='/var/tmp/build-root', jobs=2)
        exp_cmd = ['su', '--shell', '/usr/bin/build', 'root', '--',
                   '--arch', 'x86_64', '--jobs', '2',
                   '--root', '/var/tmp/build-root']
        self.assertEqual(builder.cmd(), exp_cmd)

    def test_builder14(self):
        """test cmd construction (with sudo)"""
        builder = Builder(su_cmd=Builder.SUDO, arch='x86_64',
                          root='/var/tmp/build-root', jobs=2)
        exp_cmd = ['sudo', '/usr/bin/build', '--arch', 'x86_64',
                   '--jobs', '2', '--root', '/var/tmp/build-root']
        self.assertEqual(builder.cmd(), exp_cmd)

    def test_builder15(self):
        """test cmd construction different build_cmd (no su_cmd)"""
        builder = Builder(build_cmd='/bin/echo', su_cmd=None, foo='bar')
        exp_cmd = ['/bin/echo', '--foo', 'bar']
        self.assertEqual(builder.cmd(), exp_cmd)

    def test_builder16(self):
        """test run method (retcode 0)"""
        build_cmd = self.fixture_file('./dummy.sh')
        builder = Builder(build_cmd=build_cmd, su_cmd=None)
        ret = builder.run()
        self.assertEqual(ret, 0)

    def test_builder17(self):
        """test run method (retcode 1)"""
        build_cmd = self.fixture_file('dummy.sh')
        builder = Builder(build_cmd=build_cmd, su_cmd=None, fail=True)
        ret = builder.run()
        self.assertEqual(ret, 1)

    def test_builder18(self):
        """test run method (write stdout to tmpfile)"""
        build_cmd = self.fixture_file('dummy.sh')
        builder = Builder(build_cmd=build_cmd, su_cmd=None, out='blah')
        with NamedTemporaryFile() as f:
            ret = builder.run(stdout=f)
            self.assertEqual(ret, 0)
            f.seek(0, os.SEEK_SET)
            self.assertEqual(f.read(), 'blah\n')

    def test_builder19(self):
        """test run method (no shell expansion)"""
        build_cmd = self.fixture_file('dummy.sh')
        builder = Builder(build_cmd=build_cmd, su_cmd=None, out='$PATH')
        with NamedTemporaryFile() as f:
            ret = builder.run(stdout=f)
            self.assertEqual(ret, 0)
            f.seek(0, os.SEEK_SET)
            # path is not expanded because subprocess.call is invoked
            # with shell=False
            self.assertEqual(f.read(), '$PATH\n')

    def test_builder20(self):
        """test run method (specify spec file)"""
        build_cmd = self.fixture_file('dummy.sh')
        builder = Builder(build_cmd=build_cmd, su_cmd=None)
        with NamedTemporaryFile() as f:
            ret = builder.run('foo.spec', stdout=f)
            self.assertEqual(ret, 0)
            f.seek(0, os.SEEK_SET)
            # output is the build descr
            self.assertEqual(f.read(), 'foo.spec\n')

    def test_builder21(self):
        """test cmd method (specifcy build descr)"""
        builder = Builder(su_cmd=Builder.SUDO, foo='bar')
        exp_cmd = ['sudo', '/usr/bin/build', '--foo', 'bar', 'test.spec']
        self.assertEqual(builder.cmd('test.spec'), exp_cmd)

    def test_builder22(self):
        """test cmd method (buildarch != hostarch, without helper)"""
        harch = hostarch()
        builder = Builder(su_cmd=Builder.SUDO, buildarch='i123',
                          cando={harch: {'i123': ''}})
        exp_cmd = ['sudo', '/usr/bin/build', 'test.spec']
        self.assertEqual(builder.cmd('test.spec'), exp_cmd)

    def test_builder23(self):
        """test cmd method (buildarch != hostarch, with helper)"""
        harch = hostarch()
        builder = Builder(su_cmd=Builder.SUDO, buildarch='i123',
                          cando={harch: {'i123': 'linux123'}})
        exp_cmd = ['linux123', 'sudo', '/usr/bin/build', 'test.spec']
        self.assertEqual(builder.cmd('test.spec'), exp_cmd)

    def test_builder24(self):
        """test cmd method (buildarch != hostarch and no cando)"""
        self.assertRaises(ValueError, Builder, buildarch='i123')

    def test_su_cmd1(self):
        """test the construction of the "su" cmd"""
        cmd = su_cmd('/usr/bin/build', ['--arch', 'x86_64', '--jobs', '3'])
        exp_cmd = ['su', '--shell', '/usr/bin/build', 'root', '--',
                   '--arch', 'x86_64', '--jobs', '3']
        self.assertEqual(cmd, exp_cmd)

    def test_sudo_cmd1(self):
        """test the construction of the "sudo" cmd"""
        cmd = sudo_cmd('/usr/bin/build', ['--arch', 'x86_64', '--jobs', '3'])
        exp_cmd = ['sudo', '/usr/bin/build', '--arch', 'x86_64',
                   '--jobs', '3']
        self.assertEqual(cmd, exp_cmd)

    def test_can_build1(self):
        """test can_build (simple)"""
        cando = {'i586': {'i386': '', 'i586': ''}, 'x86_64': {'x86_64': ''}}
        self.assertTrue(can_build('i586', 'i586', cando))
        self.assertTrue(can_build('i586', 'i386', cando))
        self.assertTrue(can_build('x86_64', 'x86_64', cando))
        # invalid buildarches
        self.assertFalse(can_build('i586', 'x86_64', cando))
        self.assertFalse(can_build('x86_64', 'i586', cando))

    def test_can_build2(self):
        """test can_build (unsupported hostarch - raises ValueError)"""
        cando = {'i586': {'i386': '', 'i586': ''}, 'x86_64': {'x86_64': ''}}
        cando = {'i586': ['i386', 'i586'], 'x86_64': ['x86_64']}
        self.assertRaises(ValueError, can_build, 'ppc', 'ppc', cando)

    def test_can_build3(self):
        """test can_build (with helpers)"""
        # note can_build ignores the helpers (if present)
        cando = {'i586': {'i386': '', 'i586': ''},
                 'x86_64': {'x86_64': '', 'i586': 'linux32'}}
        self.assertTrue(can_build('i586', 'i586', cando))
        self.assertTrue(can_build('i586', 'i386', cando))
        self.assertTrue(can_build('x86_64', 'x86_64', cando))
        self.assertTrue(can_build('x86_64', 'i586', cando))

    def test_build_helper1(self):
        """test build_helper"""
        cando = {'i586': {'i386': '', 'i586': ''}, 'x86_64': {'x86_64': ''}}
        self.assertEqual(build_helper('i586', 'i586', cando), '')
        self.assertEqual(build_helper('i586', 'i386', cando), '')
        self.assertEqual(build_helper('x86_64', 'x86_64', cando), '')

    def test_build_helper2(self):
        """test build_helper (unsupported hostarch - raises ValueError)"""
        cando = {'i586': {'i386': '', 'i586': ''}, 'x86_64': {'x86_64': ''}}
        self.assertRaises(ValueError, build_helper, 'ppc', 'ppc', cando)

    def test_build_helper3(self):
        """test build_helper (helper present)"""
        cando = {'i586': {'i386': '', 'i586': ''},
                 'x86_64': {'x86_64': '', 'i586': 'linux32'}}
        self.assertEqual(build_helper('i586', 'i586', cando), '')
        self.assertEqual(build_helper('i586', 'i386', cando), '')
        self.assertEqual(build_helper('x86_64', 'x86_64', cando), '')
        self.assertEqual(build_helper('x86_64', 'i586', cando), 'linux32')

    def test_build_helper4(self):
        """test build_helper (unsupported buildarch - raises ValueError)"""
        cando = {'i586': {'i386': '', 'i586': ''}, 'x86_64': {'x86_64': ''}}
        self.assertRaises(ValueError, build_helper, 'x86_64', 'i586', cando)

if __name__ == '__main__':
    unittest.main()
