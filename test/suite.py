import sys
import unittest

import test_httprequest
import test_remote
import test_build

suite = unittest.TestSuite()
suite.addTests(test_httprequest.suite())
suite.addTests(test_remote.suite())
suite.addTests(test_build.suite())
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(not result.wasSuccessful())
