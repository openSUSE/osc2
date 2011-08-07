import os

from test.httptest import MockUrllib2Request
from osc.core import Osc

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
