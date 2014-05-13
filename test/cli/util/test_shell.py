import os
import unittest
from collections import namedtuple

from osc2.cli.util.shell import AbstractShell, ShellSyntaxError
from test.osctest import OscTest


def suite():
    return unittest.makeSuite(TestAbstractShell)


class MockRenderer(object):
    """Mocks a Renderer object."""

    RenderedData = namedtuple('RenderedData', ['type', 'tmpl', 'text',
                                               'args', 'kwargs'])

    def __init__(self):
        self.rendered = []

    def render(self, tmpl, *args, **kwargs):
        data = MockRenderer.RenderedData('tmpl', tmpl, None, args, kwargs)
        self.rendered.append(data)

    def render_text(self, text, *args, **kwargs):
        data = MockRenderer.RenderedData('text', None, text, args, kwargs)
        self.rendered.append(data)


class TestAbstractShell(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = os.path.join('cli', 'util',
                                              'test_shell_fixtures')
        super(TestAbstractShell, self).__init__(*args, **kwargs)

    def test_check_input1(self):
        """test simple input"""
        shell = AbstractShell(MockRenderer())
        self.assertTrue(shell._check_input('foo bar'))

    def test_check_input2(self):
        """test simple input with quotes"""
        shell = AbstractShell(MockRenderer())
        self.assertTrue(shell._check_input('foo "bar x"'))

    def test_check_input3(self):
        """test input with mulitple quotes"""
        shell = AbstractShell(MockRenderer())
        self.assertTrue(shell._check_input('foo "bar x" "x y z"'))

    def test_check_input4(self):
        """test quote empty str"""
        shell = AbstractShell(MockRenderer())
        self.assertTrue(shell._check_input('x "" "b"'))

    def test_check_input5(self):
        """test simple quoted input"""
        shell = AbstractShell(MockRenderer())
        self.assertTrue(shell._check_input('"foo"'))

    def test_check_input6(self):
        """test input with missing quote"""
        shell = AbstractShell(MockRenderer())
        self.assertFalse(shell._check_input('foo "bar x bla'))

    def test_check_input7(self):
        """test input with missing quote (multiple quotes)"""
        shell = AbstractShell(MockRenderer())
        # "bar x " is recognized correctly
        self.assertFalse(shell._check_input('foo "bar x " "bla foobar'))

    def test_check_input8(self):
        """test incorrect input (missing whitespace after quote)"""
        shell = AbstractShell(MockRenderer())
        self.assertRaises(ShellSyntaxError, shell._check_input, 'foo "bar"x')

    def test_check_input9(self):
        """test incorrect input (missing whitespace before quote)"""
        shell = AbstractShell(MockRenderer())
        self.assertRaises(ShellSyntaxError, shell._check_input, 'foo x"bar"')

    def test_check_input10(self):
        """test incorrect input (embedded quote)"""
        shell = AbstractShell(MockRenderer())
        self.assertRaises(ShellSyntaxError, shell._check_input,
                          'foo "bar "x"')

    def test_check_input11(self):
        """test incorrect input (embedded quote)"""
        shell = AbstractShell(MockRenderer())
        self.assertRaises(ShellSyntaxError, shell._check_input,
                          'foo "bar " x" xy"')

    def test_split_input1(self):
        """test simple input"""
        shell = AbstractShell(MockRenderer())
        data = shell._split_input('foo')
        self.assertEqual(data, ['foo'])

    def test_split_input2(self):
        """test simple input (multiple elements)"""
        shell = AbstractShell(MockRenderer())
        data = shell._split_input('foo bar')
        self.assertEqual(data, ['foo', 'bar'])

    def test_split_input3(self):
        """test simple input (with quotes)"""
        shell = AbstractShell(MockRenderer())
        data = shell._split_input('foo "bar x" y')
        self.assertEqual(data, ['foo', 'bar x', 'y'])

    def test_split_input4(self):
        """test input (multiple quotes)"""
        shell = AbstractShell(MockRenderer())
        data = shell._split_input('foo "bar\nx" "y z"')
        self.assertEqual(data, ['foo', 'bar\nx', 'y z'])

    def test_split_input5(self):
        """test input (multiple whitespace)"""
        shell = AbstractShell(MockRenderer())
        data = shell._split_input('"foo  bar"')
        self.assertEqual(data, ['foo  bar'])

if __name__ == '__main__':
    unittest.main()
