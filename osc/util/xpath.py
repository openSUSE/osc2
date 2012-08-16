"""This module provides classes to build a XPath.

The XPathBuilder class can be used to build an xpath expression
in a "natural" and "pythonic" way.

This module is mainly inspired by https://github.com/jnicklas/xpath
(especially the syntax of the DSL).

"""


def children(minimum, maximum):
    """Decorator which checks the number of an expression's children.

    It raises a XPathSyntaxError if it has less than minimum or
    more than maximum children.

    """
    def decorate(f):
        def checker(self, *args, **kwargs):
            len_children = len(self._children)
            if len_children < minimum:
                msg = "At least '%d' children required." % minimum
                raise XPathSyntaxError(msg)
            if len_children > maximum:
                msg = "At most '%d' children allowed." % maximum
                raise XPathSyntaxError(msg)
            return f(self, *args, **kwargs)

        checker.func_name = f.func_name
        return checker

    return decorate


class XPathSyntaxError(SyntaxError):
    """Raised if the expression tree is (syntactically) invalid."""
    pass


class XPathBuilder(object):
    """Provides methods to build a xpath expression in a pythonic way.

    It is the interface between the user and the internal classes.

    """

    def __init__(self, factory=None, context_item=False):
        """Constructs a new XPathBuilder object.

        Keyword arguments:
        factory -- the factory which is used for creating the xpath
                   expressions (default: XPathFactory)
        context_item -- if True the default expression is a context item
                        expression - otherwise it's a simple path expression
                        (default: False)

        """
        super(XPathBuilder, self).__init__()
        self._factory = factory or XPathFactory()
        self.context_item = context_item

    def context(self, context_item):
        """Returns a new XPathBuilder object.

        The context_item parameter specifies if the default expression of the
        new XPathBuilder object is a context item expression or not.

        """
        return XPathBuilder(self._factory, context_item)

    def attr(self, *args, **kwargs):
        """Returns a new AttributeExpression object.

        *args and **kwargs are additional arguments for the
        AttributeExpression's __init__ method.

        """
        kwargs.setdefault('in_pred', True)
        return self._factory.create_AttributeExpression(*args, **kwargs)

    def dummy(self):
        """Returns a new DummyExpression object.

        *args and **kwargs are additional arguments for the
        DummyExpression's __init__ method.

        """
        return self._factory.create_DummyExpression()

    def __getattr__(self, name):
        """Delegetates the call to a new PathExpression object.

        name is the name of the requested attribute.

        """
        ci = self.context_item
        dummy = self._factory.create_PathExpression('', init=True,
                                                    context_item=ci)
        expr = getattr(dummy, name)
        return expr


