import sys
import unittest

from test import test_httprequest
from test import test_remote
from test import test_build

suite = unittest.TestSuite()
suite.addTests(test_httprequest.suite())
suite.addTests(test_remote.suite())
suite.addTests(test_build.suite())
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(not result.wasSuccessful())
