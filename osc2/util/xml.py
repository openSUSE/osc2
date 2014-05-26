"""xml utility functions"""

from collections import Sequence

from lxml import etree, objectify

__all__ = ['ElementClassLookup', 'get_parser']


class XPathFindMixin:
    """Mixes find and findall methods in that support an xpath.

    This is an old-style class to avoid issues when inheriting
    from this class and ObjectifiedElement, which in turn
    inherits from ElementBase, whose __init__ must not be
    overriden by subclasses (see comment in lxml/classlookup.pxi).

    """

    def find(self, xp):
        elms = self.findall(xp)
        if isinstance(elms, Sequence):
            if elms:
                return elms[0]
            return None
        # happens if, for example, xp == '2 + 3' (see testcases)
        return elms

    def findall(self, xp):
        return self.xpath(xp)


class OscElement(XPathFindMixin, objectify.ObjectifiedElement):
    """Base class for xml elements."""
    pass


class OscStringElement(XPathFindMixin, objectify.StringElement):
    """Base class for all data elements of type string."""
    pass


class ElementClassLookup(etree.PythonElementClassLookup):
    """Element lookup class"""

    def __init__(self, tree_class=None, empty_data_class=None, **tag_class):
        if tree_class is None:
            tree_class = OscElement
        if empty_data_class is None:
            empty_data_class = OscStringElement
        fallback = objectify.ObjectifyElementClassLookup(
            tree_class=tree_class,
            empty_data_class=empty_data_class)
        super(ElementClassLookup, self).__init__(fallback=fallback)
        self._tag_class = tag_class

    def lookup(self, doc, root):
        klass = self._tag_class.get(root.tag)
        if klass is not None:
            return klass
        # use StringElement if we have text and no children
        if root.text and not root:
            return OscStringElement
        return None


def get_parser(tree_class=None, empty_data_class=None,
               lookup_class=ElementClassLookup, **tag_class):
    """Returns an objectify parser object.

    tag_class is a "tag" => "klass" mapping. If a xml is parsed
    with this parser the tag "tag" will be represented by an instance
    of class "klass".

    Keyword arguments:
    tree_class -- class which is used for tree elements (default: None)
    empty_data_class -- class which is used for empty data elements
                        (default: None)
    lookup_class -- class which is used for the element lookup
                    (default: ElementClassLookup)

    """
    parser = objectify.makeparser()
    lookup = lookup_class(tree_class, empty_data_class, **tag_class)
    parser.set_element_class_lookup(lookup)
    return parser


def fromstring(data, parser=None, **kwargs):
    """Parse a string into a xml objectify object.

    data is the xml string.

    Keyword arguments:
    parser -- parser which should be used for parsing; if specified
              all other keyword arguments are ignored (default: None)
    see get_parser() for keyword arguments

    """
    if parser is None:
        parser = get_parser(**kwargs)
    return objectify.fromstring(data, parser=parser)