class XPathFactory(object):
    """Factory to create the expression objects.

    This way it's possible replace the existing expression
    classes with its own implementation.

    """

    def create_PathExpression(self, *args, **kwargs):
        """Constructs a new PathExpression Object.

        *args and **kwargs are additional arguments for the
        PathExpression's __init__ method.

        """
        kwargs.setdefault('factory', self)
        return PathExpression(*args, **kwargs)

    def create_FunctionExpression(self, *args, **kwargs):
        """Constructs a new FunctionExpression Object.

        *args and **kwargs are additional arguments for the
        FunctionExpression's __init__ method.

        """
        kwargs.setdefault('factory', self)
        return FunctionExpression(*args, **kwargs)

    def create_BinaryExpression(self, *args, **kwargs):
        """Constructs a new BinaryExpression Object.

        *args and **kwargs are additional arguments for the
        BinaryExpression's __init__ method.

        """
        kwargs.setdefault('factory', self)
        return BinaryExpression(*args, **kwargs)

    def create_AttributeExpression(self, *args, **kwargs):
        """Constructs a new AttributeExpression Object.

        *args and **kwargs are additional arguments for the
        AttributeExpression's __init__ method.

        """
        kwargs.setdefault('factory', self)
        return AttributeExpression(*args, **kwargs)

    def create_PredicateExpression(self, *args, **kwargs):
        """Constructs a new PredicateExpression Object.

        *args and **kwargs are additional arguments for the
        PredicateExpression's __init__ method.

        """
        kwargs.setdefault('factory', self)
        return PredicateExpression(*args, **kwargs)

    def create_ParenthesizedExpression(self, *args, **kwargs):
        """Constructs a new ParenthesizedExpression Object.

        *args and **kwargs are additional arguments for the
        ParenthesizedExpression's __init__ method.

        """
        kwargs.setdefault('factory', self)
        return ParenthesizedExpression(*args, **kwargs)

    def create_LiteralExpression(self, *args, **kwargs):
        """Constructs a new LiteralExpression object.

        *args and **kwargs are additional arguments for the
        LiteralExpression's __init__ method.

        """
        kwargs.setdefault('factory', self)
        return LiteralExpression(*args, **kwargs)

    def create_GeneratorPathDelegate(self, *args, **kwargs):
        """Constructs a new GeneratorPathDelegate object.

        *args and **kwargs are additional arguments for the
        GeneratorPathDelegate's __init__ method.

        """
        kwargs.setdefault('factory', self)
        return GeneratorPathDelegate(*args, **kwargs)

    def create_GeneratorDelegate(self, delegate, *args, **kwargs):
        """Constructs a new GeneratorDelegate object.

        *args and **kwargs are additional arguments for the
        GeneratorDelegate's __init__ method.

        """
        base_cls = delegate.__class__
        class GeneratorDelegate(base_cls):
            """Used to generate expressions from a common base expression.

            Its main purpose is to wrap the base expression object so that
            all tree operations are executed on this object instead of the
            delegate.
            No children are added and just reparent operations are executed. In
            fact we could avoid this class if we wouldn't remove the child from
            the "old" parent if a reparent operation is executed.

            """

            def __init__(self, delegate, *args, **kwargs):
                """Constructs a new GeneratorDelegate object.

                delegate is the expression object which should be wrapped.
                *args, **kwargs are additional arguments for the base class'
                __init__ method.

                """
                super(self.__class__, self).__init__(*args, **kwargs)
                self._delegate = delegate

            def __call__(self):
                return self._factory.create_GeneratorDelegate(self._delegate)

            def tostring(self):
                return self._delegate.tostring()

        kwargs.setdefault('factory', self)
        # build dummy __init__ arguments
        dummy_args = []
        if delegate.__class__.__name__ != 'ParenthesizedExpression':
            # only a ParenthesizedExpression needs no dummy arg
            # (a PredicateExpression does not have to be considered because
            # it should never be passed to this method (use
            # createGeneratorPathDelegate instead))
            dummy_args.append('')
        return GeneratorDelegate(delegate, *dummy_args, **kwargs)

    def create_DummyExpression(self, *args, **kwargs):
        """Creates a new DummyExpression object.

        *args and **kwargs are additional arguments for the
        DummyExpression's __init__ method.

        """
        return DummyExpression(*args, **kwargs)


class Tree(object):
    """Represents a simple tree.

    A tree node might have an arbitrary number of children but
    only one parent or None (if it has no parent it is the root
    node).
    It is required that a Tree (or subclass) object can be used
    in list context that is something like "tree in list" evaluates
    to True if and only if the tree object is in the list.
    As there might be cases where a Tree subclass implements a
    __eq__ method (for example) so that the requirement from above
    is NOT satisfied a special "tree mode" is introduced.
    If an object is in the "tree mode" its customized __eq__
    method should NOT be executed (for instance it should return
    "NotImplemented").
    In the tree mode it is guaranteed that only the methods and
    attributes which are defined in this class will be invoked
    (except if a subclass modified these methods).

    """

    def tree_op():
        """Decorator which is used to decorate all tree methods.

        For each object which participates in the method call
        (self, the argument and our children) the tree_mode is
        enabled.

        """
        def decorator(f):
            def operation(self, tree):
                self.tree_mode(True, self)
                if tree is not None:
                    tree.tree_mode(True, self)
                for c in self._children:
                    c.tree_mode(True, self)
                f(self, tree)
                self.tree_mode(False, self)
                if tree is not None:
                    tree.tree_mode(False, self)
                for c in self._children:
                    c.tree_mode(False, self)
            operation.func_name = f.func_name
            return operation
        return decorator

    def __init__(self, children=None):
        """Constructs a new Tree object.

        Keyword arguments:
        children -- the children objects (default: None)

        """
        super(Tree, self).__init__()
        self._children = children or []
        self._parent = None
        self._tree_mode = None
        for c in self._children:
            c.reparent(self)

    @tree_op()
    def reparent(self, parent):
        """Sets a new parent object.

        parent is the new parent.

        """
        old_parent = self._parent
        self._parent = parent
        if old_parent is not None:
            old_parent.remove_child(self)

    @tree_op()
    def append_child(self, child):
        """Appends a child object.

        child is the newly appended child.

        """
        self._children.append(child)
        child.reparent(self)

    @tree_op()
    def remove_child(self, child):
        """Removes a child object.

        child is the child which should be removed.

        """
        if child in self._children:
            self._children.remove(child)
            child.reparent(None)

    def tree_mode(self, on, obj):
        """Enables or disables the tree mode for this (self) object.

        on specifies whether the tree mode is enabled or
        disabled (True means enabled, False means disabled).
        obj is the object which want to the change the tree mode.
        A tree mode can only be disabled by the object which
        enabled it.

        """
        if self._tree_mode is None and on:
            self._tree_mode = obj
        elif not on and self._tree_mode is obj:
            self._tree_mode = None

    def is_tree_mode(self):
        """Returns True if the tree mode is enabled otherwise False."""
        return self._tree_mode is not None


