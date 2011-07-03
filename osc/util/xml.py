"""xml utility functions"""

from lxml import etree, objectify

__all__ = ['ElementLookupClass', 'get_parser']

class ElementClassLookup(etree.PythonElementClassLookup):
    """Element lookup class"""

    def __init__(self, tree_class=None, empty_data_class=None, **tag_class):
        fallback = objectify.ObjectifyElementClassLookup(
            tree_class=tree_class,
            empty_data_class=empty_data_class)
        super(ElementClassLookup, self).__init__(fallback=fallback)
        self._tag_class = tag_class

    def lookup(self, doc, root):
        klass = self._tag_class.get(root.tag)
        if klass is not None:
            return klass
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
