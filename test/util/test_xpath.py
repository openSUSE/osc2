import os
import unittest

from osc.util.xpath import XPathBuilder, XPathSyntaxError, Tree
from test.osctest import OscTest


def suite():
    return unittest.makeSuite(TestXPath)


class TestXPath(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = os.path.join('util', 'test_xpath_fixtures')
        super(TestXPath, self).__init__(*args, **kwargs)

    def test_path1(self):
        """test a simple path expression (single path)"""
        xpb = XPathBuilder()
        xp = xpb.action
        self.assertEqual(xp.tostring(), '/action')

    def test_path2(self):
        """test a simple path expression"""
        xpb = XPathBuilder()
        xp = xpb.action.source
        self.assertEqual(xp.tostring(), '/action/source')

    def test_path3(self):
        """test attribute check"""
        xpb = XPathBuilder()
        xp = xpb.action.source.attr('project')
        self.assertEqual(xp.tostring(), '/action/source/@project')

    def test_path4(self):
        """test text check"""
        xpb = XPathBuilder()
        xp = xpb.state.comment.text() == 'some text'
        exp = '/state/comment/text() = "some text"'
        self.assertEqual(xp.tostring(), exp)

    def test_path5(self):
        """test descendant axis"""
        xpb = XPathBuilder()
        xp = xpb.descendant('foo').bar.descendant('baz')
        # do not use abbreviated syntax
        exp = '/descendant::foo/bar/descendant::baz'
        self.assertEqual(xp.tostring(), exp)

    def test_path6(self):
        """test preceding axis"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar.preceding('baz').foobar
        # no abbreviated syntax for the preceding axis (afaik)
        exp = '/foo/bar/preceding::baz/foobar'
        self.assertEqual(xp.tostring(), exp)

    def test_path7(self):
        """test parent axis"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar.parent('baz').foobar
        # do not use abbreviated syntax
        exp = '/foo/bar/parent::baz/foobar'
        self.assertEqual(xp.tostring(), exp)

    def test_path8(self):
        """test a path join"""
        xpb = XPathBuilder()
        xp_1 = xpb.foo.baz
        xp_2 = xpb.bar.abc.join(xp_1)
        exp = '/bar/abc/foo/baz'
        self.assertEqual(xp_1, xp_2)
        self.assertEqual(xp_2.tostring(), exp)

    def test_path9(self):
        """test a comparison of two expressions"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar == xpb.foobar
        exp = '/foo/bar = /foobar'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop1(self):
        """test "&" (and) path expression"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar & xpb.bar.foo
        exp = '/foo/bar and /bar/foo'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop2(self):
        """test "and" (and) path expression"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar.log_and(xpb.bar.foo)
        exp = '/foo/bar and /bar/foo'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop3(self):
        """test "|" (or) path expression"""
        xpb = XPathBuilder()
        # do not confuse with xpath's union op!
        xp = xpb.a.b.c | xpb.foo
        exp = '/a/b/c or /foo'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop4(self):
        """test "or" (or) path expression"""
        xpb = XPathBuilder()
        xp = xpb.a.b.c.log_or(xpb.foo)
        exp = '/a/b/c or /foo'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop5(self):
        """test "!" (not) path expression"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar.log_not()
        exp = 'not(/foo/bar)'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop6(self):
        """test "not" (not) path expression"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar.log_not()
        exp = 'not(/foo/bar)'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop7(self):
        """test "and" and "or" path expression"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar | xpb.foobar & xpb.action.source
        exp = '/foo/bar or /foobar and /action/source'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop8(self):
        """test "and" and "or" with explicit parentheses"""
        xpb = XPathBuilder()
        xp = (xpb.foo.bar | xpb.foobar).parenthesize() & xpb.action.source
        exp = '(/foo/bar or /foobar) and /action/source'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop9(self):
        """test "and" and "or" with explicit parentheses (written ops)"""
        xpb = XPathBuilder()
        xp = (xpb.foo.bar.log_or(xpb.foobar)
              .parenthesize().log_and(xpb.action.source))
        exp = '(/foo/bar or /foobar) and /action/source'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop10(self):
        """test parenthesize more complex path expression"""
        xpb = XPathBuilder()
        xp = (xpb.foo & xpb.bar | xpb.baz).parenthesize() & xpb.foobar
        exp = '(/foo and /bar or /baz) and /foobar'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop11(self):
        """test parenthesize more complex path expression (written ops)"""
        xpb = XPathBuilder()
        xp = (xpb.foo.log_and(xpb.bar)
              .log_or(xpb.baz).parenthesize()
              .log_and(xpb.foobar))
        exp = '(/foo and /bar or /baz) and /foobar'
        self.assertEqual(xp.tostring(), exp)
        # different notation but same xpath expression (no explicit braces!)
        xp = ((xpb.foo.log_and(xpb.bar.log_or(xpb.baz)))
              .parenthesize().log_and(xpb.foobar))

    def test_pathop12(self):
        """test parenthesize (unusual use case)"""
        xpb = XPathBuilder()
        # braces not needed
        xp = xpb.foo & (xpb.bar.foo).parenthesize() | xpb.foobar
        exp = '/foo and (/bar/foo) or /foobar'
        self.assertEqual(xp.tostring(), exp)

    def test_pathop13(self):
        """test parenthesize (unusual use case) (written ops)"""
        xpb = XPathBuilder()
        # braces not needed
        xp = xpb.foo.log_and(xpb.bar.foo.parenthesize()).log_or(xpb.foobar)
        exp = '/foo and (/bar/foo) or /foobar'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate1(self):
        """test a path expression with simple predicate"""
        xpb = XPathBuilder()
        xp = xpb.action.source[xpb.attr('project') == 'bar']
        exp = '/action/source[@project = "bar"]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate2(self):
        """test a path expression with simple predicate (written ops)"""
        xpb = XPathBuilder()
        xp = xpb.action.source.where(xpb.attr('project').equals('bar'))
        exp = '/action/source[@project = "bar"]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate3(self):
        """test a path expression with multiple predicates"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar[xpb.attr('name') != 'abc'][xpb.attr('x') == 'foo']
        exp = '/foo/bar[@name != "abc"][@x = "foo"]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate4(self):
        """test a path expression with multiple predicates (written ops)"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar.where(xpb.attr('name').not_equals('abc'))
        xp = xp.where(xpb.attr('x').equals('foo'))
        exp = '/foo/bar[@name != "abc"][@x = "foo"]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate5(self):
        """test a path expression with a "position" predicate"""
        xpb = XPathBuilder()
        xp = xpb.foobar[2]
        exp = '/foobar[2]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate6(self):
        """test a path expression with a "position" predicate (written ops)"""
        xpb = XPathBuilder()
        xp = xpb.foobar.where(2)
        exp = '/foobar[2]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate7(self):
        """test a predicate with more conditions"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar[(xpb.attr('name') == 'foo') & (xpb.attr('x') == 'x')]
        exp = '/foo/bar[@name = "foo" and @x = "x"]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate8(self):
        """test a predicate with more conditions (written ops)"""
        xpb = XPathBuilder()
        pred = (xpb.attr('name').equals('foo')
                .log_and(xpb.attr('x').equals('x')))
        xp = xpb.foo.bar.where(pred)
        exp = '/foo/bar[@name = "foo" and @x = "x"]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate9(self):
        """test a predicate with attribute and path expression"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar[(xpb.attr('foo') == 'bar') | xpb.foobar]
        exp = '/foo/bar[@foo = "bar" or /foobar]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate10(self):
        """test a predicate with attribute and path expression (written ops)"""
        xpb = XPathBuilder()
        pred = xpb.attr('foo').equals('bar').log_or(xpb.foobar)
        xp = xpb.foo.bar.where(pred)
        exp = '/foo/bar[@foo = "bar" or /foobar]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate11(self):
        """test a "chained" predicate"""
        xpb = XPathBuilder()
        xp = xpb.a.b.c[(xpb.attr('d') == 'e') & xpb.foo[xpb.attr('z') == 'ab']]
        exp = '/a/b/c[@d = "e" and /foo[@z = "ab"]]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate12(self):
        """test a "chained" predicate (written ops)"""
        xpb = XPathBuilder()
        pred = (xpb.attr('d').equals('e')
                .log_and(xpb.foo.where(xpb.attr('z').equals('abc'))))
        xp = xpb.a.b.c.where(pred)
        exp = '/a/b/c[@d = "e" and /foo[@z = "abc"]]'
        self.assertEqual(xp.tostring(), exp)

    def test_predicate13(self):
        """test contains function"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar[xpb.attr('x').contains('foo')]
        exp = '/foo/bar[contains(@x, "foo")]'
        self.assertEqual(xp.tostring(), exp)

    def test_generator1(self):
        """test a non generator (everything happens in place)"""
        xpb = XPathBuilder()
        xp = xpb.foo
        xp = xp.bar
        xp = xp.baz[xpb.attr('x') == 'y']
        xp = xp[1]
        exp = '/foo/bar/baz[@x = "y"][1]'
        self.assertEqual(xp.tostring(), exp)

    def test_generator2(self):
        """test a non generator (everything happens in place) (written ops)"""
        xpb = XPathBuilder()
        xp = xpb.foo
        xp = xp.bar
        xp = xp.baz.where(xpb.attr('x').equals('y'))
        xp = xp.where(1)
        exp = '/foo/bar/baz[@x = "y"][1]'
        self.assertEqual(xp.tostring(), exp)

    def test_generator3(self):
        """test a xpath generator"""
        xpb = XPathBuilder()
        xp1 = xp2 = None
        base_xp = xpb.base.foo[xpb.attr('abc') == 'x']
        with base_xp as b:
            xp1 = b().bar.text() == 'foo'
            xp2 = b().x.y.z[42]
        base_exp = '/base/foo[@abc = "x"]'
        xp1_exp = '/base/foo[@abc = "x"]/bar/text() = "foo"'
        xp2_exp = '/base/foo[@abc = "x"]/x/y/z[42]'
        self.assertEqual(base_xp.tostring(), base_exp)
        self.assertEqual(xp1.tostring(), xp1_exp)
        self.assertEqual(xp2.tostring(), xp2_exp)

    def test_generator4(self):
        """test a xpath generator (written ops)"""
        xpb = XPathBuilder()
        xp1 = xp2 = None
        base_xp = xpb.base.foo.where(xpb.attr('abc').equals('x'))
        with base_xp as b:
            xp1 = b().bar.text().equals('foo')
            xp2 = b().x.y.z.where(42)
        base_exp = '/base/foo[@abc = "x"]'
        xp1_exp = '/base/foo[@abc = "x"]/bar/text() = "foo"'
        xp2_exp = '/base/foo[@abc = "x"]/x/y/z[42]'
        self.assertEqual(base_xp.tostring(), base_exp)
        self.assertEqual(xp1.tostring(), xp1_exp)
        self.assertEqual(xp2.tostring(), xp2_exp)

    def test_generator5(self):
        """test a xpath generator (path join - append generated)"""
        xpb = XPathBuilder()
        xp = None
        base_xp = xpb.base.foo.bar
        base_gen = None
        with base_xp as b:
            base_gen = b
            xp = b().join(xpb.a.b.c[3])
        exp = '/base/foo/bar/a/b/c[3]'
        base_exp = '/base/foo/bar'
        # check tree structure
        self.assertTrue(base_xp._parent is None)
        self.assertTrue(len(base_xp._children[0]._children[0]._children) == 0)
        self.assertTrue(base_gen._parent is None)
        self.assertTrue(len(base_gen._children) == 0)
        # check xpath
        self.assertEqual(xp.tostring(), exp)
        self.assertEqual(base_xp.tostring(), base_exp)
        self.assertEqual(base_gen.tostring(), base_exp)

    def test_generator6(self):
        """test a xpath generator (path join - prefix generated)"""
        xpb = XPathBuilder()
        xp1 = xp2 = None
        base_xp = xpb.base.foo.bar
        base_gen = None
        with base_xp as b:
            base_gen = b
            xp1 = xpb.a.b.c.join(b())
            xp2 = xpb.test.join(b())
        xp1_exp = '/a/b/c/base/foo/bar'
        xp2_exp = '/test/base/foo/bar'
        base_exp = '/base/foo/bar'
        # check tree structure
        self.assertTrue(base_xp._parent is None)
        self.assertTrue(len(base_xp._children[0]._children[0]._children) == 0)
        self.assertTrue(base_gen._parent is None)
        self.assertTrue(len(base_gen._children) == 0)
        # check xpath
        self.assertEqual(xp1.tostring(), xp1_exp)
        self.assertEqual(xp2.tostring(), xp2_exp)
        self.assertEqual(base_xp.tostring(), base_exp)
        self.assertEqual(base_gen.tostring(), base_exp)

    def test_generator7(self):
        """test a xpath generator (the root node is a BinaryExpression)"""
        xpb = XPathBuilder()
        xp1 = xp2 = None
        base_xp = xpb.foo.bar & xpb.x.y
        base_gen = None
        with base_xp as b:
            base_gen = b
            xp1 = b() | xpb.c
            xp2 = b() | xpb.d
        xp1_exp = '/foo/bar and /x/y or /c'
        xp2_exp = '/foo/bar and /x/y or /d'
        base_exp = '/foo/bar and /x/y'
        # check tree structure
        self.assertTrue(base_xp._parent is None)
        self.assertTrue(base_gen._parent is None)
        # check xpath
        self.assertEqual(xp1.tostring(), xp1_exp)
        self.assertEqual(xp2.tostring(), xp2_exp)
        self.assertEqual(base_xp.tostring(), base_exp)
        self.assertEqual(base_gen.tostring(), base_exp)

    def test_generator8(self):
        """test a xpath generator (root node is a ParenthesizedExpression)"""
        xpb = XPathBuilder()
        xp1 = xp2 = None
        base_xp = (xpb.foo.bar | xpb.x.y).parenthesize()
        base_gen = None
        with base_xp as b:
            base_gen = b
            xp1 = b() & xpb.c
            xp2 = b() & xpb.d
        xp1_exp = '(/foo/bar or /x/y) and /c'
        xp2_exp = '(/foo/bar or /x/y) and /d'
        base_exp = '(/foo/bar or /x/y)'
        # check tree structure
        self.assertTrue(base_xp._parent is None)
        self.assertTrue(base_gen._parent is None)
        # check xpath
        self.assertEqual(xp1.tostring(), xp1_exp)
        self.assertEqual(xp2.tostring(), xp2_exp)
        self.assertEqual(base_xp.tostring(), base_exp)
        self.assertEqual(base_gen.tostring(), base_exp)

    def test_context_item1(self):
        """test context item for the initial expression"""
        xpb = XPathBuilder(context_item=True)
        xp1 = xpb.foo.bar
        xp1_exp = './foo/bar'
        xp2 = xpb.context(False).foo.bar
        xp2_exp = '/foo/bar'
        self.assertEqual(xp1.tostring(), xp1_exp)
        self.assertEqual(xp2.tostring(), xp2_exp)
        self.assertTrue(xpb.context_item)

    def test_context_item2(self):
        """test context item (disabled) for the initial expression"""
        xpb = XPathBuilder(context_item=False)
        xp1 = xpb.foo.bar
        xp1_exp = '/foo/bar'
        xp2 = xpb.context(True).foo.bar
        xp2_exp = './foo/bar'
        self.assertEqual(xp1.tostring(), xp1_exp)
        self.assertEqual(xp2.tostring(), xp2_exp)
        self.assertFalse(xpb.context_item)

    def test_context_item3(self):
        """test context item (nested expression)"""
        xpb = XPathBuilder()
        xp = xpb.foo[xpb.context(True).bar | xpb.context(True).baz]
        exp = '/foo[./bar or ./baz]'
        self.assertEqual(xp.tostring(), exp)

    def test_context_item4(self):
        """test context item (nested expression) (written ops)"""
        xpb = XPathBuilder()
        xp = xpb.foo.where(xpb.context(True).bar.log_or(xpb.context(True).baz))
        exp = '/foo[./bar or ./baz]'
        self.assertEqual(xp.tostring(), exp)

    def test_exception1(self):
        """test invalid expression tree"""
        xpb = XPathBuilder()
        pred = xpb.attr('foo') == 'bar'
        path = xpb.foo.bar
        pred_expr = path[pred]
        self.assertEqual(pred_expr.tostring(), '/foo/bar[@foo = "bar"]')
        l = [xpb.foo]
        pred.reparent(None)
        self.assertRaises(XPathSyntaxError, pred_expr.tostring)

    def test_tree_mode1(self):
        """test the tree mode"""
        tree_1 = Tree(children=[])
        tree_2 = Tree(children=[])
        self.assertFalse(tree_1.is_tree_mode())
        tree_1.tree_mode(True, tree_1)
        self.assertTrue(tree_1.is_tree_mode())
        # tree_2 is not allowed to disable the tree mode
        tree_1.tree_mode(False, tree_2)
        self.assertTrue(tree_1.is_tree_mode())
        tree_1.tree_mode(False, tree_1)
        self.assertFalse(tree_1.is_tree_mode())

    def test_tree_mode2(self):
        """test list context in tree mode"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar
        xp.tree_mode(True, xp)
        bar = xpb.bar
        bar.tree_mode(True, xp)
        baz = xpb.baz
        baz.tree_mode(True, xp)
        foo_bar = xpb.foo.bar
        foo_bar.tree_mode(True, xp)
        self.assertTrue(xp.is_tree_mode())
        l = [bar, foo_bar, xp, baz]
        self.assertTrue(xp in l)
        l.remove(xp)
        self.assertTrue(len(l) == 3)
        self.assertFalse(xp in l)
        xp.tree_mode(False, xp)
        self.assertFalse(xp.is_tree_mode())

    def test_tree_mode3(self):
        """test tree operation (remove_child)"""
        xpb = XPathBuilder()
        xp_1 = xpb.foo
        xp_2 = xpb.baz
        xp_and = xp_1 & xp_2
        self.assertTrue(xp_and._parent is None)
        self.assertTrue(len(xp_and._children) == 2)
        self.assertTrue(xp_and._children[0] is xp_1)
        self.assertTrue(xp_and._children[1] is xp_2)
        self.assertTrue(xp_1._parent is xp_and)
        self.assertTrue(len(xp_1._children) == 0)
        self.assertTrue(xp_2._parent is xp_and)
        self.assertTrue(len(xp_2._children) == 0)
        xp_and.remove_child(xp_2)
        # check references after remove
        self.assertTrue(xp_and._parent is None)
        self.assertTrue(len(xp_and._children) == 1)
        self.assertTrue(xp_and._children[0] is xp_1)
        self.assertTrue(xp_1._parent is xp_and)
        self.assertTrue(len(xp_1._children) == 0)
        # xp_2's references were changed
        self.assertTrue(xp_2._parent is None)
        self.assertTrue(len(xp_2._children) == 0)

    def test_tree_mode4(self):
        """test tree operation (reparent - nearly the same as above)"""
        xpb = XPathBuilder()
        xp_1 = xpb.foo
        xp_2 = xpb.baz
        xp_and = xp_1 & xp_2
        self.assertTrue(xp_and._parent is None)
        self.assertTrue(len(xp_and._children) == 2)
        self.assertTrue(xp_and._children[0] is xp_1)
        self.assertTrue(xp_and._children[1] is xp_2)
        self.assertTrue(xp_1._parent is xp_and)
        self.assertTrue(len(xp_1._children) == 0)
        self.assertTrue(xp_2._parent is xp_and)
        self.assertTrue(len(xp_2._children) == 0)
        xp_2.reparent(None)
        # check references after remove
        self.assertTrue(xp_and._parent is None)
        self.assertTrue(len(xp_and._children) == 1)
        self.assertTrue(xp_and._children[0] is xp_1)
        self.assertTrue(xp_1._parent is xp_and)
        self.assertTrue(len(xp_1._children) == 0)
        # xp_2's references were changed
        self.assertTrue(xp_2._parent is None)
        self.assertTrue(len(xp_2._children) == 0)

    def test_non_hashable1(self):
        """test hash() on an expression"""
        xpb = XPathBuilder()
        xp = xpb.foo.bar
        d = {}
        self.assertRaises(TypeError, hash, xp)
        self.assertRaises(TypeError, d.setdefault, xp, 'key')

    def test_dummy1(self):
        """test dummy method 1"""
        xpb = XPathBuilder()
        xp = xpb.dummy()
        self.assertFalse(xp)
        xp = xp & xpb.foo.bar
        self.assertTrue(xp)
        exp = '/foo/bar'
        self.assertEqual(xp.tostring(), exp)

    def test_dummy2(self):
        """test dummy method 2"""
        xpb = XPathBuilder()
        xp = xpb.dummy()
        self.assertFalse(xp)
        xp = xp & (xpb.attr('foo') == 'xyz')
        self.assertTrue(xp)
        exp = '@foo = "xyz"'
        self.assertEqual(xp.tostring(), exp)

    def test_dummy3(self):
        """test DummyExpression's parenthesize method"""
        xpb = XPathBuilder()
        xp = xpb.dummy()
        self.assertTrue(xp.parenthesize() is xp)

    def test_dummy4(self):
        """test DummyExpression negate (log_not)"""
        xpb = XPathBuilder()
        xp = xpb.dummy()
        self.assertTrue(xp.log_not() is xp)

    def test_dummy5(self):
        """test DummyExpression on the right hand side of "and" op"""
        xpb = XPathBuilder()
        xp = xpb.dummy()
        xp = xpb.foo & xp
        exp = '/foo'
        self.assertEqual(xp.tostring(), exp)

    def test_dummy6(self):
        """test DummyExpression on the right hand side of "or" op"""
        xpb = XPathBuilder()
        xp = xpb.dummy()
        xp = xpb.bar | xp
        exp = '/bar'
        self.assertEqual(xp.tostring(), exp)

if __name__ == '__main__':
    unittest.main()