class Expression(Tree):
    """Abstract base class for all xpath expressions."""

    # Expressions are not hashable because __eq__ etc. are implemented
    # in an incompatible way
    __hash__ = None

    def disable_in_tree_mode():
        """Decorator which "disables" a method if the object is in tree mode.

        "Disabling" a method means in this context that it
        simply returns NotImplemented.

        """
        def decorator(f):
            def disable(self, *args, **kwargs):
                if self.is_tree_mode():
                    return NotImplemented
                return f(self, *args, **kwargs)

            disable.func_name = f.func_name
            return disable
        return decorator

    def __init__(self, factory, children=None):
        """Constructs a new Expression object.

        factory is the factory which is used for creating new
        expression objects.

        Keyword arguments:
        children -- the expression's children (default: None)

        """
        super(Expression, self).__init__(children)
        self._factory = factory

    def log_and(self, expr):
        """Connects self and expr via "and".

        expr is the right expression.

        """
        children = [self, expr]
        return self._factory.create_BinaryExpression('and', children=children)

    def log_or(self, expr):
        """Connects self and expr via "or".

        expr is the right expression.

        """
        children = [self, expr]
        return self._factory.create_BinaryExpression('or', children=children)

    def log_not(self):
        """Negate self."""
        # technically not is an xpath function and not a
        # logical expression so the method name is a bit misleading
        # this object is NOT a children just a parameter
        return self._factory.create_FunctionExpression('not', self,
                                                       in_pred=True,
                                                       children=[])

    def equals(self, literal):
        """Compares

        literal is a str literal.

        """
        lit_expr = self._expression_or_literal(literal)
        children = [self, lit_expr]
        return self._factory.create_BinaryExpression('=', children=children)

    def not_equals(self, literal):
        """Returns a BinaryExpression Object.

        literal is a str literal.

        """
        lit_expr = self._expression_or_literal(literal)
        children = [self, lit_expr]
        return self._factory.create_BinaryExpression('!=', children=children)

    def parenthesize(self):
        """Parenthesize self."""
        return self._factory.create_ParenthesizedExpression(children=[self])

    def tostring(self):
        """String representation of the expression"""
        raise NotImplementedError()

    def _expression_or_literal(self, expr):
        """Returns an Expression (or subclass) object.

        If expr is an Expression object expr is returned otherwise
        a LiteralExpression is returned.

        """
        if not hasattr(expr, 'reparent'):
            # treat it as a literal (the above is sufficient - we don't
            # do strict type checks like issubclass etc.)
            expr = self._factory.create_LiteralExpression(expr)
        return expr

    def __enter__(self):
        return self._factory.create_GeneratorDelegate(self)

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @disable_in_tree_mode()
    def __and__(self, other):
        return self.log_and(other)

    @disable_in_tree_mode()
    def __or__(self, other):
        return self.log_or(other)

    @disable_in_tree_mode()
    def __eq__(self, other):
        return self.equals(other)

    @disable_in_tree_mode()
    def __ne__(self, other):
        return self.not_equals(other)


