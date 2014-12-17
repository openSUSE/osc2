from __future__ import print_function
import unittest

from osc2.util.delegation import StringifiedDelegator


def suite():
    return unittest.makeSuite(TestDelegation)


class Foo(object):
    def __init__(self):
        self.bar = 42
        self.name = 'foo'
        self.i = 0
        self._del = False
        self._enter = False
        self._exit = False

    def acc(self):
        self.i += 1

    def endswith(self, end):
        return False

    def __enter__(self):
        self._enter = True

    def __exit__(self, *args, **kwargs):
        self._exit = True

    def __del__(self):
        self._del = True

    def __str__(self):
        return self.name


# we only test the StringifiedDelegator, because this
# indirectly tests the Delegator class as well
class TestDelegation(unittest.TestCase):

    def test_sdelegator1(self):
        """test simple delegation"""
        sdel = StringifiedDelegator(Foo())
        self.assertEqual(sdel, 'foo')
        self.assertTrue(id(sdel) != id('foo'))
        # test attribute delegations
        self.assertEqual(sdel.bar, 42)
        self.assertEqual(sdel.name, 'foo')
        self.assertFalse(sdel._enter)
        self.assertFalse(sdel._exit)
        # endswith method is not delegated
        self.assertTrue(sdel.endswith('o'))
        # test some str operations and methods
        self.assertEqual(sdel * 3, 'foofoofoo')
        self.assertEqual(sdel + 'bar', 'foobar')
        self.assertEqual(len(sdel), 3)
        self.assertEqual(sdel[1], 'o')
        self.assertTrue(sdel.startswith('fo'))

    def test_sdelegator2(self):
        """add and set attributes"""
        foo = Foo()
        sdel = StringifiedDelegator(foo)
        # modify existing attribute
        self.assertEqual(sdel.bar, 42)
        self.assertEqual(foo.bar, 42)
        sdel.bar = 'bar'
        self.assertEqual(sdel.bar, 'bar')
        self.assertEqual(foo.bar, 'bar')
        # modified bar via the "foo"
        foo.bar = -1
        self.assertEqual(sdel.bar, -1)
        # add attribute
        self.assertFalse(hasattr(foo, 'x'))
        sdel.x = 0
        self.assertTrue(hasattr(sdel, 'x'))
        self.assertTrue(hasattr(foo, 'x'))
        self.assertEqual(foo.x, 0)

    def test_sdelegator3(self):
        """test adding special methods"""
        foo = Foo()
        self.assertFalse(foo._enter)
        self.assertFalse(foo._exit)
        sdel = StringifiedDelegator(foo, foo.__enter__, foo.__exit__)
        with sdel:
            self.assertTrue(foo._enter)
            self.assertFalse(foo._exit)
        self.assertTrue(foo._exit)

    def test_sdelegator4(self):
        """test __del__ method (not delegated)"""
        foo = Foo()
        sdel = StringifiedDelegator(foo)
        self.assertFalse(sdel._del)
        self.assertFalse(foo._del)
        del sdel
        self.assertFalse(foo._del)

    def test_sdelegator5(self):
        """test __del__ method (delegate it)"""
        foo = Foo()
        sdel = StringifiedDelegator(foo, foo.__del__)
        self.assertFalse(sdel._del)
        self.assertFalse(foo._del)
        del sdel
        self.assertTrue(foo._del)

    def test_sdelegator6(self):
        """test __del__ method (two references)"""
        foo = Foo()
        sdel = StringifiedDelegator(foo, foo.__del__)
        ref = sdel
        self.assertFalse(sdel._del)
        self.assertFalse(foo._del)
        del sdel
        self.assertFalse(foo._del)
        del ref
        self.assertTrue(foo._del)

    def test_sdelegator7(self):
        """delegator str is immutable"""
        foo = Foo()
        sdel = StringifiedDelegator(foo)
        self.assertEqual(sdel, 'foo')
        foo.name = 'bar'
        self.assertEqual(str(foo), 'bar')
        self.assertEqual(sdel, 'foo')

    def test_sdelegator8(self):
        """test kwargs"""
        foo = Foo()
        sdel = StringifiedDelegator(foo, my_acc=foo.acc, inc=foo.acc)
        self.assertEqual(foo.i, 0)
        sdel.acc()
        sdel.my_acc()
        sdel.inc()
        self.assertEqual(foo.i, 3)

    def test_sdelegator9(self):
        """test args and kwargs"""
        foo = Foo()
        func = lambda: 'foobar'
        sdel = StringifiedDelegator(foo, foo.endswith, inc=foo.acc,
                                    foobar=func)
        self.assertEqual(sdel, 'foo')
        self.assertFalse(sdel.endswith('o'))
        sdel.inc()
        self.assertEqual(sdel.i, 1)
        self.assertEqual(sdel.foobar(), 'foobar')
        self.assertFalse(hasattr(foo, 'foobar'))

    def test_sdelegator10(self):
        """test illegal arguments"""
        foo = Foo()
        self.assertRaises(ValueError, StringifiedDelegator, None)
        self.assertRaises(ValueError, StringifiedDelegator, foo,
                          foo.endswith, endswith=foo.acc)

if __name__ == '__main__':
    unittest.main()
