import sys
import unittest

from test import test_httprequest
from test import test_remote
from test import test_build
from test import test_source
from test import test_oscargs
from test import test_builder
from test import test_fetch
from test import test_search
from test.wc import test_util
from test.wc import test_project
from test.wc import test_package
from test.wc import test_convert
from test.util import test_xpath
from test.util import test_cpio


def additional_tests():
    suite = unittest.TestSuite()
    suite.addTests(test_httprequest.suite())
    suite.addTests(test_remote.suite())
    suite.addTests(test_build.suite())
    suite.addTests(test_source.suite())
    suite.addTests(test_oscargs.suite())
    suite.addTests(test_builder.suite())
    suite.addTests(test_fetch.suite())
    suite.addTests(test_search.suite())
    suite.addTests(test_util.suite())
    suite.addTests(test_project.suite())
    suite.addTests(test_package.suite())
    suite.addTests(test_convert.suite())
    suite.addTests(test_xpath.suite())
    suite.addTests(test_cpio.suite())
    return suite

if __name__ == '__main__':
    suite = additional_tests()
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    sys.exit(not result.wasSuccessful())
