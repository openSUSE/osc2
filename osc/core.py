from osc.httprequest import Urllib2HTTPRequest


# XXX: needs a bit more thinking... this will be the "global" place where
#      the library can be configured (like using a specific http object...)
class Osc(object):
    _osc = None

    def __init__(self, apiurl, username='', password='', request_object=None,
                 debug=False, validate=True):
        super(Osc, self).__init__()
        if username and request_object is not None:
            raise ValueError('either specify username or request_object')
        self.request_object = request_object
        if request_object is None:
            self.request_object = Urllib2HTTPRequest(apiurl,
                                                     username=username,
                                                     password=password,
                                                     validate=validate,
                                                     debug=debug)
        Osc._osc = self

    def get_reqobj(self):
        return self.request_object

    @staticmethod
    def init(*args, **kwargs):
        return Osc(*args, **kwargs)

    @staticmethod
    def get_osc():
        if Osc._osc is None:
            Osc._osc = Osc('https://api.opensuse.org')
        return Osc._osc
