import unittest
from collections import Sequence

from osc2.util.xml import fromstring
from test.osctest import OscTestCase


def suite():
    return unittest.makeSuite(TestXML)


class TestXML(OscTestCase):
    def setUp(self):
        self.xml = fromstring(
            """
            <root>
              <foo>
                <bar name="xyz">
                  <foo/>
                </bar>
                <bar/>
                <bar/>
              </foo>
              <foo/>
            </root>
            """
        )

    def test_find(self):
        """Find single element (child)"""
        elm = self.xml.find('foo')
        self.assertIsNotNone(elm)
        self.assertFalse(isinstance(elm, Sequence))

    def test_find_xpath(self):
        """Find single element using xpath"""
        elm = self.xml.find('//bar')
        self.assertIsNotNone(elm)
        self.assertFalse(isinstance(elm, Sequence))
        self.assertEqual(elm.get('name'), 'xyz')

    def test_find_result_xpath(self):
        """Call find with an xpath expr on the result returned by find"""
        elm = self.xml.find('//bar')
        self.assertIsNotNone(elm)
        elm = elm.find('//foo')
        self.assertIsNotNone(elm)

    def test_find_nonexistent(self):
        """Try to find a nonexistent element"""
        elm = self.xml.find('nonexistent')
        self.assertIsNone(elm)

    def test_find_arbitrary_xpath(self):
        """Find also takes an aribtrary xpath"""
        # this usage is discouraged, find should only
        # be used to return an element
        data = self.xml.find('2 + 3')
        self.assertEqual(data, 5.0)

    def test_findall(self):
        """Test findall"""
        elms = self.xml.findall('foo')
        self.assertTrue(isinstance(elms, Sequence))
        self.assertEqual(len(elms), 2)

    def test_findall_xpath(self):
        """Test findall with xpath"""
        elms = self.xml.findall('//bar')
        self.assertTrue(isinstance(elms, Sequence))
        self.assertEqual(len(elms), 3)

    def test_findall_nonexistent(self):
        """Test findall with nonexistent element"""
        elms = self.xml.findall('nonexistent')
        self.assertTrue(isinstance(elms, Sequence))
        self.assertEqual(len(elms), 0)

    def test_findall_arbitrary_xpath(self):
        """findall also takes an aribtrary xpath"""
        # this usage is discouraged, findall should only
        # be used to return a list of elements
        data = self.xml.findall('2 + 3')
        self.assertEqual(data, 5.0)

    def test_iterfind(self):
        """iterfind is not overriden (the default does not support an xpath)"""
        self.assertRaises(SyntaxError, self.xml.iterfind, '//foo')

if __name__ == '__main__':
    unittest.main()
