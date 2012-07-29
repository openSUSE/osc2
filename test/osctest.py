import os
import sys

from test.httptest import MockUrllib2Request
from osc.core import Osc


# copied from unittest/case.py (python 2.7)
class _AssertRaisesContext(object):
    """A context manager used to implement TestCase.assertRaises* methods."""

    def __init__(self, expected, test_case, expected_regexp=None):
        self.expected = expected
        self.failureException = test_case.failureException
        self.expected_regexp = expected_regexp

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is None:
            try:
                exc_name = self.expected.__name__
            except AttributeError:
                exc_name = str(self.expected)
            raise self.failureException(
                "{0} not raised".format(exc_name))
        if not issubclass(exc_type, self.expected):
            # let unexpected exceptions pass through
            return False
        self.exception = exc_value # store for later retrieval
        if self.expected_regexp is None:
            return True

        expected_regexp = self.expected_regexp
        if isinstance(expected_regexp, basestring):
            expected_regexp = re.compile(expected_regexp)
        if not expected_regexp.search(str(exc_value)):
            raise self.failureException('"%s" does not match "%s"' %
                     (expected_regexp.pattern, str(exc_value)))
        return True


class OscTest(MockUrllib2Request):
    """Base class for all osc related testcases.

    Sets up core.Osc class to use a dummy request object.

    """
    def __init__(self, *args, **kwargs):
        self.apiurl = kwargs.pop('apiurl', 'http://localhost')
        super(OscTest, self).__init__(*args, **kwargs)

    def setUp(self):
        super(OscTest, self).setUp()
        Osc.init(self.apiurl, validate=True)

    def assertIsNotNone(self, x):
        if hasattr(super(OscTest, self), 'assertIsNotNone'):
            return super(OscTest, self).assertIsNotNone(x)
        return self.assertTrue(x is not None)

    def assertIsNone(self, x):
        if hasattr(super(OscTest, self), 'assertIsNone'):
            return super(OscTest, self).assertIsNone(x)
        return self.assertTrue(x is None)

    def assertEqualFile(self, x, filename, mode='r'):
        with open(self.fixture_file(filename), mode) as f:
            return self.assertEqual(x, f.read())

    def _exists(self, path, *filenames, **kwargs):
        store = kwargs.get('store', False)
        data = kwargs.get('data', False)
        if store and data:
            raise ValueError('store and data are mutually exclusive')
        filename = os.path.join(*filenames)
        fname = os.path.join(path, filename)
        if store:
            fname = os.path.join(path, '.osc', filename)
        elif data:
            fname = os.path.join(path, '.osc', 'data', filename)
        self.assertTrue(os.path.exists(fname))

    def _not_exists(self, path, *filenames, **kwargs):
        self.assertRaises(AssertionError, self._exists, path, *filenames,
                          **kwargs)

    def assertRaises(self, excClass, callableObj=None, *args, **kwargs):
        """Overriden in order to provide backward compatibility.

        With python < 2.7 it is not possible to use this as a context
        manager.

        """
        if sys.version_info >= (2, 7):
            return super(OscTest, self).assertRaises(excClass, callableObj,
                                                     *args, **kwargs)
        # backport ability to use this method as a context manager
        # copied code from unittest/case.py (python 2.7)
        context = _AssertRaisesContext(excClass, self)
        if callableObj is None:
            return context
        with context:
            callableObj(*args, **kwargs)
