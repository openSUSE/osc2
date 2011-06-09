from httptest import MockUrllib2Request
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
