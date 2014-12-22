"""Provides classes that facilitate delegation tasks.

These classes can be used, if normal duck typing is not sufficient
anymore. Suppose an instance of the class osc2.util.io.TemporaryDirectory
should be passed to the os.stat function. This will not work, because os.stat
requires a str/unicode or buffer instance as a parameter. Thus, simple
duck typing is insufficient (PyUnicode_FromEncodedObject, which is
indirectly called by posix_do_stat, has "strict" type checks).
So the idea is to wrap the TemporaryDirectory instance in an instance that
behaves like/is a str/unicode instance. Additionally, all non-str method
calls are delegated to the real TemporaryDirectory instance.
For this, this module provides several classes.

The use-case from above is implemented in the osc2.util.io.mkdtemp function.

"""

import inspect


class DynamicDecorator(object):
    """Dynamically enrich an existing type with additional methods.

    Actually, a new type, which provides the additional methods, is
    created that inherits from the existing type.

    """

    def __new__(cls, *args, **kwargs):
        """Returns an instance of a newly created type.

        The newly created type inherits from cls and provides additional
        methods, which are specified via *args and **kwargs.

        args is supposed to be a tuple of methods/functions.
        kwargs is supposed to be a dict that maps a "name" to a
        "method"/"function". These specified methods/functions will be
        part of the newly created type.
        In order to support cooperative inheritance, args and kwargs may
        contain additional arbitrary objects. These are ignored and passed
        to our superclass' __new__ method.
        If kwargs contains a key that is equal to the __name__ of a
        method/function in the args tuple, a ValueError is raised.

        """
        def _add(meths, call, name):
            if name in meths:
                msg = "duplicate method name: %s" % name
                raise ValueError(msg)
            meths[name] = call

        def _add_function(meths, func, name=''):
            # new_func is still a function!
            new_func = lambda self, *args, **kwargs: func(*args, **kwargs)
            _add(meths, new_func, name or func.__name__)

        def _add_method(meths, meth, name=''):
            _add(meths, meth, name or meth.__name__)

        id_args = id(args)
        id_kwargs = id(kwargs)
        args = list(args)
        meths = {}
        for i in args[:]:
            if inspect.isfunction(i):
                _add_function(meths, i)
                args.remove(i)
            elif inspect.ismethod(i):
                _add_method(meths, i)
                args.remove(i)
        for k, v in dict(kwargs).iteritems():
            if inspect.isfunction(v):
                _add_function(meths, v, k)
                del kwargs[k]
            elif inspect.ismethod(v):
                _add_method(meths, v, k)
                del kwargs[k]
        name = "%s_%s_%s" % (cls.__name__, id_args, id_kwargs)
        new_cls = type(name, (cls,), meths)
        return super(DynamicDecorator, cls).__new__(new_cls, *args, **kwargs)


class Delegator(DynamicDecorator):
    """Delegates certain method calls to the "delegate"."""

    def __init__(self, delegate, *args, **kwargs):
        """Constructs a new Delegator instance.

        delegate is the object to which, for example, method calls should
        be delegated to. If delegate is None, a ValueError is raised.

        *args and **kwargs can be used to decorate the Delegator instance
        with additional methods (see DynamicDelegator for the details).
        This is needed, if duck-typing is not sufficient anymore (e.g. some
        special methods have to be part of the type).

        Note: instead of specifying additional methods via *args and **kwargs,
        it is also possible to subclass this class and explicitly add the
        methods.

        """
        super(Delegator, self).__init__(self)
        if delegate is None:
            raise ValueError('delegate must not be None')
        self._delegate = delegate

    def __new__(cls, delegate, *args, **kwargs):
        """Constructs a Delegator instance.

        Actually, an instance of a dynamic type is returned, which is
        created in the DynamicDecorator's __new__ method.
        This method is necessary, because the delegate should not be
        passed to the DynamicDecorator's __new__ method.

        """
        return super(Delegator, cls).__new__(cls, *args, **kwargs)

    def __getattr__(self, key):
        return getattr(self._delegate, key)

    def __setattr__(self, key, val):
        def _hasattr(key):
            exists = True
            try:
                super(Delegator, self).__getattribute__(key)
            except AttributeError:
                exists = False
            return exists

        # as long as the _delegate was not set, all attributes
        # are added to the delegator instance (instead of the delegate);
        # once the _delegate is set, our own attributes can still be
        # manipulated (see also the testcases)
        if not _hasattr('_delegate') or _hasattr(key):
            super(Delegator, self).__setattr__(key, val)
        else:
            setattr(self._delegate, key, val)


class StringifiedDelegator(Delegator, unicode):
    """Represents a delegator that can be treated like a str."""

    def __new__(cls, delegate, *args, **kwargs):
        """Constructs a new StringifiedDelegator instance."""
        return super(StringifiedDelegator, cls).__new__(
            cls, delegate, str(delegate), *args, **kwargs
        )
