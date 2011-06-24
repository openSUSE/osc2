import sys
import unittest

import test.test_httprequest
import test.test_remote
import test.test_build

suite = unittest.TestSuite()
suite.addTests(test.test_httprequest.suite())
suite.addTests(test.test_remote.suite())
suite.addTests(test.test_build.suite())
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(not result.wasSuccessful())