class PathExpression(Expression):
    """Represents a xpath path expression"""

    def __init__(self, name, axis='', init=False,
                 context_item=False, **kwargs):
        """Constructs a new PathExpression object.

        name is the of the path component.
        **kwargs are the arguments for the superclass'
        __init__ method.

        Keyword arguments:
        axis -- the name of the axis (default: '' - child axis)
        init -- if True it indicates that this is the first expression
                in the expression tree (needs some special handling due
                to the way the XPathBuilder class works) (default: False)
        context_item -- if True the PathExpression is treated like a context
                        item expression (it starts with an initial '.')
                        (default: False)

        """
        super(PathExpression, self).__init__(**kwargs)
        self._name = name
        self._axis = axis
        self._init = init
        self._context_item = context_item

    def descendant(self, name):
        """Returns a PathExpression object for the descendant axis.

        name is the name of the path component.

        """
        return self._create_parent('Path', name, 'descendant')

    def preceding(self, name):
        """Returns a PathExpression object for the preceding axis.

        name is the name of the path component.

        """
        return self._create_parent('Path', name, 'preceding')

    def parent(self, name):
        """Returns a PathExpression object for the parent axis.

        name is the name of the path component.

        """
        return self._create_parent('Path', name, 'parent')

    def attr(self, name):
        """Returns an AttributeExpression object.

        name is the name of the attribute.

        """
        return self._create_parent('Attribute', name, in_pred=False)

    def where(self, expr):
        """Returns a PredicateExpression object.

        expr is the predicate expression or a (int) literal.

        """
        expr = self._expression_or_literal(expr)
        children = [self, expr]
        return self._factory.create_PredicateExpression(children=children)

    def join(self, expr):
        """Joins two (Path) Expressions and returns expr.

        expr is the (path) expression which is "appended".
        (Example: foo.bar.join(baz.foo) => /foo/bar/baz/foo)

        """
        leaf = expr
        # XXX: we should ensure that no infinite recursion is possible
        #      ignore it for now
        while leaf._children:
            leaf = leaf._children[0]
        leaf.append_child(self)
        return expr

    def text(self):
        """Returns a FunctionExpression object.

        This FunctionExpression represents a text() kind test.

        """
        return self._factory.create_FunctionExpression('text', in_pred=False,
                                                       children=[self])

    def _create_parent(self, kind, *args, **kwargs):
        """Returns a new Expression object which is the new parent"""
        if self._init:
            self._init = False
            kwargs.setdefault('context_item', self._context_item)
        else:
            kwargs.setdefault('children', [self])
        meth = getattr(self._factory, 'create_' + kind + 'Expression')
        expr = meth(*args, **kwargs)
        return expr

    def __getattr__(self, name):
        return self._create_parent('Path', name)

    def __getitem__(self, key):
        return self.where(key)

    def __enter__(self):
        return self._factory.create_GeneratorPathDelegate(self)

    @children(0, 1)
    def tostring(self):
        res = ''
        if self._children:
            res = self._children[0].tostring()
        if self._context_item:
            res += '.'
        if self._axis:
            return res + "/%s::%s" % (self._axis, self._name)
        return res + "/%s" % self._name


class AttributeExpression(Expression):
    """Represents an attribute expression."""

    def __init__(self, name, in_pred=False, **kwargs):
        """Constructs a new AttributeExpression object.

        name is the name of the attribute.
        **kwargs are the arguments for the superclass'
        __init__ method.

        Keyword arguments:
        in_pred -- indicates if this attribute is used in a
                   predicate or in a path (default: False)

        """
        super(AttributeExpression, self).__init__(**kwargs)
        self._name = name
        self._in_pred = in_pred

    def contains(self, literal):
        """Returns a FunctionExpression object.

        literal is a str literal.
        The FunctionExpression represents the "contains(attr, literal)"
        xpath function.

        """
        lit_expr = self._expression_or_literal(literal)
        return self._factory.create_FunctionExpression('contains', self,
                                                       lit_expr,
                                                       in_pred=self._in_pred,
                                                       children=[])

    def tostring(self):
        if self._in_pred:
            return '@' + self._name
        if self._children:
            return self._children[0].tostring() + '/@' + self._name
        return '/@' + self._name


