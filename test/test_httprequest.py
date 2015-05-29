import unittest
import urllib2

from lxml import etree

from test.osctest import OscTest
from osc2.httprequest import Urllib2HTTPRequest, HTTPError
from test.httptest import GET, PUT, POST, DELETE


def suite():
    return unittest.makeSuite(TestHTTPRequest)


class TestHTTPRequest(OscTest):
    def __init__(self, *args, **kwargs):
        kwargs['fixtures_dir'] = 'test_httprequest_fixtures'
        super(TestHTTPRequest, self).__init__(*args, **kwargs)

    def read_file(self, filename):
        return open(self.fixture_file(filename), 'r').read()

    @GET('http://localhost/source', text='foobar',
         exp_headers={'Authorization': None})
    def test_1(self):
        """simple get"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.get('/source')
        self.assertEqual(resp.read(), 'foobar')
        self.assertIsNone(resp._sio)

    @GET('http://localhost/source/server%3Amail?esc=foo%26bar&foo=bar',
         text='foobar')
    def test2(self):
        """simple get with query"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.get('/source/server:mail', foo='bar', esc='foo&bar')
        self.assertEqual(resp.read(), 'foobar')
        self.assertIsNone(resp._sio)

    @GET('http://localhost/source', file='prj_list.xml')
    def test3(self):
        """simple get with response validation"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.get('/source', schema=self.fixture_file('directory.xsd'))
        self.assertEqual(resp.read(), self.read_file('prj_list.xml'))
        self.assertIsNotNone(resp._sio)

    @GET('http://localhost/source', text='<foo />')
    def test4(self):
        """simple get with response validation (validation fails)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        self.assertRaises(etree.DocumentInvalid, r.get, '/source',
                          schema=self.fixture_file('directory.xsd'))

    @PUT('http://localhost/source/foo/bar/file', exp='this is a test',
         text='ok')
    def test5(self):
        """simple put"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.put('/source/foo/bar/file', data='this is a test')
        self.assertEqual(resp.read(), 'ok')
        self.assertIsNone(resp._sio)

    @PUT('http://localhost/source/foo/bar/file?foo=bar&x=foo+bar',
         expfile='putfile', text='ok',
         exp_content_type='application/octet-stream')
    def test6(self):
        """simple put (filename, uses mmap)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '',
                               False, True, 20)
        resp = r.put('/source/foo/bar/file',
                     filename=self.fixture_file('putfile'),
                     x='foo bar', foo='bar')
        self.assertEqual(resp.read(), 'ok')
        self.assertIsNone(resp._sio)

    @POST('http://localhost/dummy', exp='simple+text', text='ok',
          exp_content_type='application/x-www-form-urlencoded')
    def test7(self):
        """simple post (urlencoded data)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.post('/dummy', data='simple text', urlencoded=True)
        self.assertEqual(resp.read(), 'ok')
        self.assertIsNone(resp._sio)

    @POST('http://localhost/source/foo/bar/file?foo=bar&x=foo+bar',
          expfile='putfile', file='prj_list.xml',
          exp_content_type='application/octet-stream')
    def test8(self):
        """simple post (filename, uses mmap) - validate response"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '',
                               False, True, 20)
        resp = r.post('/source/foo/bar/file',
                      filename=self.fixture_file('putfile'),
                      schema=self.fixture_file('directory.xsd'),
                      x='foo bar', foo='bar')
        self.assertEqual(resp.read(), self.read_file('prj_list.xml'))
        self.assertIsNotNone(resp._sio)

    @POST('http://localhost/source/foo/bar/file?foo=bar&x=foo+bar',
          expfile='putfile', text='<somexml />',
          exp_content_type='application/octet-stream')
    def test9(self):
        """simple post (filename, uses mmap) - validation fails"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '',
                               False, True, 20)
        self.assertRaises(etree.DocumentInvalid, r.post,
                          '/source/foo/bar/file',
                          filename=self.fixture_file('putfile'),
                          schema=self.fixture_file('directory.xsd'),
                          x='foo bar', foo='bar')

    @DELETE('http://localhost/source/project', text='foobar')
    def test10(self):
        """simple delete"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.delete('/source/project')
        self.assertEqual(resp.read(), 'foobar')
        self.assertIsNone(resp._sio)

    @GET('http://localhost/source', text='foobar', header1='foo', x='42')
    def test11(self):
        """test response object"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.get('source')
        self.assertEqual(resp.url, 'http://localhost/source')
        self.assertEqual(resp.code, 200)
        self.assertEqual(resp.headers.get('header1'), 'foo')
        self.assertEqual(resp.headers['x'], '42')

    @GET('http://localhost/source',
         exception=urllib2.HTTPError('http://localhost/source', 403, 'error',
                                     {}, None))
    def test12(self):
        """test exception handling (get)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        self.assertRaises(HTTPError, r.get, 'source')

    @PUT('http://localhost/source', exp='foo bar',
         exception=urllib2.HTTPError('http://localhost/source', 400, 'error',
                                     {}, None))
    def test13(self):
        """test exception handling (put)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        self.assertRaises(HTTPError, r.put, 'source', data='foo bar')

    @GET('http://localhost/source',
         exception=urllib2.HTTPError('http://localhost/source', 403, 'error',
                                     {'foo': 'bar'}, None))
    def test14(self):
        """test exception handling (check exception object)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        with self.assertRaises(HTTPError) as cm:
            r.get('/source')
        self.assertEqual(cm.exception.url, 'http://localhost/source')
        self.assertEqual(cm.exception.code, 403)
        self.assertEqual(cm.exception.headers['foo'], 'bar')
        self.assertIsNotNone(cm.exception.orig_exc)

    @GET('http://apiurl/source', text='foobar')
    def test15(self):
        """test optional apiurl (GET)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.get('/source', apiurl='http://apiurl')
        self.assertEqual(resp.read(), 'foobar')

    @DELETE('http://api/source', text='foobar')
    def test16(self):
        """test optional apiurl (DELETE)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.delete('/source', apiurl='http://api')
        self.assertEqual(resp.read(), 'foobar')

    @POST('http://apiurl/source', exp='foo', text='foobar')
    def test17(self):
        """test optional apiurl (POST)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.post('/source', data='foo', apiurl='http://apiurl')
        self.assertEqual(resp.read(), 'foobar')

    @PUT('http://url/source', exp='foo', text='foobar')
    def test18(self):
        """test optional apiurl (PUT)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.put('/source', data='foo', apiurl='http://url')
        self.assertEqual(resp.read(), 'foobar')

    @PUT('http://localhost/source/prj/_meta', exp='<xml/>', text='foobar',
         exp_content_type='application/xml')
    def test19(self):
        """test content type (PUT)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.put('/source/prj/_meta', data='<xml/>',
                     content_type='application/xml')
        self.assertEqual(resp.read(), 'foobar')

    @PUT('http://localhost/source', exp='asdf', text='foobar',
         exp_content_type='foo')
    def test20(self):
        """test content type (POST)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.put('/source', data='asdf', content_type='foo')
        self.assertEqual(resp.read(), 'foobar')

    def test21(self):
        """test content type and urlencoded (POST)"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        self.assertRaises(ValueError, r.post, '/source', data='bar',
                          content_type='foo', urlencoded=True)

    @GET('http://localhost/test?binary=foo&binary=bar&binary=foobar&other=ok',
         text='foobar')
    def test22(self):
        """test use same query parameter more than once"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.get('/test', binary=['foo', 'bar', 'foobar'], other='ok')
        self.assertEqual(resp.read(), 'foobar')

    @GET('http://localhost/test?binary=foo&test=4', text='foo')
    def test23(self):
        """test ignore empty query keys"""
        r = Urllib2HTTPRequest('http://localhost', True, '', '', '', False)
        resp = r.get('/test', binary=['', 'foo'], test='4', x='', y=None,
                     z=[''], a=['', None])
        self.assertEqual(resp.read(), 'foo')

    @GET('http://localhost/test', text='foo',
         exp_headers={'Authorization': 'Basic Zm9vOmJhcg=='})
    def test_basic_auth_handler1(self):
        """test the default basic auth handler"""
        r = Urllib2HTTPRequest('http://localhost', username='foo',
                               password='bar')
        resp = r.get('/test')
        self.assertEqual(resp.read(), 'foo')

    @GET('http://localhost/test', text='foo', code=401,
         exp_headers={'Authorization': 'Basic Zm9vOmJhcg=='},
         www_authenticate='Basic realm="foo bar"')
    def test_basic_auth_handler2(self):
        """test the default basic auth handler (wrong creds)"""
        r = Urllib2HTTPRequest('http://localhost', username='foo',
                               password='bar')
        self.assertRaises(HTTPError, r.get, '/test')

    @GET('http://api.opensuse.org/source', text='foo',
         exp_headers={'Authorization': 'Basic Zm9vOmJhcg==',
                      'Cookie': 'openSUSE_session=xyz'})
    def test_basic_auth_handler3(self):
        """always send credentials (even if a cookie is used)"""
        r = Urllib2HTTPRequest('http://api.opensuse.org', username='foo',
                               password='bar',
                               cookie_filename=self.fixture_file('cookie'))
        resp = r.get('/source')
        self.assertEqual(resp.read(), 'foo')

    @GET('http://api.opensuse.org/source', text='foo',
         exp_headers={'Authorization': None})
    def test_basic_auth_handler4(self):
        """do not send credentials to an arbitrary host"""
        r = Urllib2HTTPRequest('http://localhost', username='foo',
                               password='bar')
        resp = r.get('/source', apiurl='http://api.opensuse.org')
        self.assertEqual(resp.read(), 'foo')

    @GET('http://localhost/test', text='', code=302,
         exp_headers={'Authorization': 'Basic Zm9vOmJhcg=='},
         location='http://example.com/foobar/test')
    @GET('http://example.com/foobar/test', text='foo',
         exp_headers={'Authorization': None})
    def test_basic_auth_handler5(self):
        """do not send credentials to an arbitrary redirect location"""
        r = Urllib2HTTPRequest('http://localhost', username='foo',
                               password='bar')
        resp = r.get('/test')
        self.assertEqual(resp.read(), 'foo')

    @GET('http://localhost/test', text='', code=302,
         exp_headers={'Authorization': 'Basic Zm9vOmJhcg=='},
         location='https://localhost/foobar/test')
    @GET('https://localhost/foobar/test', text='foo',
         exp_headers={'Authorization': 'Basic Zm9vOmJhcg=='})
    def test_basic_auth_handler6(self):
        """send credentials, if the redirect location's host did not change"""
        r = Urllib2HTTPRequest('http://localhost', username='foo',
                               password='bar')
        resp = r.get('/test')
        self.assertEqual(resp.read(), 'foo')

    @GET('https://localhost/test', text='foo',
         exp_headers={'Authorization': 'Basic Zm9vOmJhcg=='})
    def test_basic_auth_handler7(self):
        """test a https request"""
        r = Urllib2HTTPRequest('https://localhost', username='foo',
                               password='bar')
        resp = r.get('/test')
        self.assertEqual(resp.read(), 'foo')

    @staticmethod
    def _setup_ext_basic_auth_handler(url, username, password):
        authhandler = urllib2.HTTPBasicAuthHandler(
            urllib2.HTTPPasswordMgrWithDefaultRealm())
        authhandler.add_password(None, url, username, password)
        return authhandler

    @GET('http://localhost/test', text='', code=401,
         www_authenticate='Basic realm="foo bar"')
    @GET('http://localhost/test', text='foo',
         exp_headers={'Authorization': 'Basic Zm9vOmJhcg=='})
    def test_external_basic_auth_handler1(self):
        """test external basic auth handler"""
        handler = self._setup_ext_basic_auth_handler('http://localhost',
                                                     'foo', 'bar')
        r = Urllib2HTTPRequest('http://localhost', handlers=[handler])
        resp = r.get('/test')
        self.assertEqual(resp.read(), 'foo')

    @GET('http://localhost/test', text='', code=401,
         exp_headers={'Authorization': 'Basic Zm9vOmJhcg=='},
         www_authenticate='Basic realm="foo bar"')
    @GET('http://localhost/test', text='foo',
         exp_headers={'Authorization': 'Basic Zm9vOmZvb2Jhcg=='})
    def test_external_basic_auth_handler2(self):
        """test external + default basic auth handler (pathological case)"""
        # the default basic auth handler does not override an existing
        # Authorization header
        handler = self._setup_ext_basic_auth_handler('http://localhost',
                                                     'foo', 'foobar')
        r = Urllib2HTTPRequest('http://localhost', username='foo',
                               password='bar', handlers=[handler])
        resp = r.get('/test')
        self.assertEqual(resp.read(), 'foo')

if __name__ == '__main__':
    unittest.main()
