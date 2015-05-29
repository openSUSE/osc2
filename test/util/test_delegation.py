import unittest

from osc2.util.delegation import StringifiedDelegator, Delegator
from test.osctest import OscTestCase


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
class TestDelegation(OscTestCase):

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

    def test_getattr_no_max_recursion(self):
        """count getattr calls to avoid a max recursion RuntimeError"""
        class CountingDelegator(Delegator):
            # use a class level counter so that the counting
            # does not influence the behavior of __getattr__; if we
            # would use an instance attribute, the behavior of __getattr__
            # would have been altered (accessing an instance attribute leads
            # to an infinite recursion)
            _getattr_cnt = 0

            def __getattr__(self, key):
                CountingDelegator._getattr_cnt += 1
                return super(CountingDelegator, self).__getattr__(key)

        foo = Foo()
        cdel = CountingDelegator(foo)
        self.assertEqual(CountingDelegator._getattr_cnt, 0)
        self.assertEqual(cdel.i, 0)
        self.assertEqual(CountingDelegator._getattr_cnt, 1)
        cdel.attr = None
        self.assertEqual(CountingDelegator._getattr_cnt, 1)
        self.assertIsNone(cdel.attr)
        self.assertEqual(CountingDelegator._getattr_cnt, 2)
        cdel.acc()
        self.assertEqual(CountingDelegator._getattr_cnt, 3)
        self.assertEqual(cdel.i, 1)
        self.assertEqual(CountingDelegator._getattr_cnt, 4)

    def test_correct_subclassing(self):
        """test "correct"/"expected" subclassing behavior"""
        class CorrectDelegator(Delegator):
            def __init__(self, delegate):
                self.foobar = 42
                super(CorrectDelegator, self).__init__(delegate)
        foo = Foo()
        cdel = CorrectDelegator(foo)
        self.assertEqual(cdel.foobar, 42)
        # the foobar attribute was _not_ set on the delegate
        self.assertFalse(hasattr(foo, 'foobar'))
        # modify foobar
        cdel.foobar = 24
        self.assertEqual(cdel.foobar, 24)
        self.assertFalse(hasattr(foo, 'foobar'))
        # the delegate can be changed as well (usually instantiating
        # a new delegator instance is the better choice (w.r.t.
        # code readability))
        foo2 = Foo()
        cdel._delegate = foo2
        cdel.acc()
        self.assertEqual(cdel.i, 1)
        self.assertEqual(foo2.i, 1)
        # the old delegate was not changed
        self.assertEqual(foo.i, 0)

    def test_wrong_subclassing(self):
        """test "wrong"/"unexpected" subclassing behavior"""
        class WrongDelegator(Delegator):
            def __init__(self, delegate):
                # call the superclass' __init__ before setting
                # our own attributes
                super(WrongDelegator, self).__init__(delegate)
                # this sets the foobar attribute on the delegate
                # instead on the delegator instance
                self.foobar = 42

        foo = Foo()
        wdel = WrongDelegator(foo)
        self.assertEqual(wdel.foobar, 42)
        # the foobar attribute was set on the delegate
        self.assertTrue(hasattr(foo, 'foobar'))
        # modify foobar
        wdel.foobar = 24
        self.assertEqual(wdel.foobar, 24)
        self.assertEqual(foo.foobar, 24)

    def test_hiding(self):
        """delegator attributes hide delegate attributes"""
        # hides the attribute "i" and method "acc"
        class HidingDelegator(Delegator):
            def __init__(self, delegate):
                self.i = 42
                super(HidingDelegator, self).__init__(delegate)

            def acc(self):
                self.i -= 1

        foo = Foo()
        hdel = HidingDelegator(foo)
        self.assertEqual(hdel.i, 42)
        self.assertEqual(foo.i, 0)
        hdel.acc()
        self.assertEqual(hdel.i, 41)
        self.assertEqual(foo.i, 0)
        foo.acc()
        self.assertEqual(hdel.i, 41)
        self.assertEqual(foo.i, 1)

if __name__ == '__main__':
    unittest.main()