class LiteralExpression(Expression):
    """Represents a literal."""

    def __init__(self, literal, **kwargs):
        """Constructs a new LiteralExpression object.

        literal is the literal which should be represented
        by this object. If the literal is a string (it is treated
        as a string if it has a "upper" attribute/method (this was
        arbitrarily chosen)) it sourrunded with "". Otherwise its
        str representation is returned.
        **kwargs are the arguments for the superclass'
        __init__ method.

        """
        super(LiteralExpression, self).__init__(**kwargs)
        self._literal = literal

    @children(0, 0)
    def tostring(self):
        if hasattr(self._literal, 'upper'):
            # treat it as a string
            return "\"%s\"" % str(self._literal)
        return str(self._literal)


class PredicateExpression(PathExpression):
    """Represents a xpath predicate"""

    def __init__(self, **kwargs):
        """Constructs a new PredicateExpression object.

        **kwargs are the arguments for the superclass'
        __init__ method.

        """
        super(PredicateExpression, self).__init__('', **kwargs)

    @children(2, 2)
    def tostring(self):
        return "%s[%s]" % (self._children[0].tostring(),
                           self._children[1].tostring())


class BinaryExpression(Expression):
    """Represents a binary (operator) expression in infix notation."""

    def __init__(self, op, **kwargs):
        """Constructs a new BinaryExpression object.

        op is the binary operator which is used to connect children[0]
        and children[1]. children[0] is the left and children[1] the
        right expression.
        **kwargs are the arguments for the superclass'
        __init__ method.

        """
        super(BinaryExpression, self).__init__(**kwargs)
        self._op = op

    @children(2, 2)
    def tostring(self):
        return "%s %s %s" % (self._children[0].tostring(), self._op,
                             self._children[1].tostring())


class FunctionExpression(Expression):
    """Represents a xpath function in "prefix notation"."""

    def __init__(self, name, *params, **kwargs):
        """Constructs a new FunctionExpression object.

        name is the name of the function and params are
        the parameters.
        **kwargs are the arguments for the superclass'
        __init__ method.

        Keyword arguments:
        in_pred -- indicates if this function is used in a
                   predicate or in a path (default: False)

        """
        in_pred = kwargs.pop('in_pred', False)
        super(FunctionExpression, self).__init__(**kwargs)
        self._name = name
        # hmm it might be better to treat the params as children
        self._params = []
        self._in_pred = in_pred
        for p in params:
            expr = self._expression_or_literal(p)
            self._params.append(expr)

    def tostring(self):
        res = ''
        if self._children:
            res = self._children[0].tostring()
        params = [p.tostring() for p in self._params]
        if not self._in_pred:
            res += '/'
        return res + "%s(%s)" % (self._name, ', '.join(params))


class ParenthesizedExpression(Expression):
    """Represents a parenthesized expression."""

    def __init__(self, **kwargs):
        """Constructs a new ParenthesizedExpression object.

        parentheses.
        **kwargs are the arguments for the superclass'
        __init__ method.

        """
        super(ParenthesizedExpression, self).__init__(**kwargs)

    @children(1, 1)
    def tostring(self):
        return "(%s)" % self._children[0].tostring()


class GeneratorPathDelegate(PathExpression):
    """Used to generate expressions from a common base PathExpression.

    Its main purpose is to wrap the base PathExpression (or subclass)
    object so that all tree operations are executed on this object
    instead of the delegate.

    """

    def __init__(self, delegate, **kwargs):
        """Constructs a new GeneratorPathDelegate object.

        delegate is the PathExpression (or subclass) object
        which should be wrapped.
        **kwargs are additional arguments for the Tree's
        __init__ method.

        """
        super(GeneratorPathDelegate, self).__init__('', **kwargs)
        self._delegate = delegate

    def __call__(self):
        return self._factory.create_GeneratorPathDelegate(self._delegate)

    @children(0, 1)
    def tostring(self):
        res = ''
        if self._children:
            res = self._children[0].tostring()
        return res + self._delegate.tostring()


class DummyExpression(object):
    """This class represents a dummy expression.

    Its sole purpose is to make the xpath code
    easier to read (we can avoid "xp is None" tests
    in a loop).

    """

    def parenthesize(self):
        return self

    def __and__(self, other):
        return other

    def __or__(self, other):
        return other

    def __eq__(self, other):
        return other

    def __ne__(self, other):
        return other

    def __nonzero__(self):
        return False
