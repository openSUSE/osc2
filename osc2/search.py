"""This module provides classes to search in the obs.

Currently only the search for requests is supported.

"""

from lxml import etree

from osc2.remote import Request
from osc2.util.xml import fromstring, OscElement
from osc2.core import Osc


class RequestCollection(OscElement):
    """Contains the request search results.

    All request objects are read only. In order to "work"
    with the request objects (except reading) a call to
    the Request's real_obj method is required.

    """
    SCHEMA = ''

    def __iter__(self):
        for r in self.iterfind('request'):
            yield r.real_obj()


class RORequest(OscElement):
    """Represents a read only request.

    This kind of request object is usually used in a collection.

    """

    def real_obj(self):
        """Returns a "real" Request object.

        The returned object is "writable" too that is
        its state can be changed etc.

        """
        return Request(xml_data=etree.tostring(self))


def _find(path, xp, tag_class={}, **kwargs):
    """Returns a Collection with objects which match the xpath.

    path is the remote path which is used for the http request.
    xp is the xpath which is used for the search (either an
    Expression object or a string).

    Keyword arguments:
    tag_class -- a dict which maps tag names to classes
                 (see util.xml.fromstring for the details)
                 (default: {})
    **kwargs -- optional parameters for the http request

    """
    request = Osc.get_osc().get_reqobj()
    xpath = xp
    if hasattr(xp, 'tostring'):
        xpath = xp.tostring()
    f = request.get(path, match=xpath, **kwargs)
    return fromstring(f.read(), **tag_class)


def find_request(xp, **kwargs):
    """Returns a RequestCollection with objects which match the xpath.

    xp is the xpath which is used for the search (either an
    Expression object or a string).

    Keyword arguments:
    **kwargs -- optional parameters for the http request

    """
    path = '/search/request'
    if 'schema' not in kwargs:
        kwargs['schema'] = RequestCollection.SCHEMA
    tag_class = {'collection': RequestCollection, 'request': RORequest}
    return _find(path, xp, tag_class, **kwargs)
