import sys
import unittest

import test_httprequest
import test_remote

suite = unittest.TestSuite()
suite.addTests(test_httprequest.suite())
suite.addTests(test_remote.suite())
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(not result.wasSuccessful())
