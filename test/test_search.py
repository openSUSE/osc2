import unittest

from lxml import etree

from osc2.search import find_request, RequestCollection
from osc2.util.xpath import XPathBuilder
from test.osctest import OscTest
from test.httptest import GET


def suite():
    return unittest.makeSuite(TestSearch)


class TestSearch(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = 'test_search_fixtures'
        super(TestSearch, self).__init__(*args, **kwargs)

    def tearDown(self):
        super(TestSearch, self).tearDown()
        RequestCollection.SCHEMA = ''

    @GET(('http://localhost/search/request?match='
          '%2Fstate%5B%40name+%3D+%22new%22+or+%40name+%3D+%22review%22%5D'
          '+and+%28%2Faction%2Ftarget%5B%40project+%3D+%22prj%22%5D'
          '+or+%2Faction%2Fsource%5B%40project+%3D+%22prj%22%5D%29'),
         file='collection_request1.xml')
    def test_request1(self):
        """test find_request"""
        xpb = XPathBuilder()
        xp = xpb.state[(xpb.attr('name') == 'new')
                       | (xpb.attr('name') == 'review')]
        xp = xp & (xpb.action.target[xpb.attr('project') == 'prj']
                   | xpb.action.source[xpb.attr('project') == 'prj']
                  ).parenthesize()
        collection = find_request(xp)
        self.assertTrue(len(collection.request[:]) == 3)
        self.assertEqual(collection.request[0].get('id'), '1')
        self.assertEqual(collection.request[0].action.source.get('project'),
                         'foo')
        self.assertEqual(collection.request[1].get('id'), '42')
        self.assertEqual(collection.request[1].action.get('type'), 'submit')
        self.assertEqual(collection.request[2].get('id'), '108')
        self.assertEqual(collection.request[2].review[2].get('by_group'),
                         'autobuild-team')
        # test __iter__ method of the collection
        ids = ['1', '42', '108']
        for r in collection:
            self.assertEqual(r.get('id'), ids.pop(0))
        self.assertTrue(len(ids) == 0)

    @GET(('http://localhost/search/request?match='
          '%2Fstate%5B%40name+%3D+%22new%22%5D'),
         file='collection_request2.xml')
    def test_request2(self):
        """test find_request (with validation)"""
        RequestCollection.SCHEMA = self.fixture_file('collection_request.xsd')
        xpb = XPathBuilder()
        xp = xpb.state[xpb.attr('name') == 'new']
        collection = find_request(xp)
        self.assertTrue(len(collection.request[:]) == 1)
        self.assertEqual(collection.get('matches'), '1')
        self.assertEqual(collection.request[0].action.get('type'), 'submit')
        self.assertEqual(collection.request.action.get('type'), 'submit')

    @GET(('http://localhost/search/request?match='
          '%2Fstate%5B%40name+%3D+%22new%22%5D'),
         file='collection_request2.xml')
    def test_request3(self):
        """test find_request (xpath as string)"""
        xpath = '/state[@name = "new"]'
        collection = find_request(xpath)
        self.assertTrue(len(collection.request[:]) == 1)
        self.assertEqual(collection.get('matches'), '1')
        self.assertEqual(collection.request[0].action.get('type'), 'submit')

    @GET(('http://localhost/search/request?match='
          '%2Fstate%5B%40name+%3D+%22declined%22%5D'),
         text='<collection matches="1"><foo /></collection>')
    def test_request4(self):
        """test find_request (validation fails)"""
        RequestCollection.SCHEMA = self.fixture_file('collection_request.xsd')
        xpb = XPathBuilder()
        xp = xpb.state[xpb.attr('name') == 'declined']
        self.assertRaises(etree.DocumentInvalid, find_request, xp)

if __name__ == '__main__':
    unittest.main()
