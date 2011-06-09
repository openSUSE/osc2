import logging

from lxml import etree
from lxml import objectify

from osc.core import Osc

class AddElement(object):
    """Adds a new element called "tag" to the provided "element"

    Note: it tries to add the new element next to existing elements
    (if they exists). Otherwise it's simply appended to "element".

    """

    def __init__(self, element, tag):
        """Constructs a new AddElement object.

        "element" is the element to which we will add a new element
        which is called "tag".

        """
        self._element = element
        self._tag = tag

    def _add_data(self, data, attribs):
        data_elm = objectify.DataElement(data)
        target_elm = self._element.makeelement(self._tag, **attribs)
        existing = self._element.findall(self._tag)
        if existing:
            # add it next to the latest element
            existing[-1].addnext(target_elm)
        else:
            self._element.append(target_elm)
        # this is everything but thread-safe (OTOH it's highly unlikely
        # that the same model is shared (and modified) between threads)
        getattr(self._element, self._tag).__setitem__(len(existing), data_elm)
        return data_elm

    def _add_tree(self, attribs):
        elm = self._element.makeelement(self._tag, **attribs)
        existing = self._element.findall(self._tag)
        if existing:
            # add it next to the latest element
            existing[-1].addnext(elm)
        else:
            self._element.append(elm)
        return elm

    def __call__(self, *args, **kwargs):
        """Add the new element"""
        if not args:
            return self._add_tree(kwargs)
        return self._add_data(args[0], kwargs)


class OscElement(objectify.ObjectifiedElement):
    """Base class for all osc elements.

    This class overrides __getattr__ in order to return our special
    method object if name matches the pattern: add_tagname.
    In this case an instance is return which adds a new element
    "tagname" to _this_ element.

    """
    def __getattr__(self, name):
        data = name.split('_', 1)
        if len(data) == 1 or not data[0] == 'add':
            return super(OscElement, self).__getattr__(name)
        add = AddElement(self, data[1])
        return add

class ReadOnlyModelError(Exception):
    """Exception raised if a readonly model is going to be stored"""
    pass

class RemoteModel(object):
    """Base class for all remote models"""

    def __init__(self, tag='', xml_data='', schema='', store_schema='',
                 **kwargs):
        """Creates a new remote model object.

        Keyword arguments:
        tag -- root tag for this model (default: '')
        xml_data -- xml string which represents this model (default: '')
        schema -- path to schema for this model (default: '')
        store_schema -- path to the schema file which is used to validate the
                        response after storing the xml (default: '')
        kwargs -- attributes for the root tag

        Note: if tag _and_ xml_data is specified, tag is ignored

        """
        super(RemoteModel, self).__init__()
        self._schema = schema
        self._store_schema = store_schema
        self._logger = logging.getLogger(__name__)
#        if tag and xml_data:
#            raise ValueError("Either specificy tag or xml_data but not both")
        if xml_data:
            parser = self._get_parser()
            self._xml = objectify.fromstring(xml_data, parser=parser)
        elif tag:
            self._xml = self._get_parser().makeelement(tag, **kwargs)
        else:
            raise ValueError("Either tag or xml_data is required")

    def _get_parser(self):
        """Returns a parser object which is configured with OscElement as the
        default tree_class.

        """
        parser = objectify.makeparser()
        lookup = objectify.ObjectifyElementClassLookup(tree_class=OscElement)
        parser.set_element_class_lookup(lookup)
        return parser

    def __getattr__(self, name):
        return getattr(self._xml, name)

    def __setattr__(self, name, value):
        if name.startswith('_'):
            self.__dict__[name] = value
            return value
        return setattr(self._xml, name, value)

    def __delattr__(self, name):
        if name.startswith('_'):
            return delattr(self.__dict__, name)
        return delattr(self._xml, name)

    def tostring(self):
        """Returns object as xml string"""
        objectify.deannotate(self._xml)
        etree.cleanup_namespaces(self._xml)
        return etree.tostring(self._xml, pretty_print=True)

    # XXX: should we introduce a custom exception if validation fails?
    def validate(self):
        """Validates xml against a schema.

        If validation is disabled, False is returned.
        If validation succeeds True is returned.
        If validation fails an exception is raised (etree.DocumentInvalid)

        """
        if not self._schema or not self.validate:
            return False
        self._logger.debug("validate modle against schema: %s", self._schema)
        if self._schema.endswith('.rng'):
            schema = etree.RelaxNG(file=self._schema)
        elif self._schema.endswith('.xsd'):
            schema = etree.XMLSchema(file=self._schema)
        else:
            raise ValueError('unsupported schema file')
        schema.assertValid(self._xml)
        return True

    def store(self, path, method='PUT', **kwargs):
        """Store the xml to the server.

        Keyword arguments:
        path -- the url path (default: '')
        method -- the http method (default: 'PUT')
        kwargs -- parameters for the http request (like query parameters,
                  post data etc.)

        """
        self.validate()
        request = Osc.get_osc().get_reqobj()
        http_method = RemoteModel._get_http_method(request, method)
        if not 'data' in kwargs:
            kwargs['data'] = self.tostring()
        if not 'schema' in kwargs:
            kwargs['schema'] = self._store_schema
        http_method(path, **kwargs)

    @classmethod
    def get_object(cls, path, method='GET', **kwargs):
        """Get the remote model from the server.

        Keyword arguments:
        path -- the url path (default: '')
        method -- the http method (default: 'GET')
        kwargs -- parameters for the http request (like query parameters,
                  schema etc.)

        """
        request = Osc.get_osc().get_reqobj()
        http_method = RemoteModel._get_http_method(request, method)
        xml_data = http_method(path, **kwargs).read()
        return cls(xml_data=xml_data)

    @staticmethod
    def _get_http_method(request_obj, method):
        """Get the requested http method from the http object (internal)"""
        meth = getattr(request_obj, method.lower(), None)
        if meth is None:
            msg = "http request object doesn't support method: %s" % method
            raise ValueError(msg)
        return meth


class RemoteProject(RemoteModel):
    PATH = '/source/%(project)s/_meta'
    SCHEMA = ''
    PUT_RESPONSE_SCHEMA = ''

    def __init__(self, name='', **kwargs):
        super(RemoteProject, self).__init__(tag='project', name=name,
                                            schema=RemoteProject.SCHEMA,
                                            **kwargs)

    @classmethod
    def get_object(cls, project, **kwargs):
        path = RemoteProject.PATH % {'project': project}
        if not 'schema' in kwargs:
            kwargs['schema'] = RemoteProject.SCHEMA
        return super(RemoteProject, cls).get_object(path, **kwargs)

    def store(self, **kwargs):
        path = RemoteProject.PATH % {'project': self.get('name')}
        if not 'schema' in kwargs:
            kwargs['schema'] = RemoteProject.PUT_RESPONSE_SCHEMA
        return super(RemoteProject, self).store(path, method='PUT', **kwargs)


class RemotePackage(RemoteModel):
    PATH = '/source/%(project)s/%(package)s/_meta'
    SCHEMA = ''
    PUT_RESPONSE_SCHEMA = ''

    def __init__(self, project='', name='', **kwargs):
        # project is not required
        if project:
            kwargs['project'] = project
        super(RemotePackage, self).__init__(tag='package', name=name,
                                            schema=RemotePackage.SCHEMA,
                                            **kwargs)

    @classmethod
    def get_object(cls, project, package, **kwargs):
        path = RemotePackage.PATH % {'project': project, 'package': package}
        if not 'schema' in kwargs:
            kwargs['schema'] = RemotePackage.SCHEMA
        return super(RemotePackage, cls).get_object(path, **kwargs)

    def store(self, **kwargs):
        path = RemotePackage.PATH % {'project': self.get('project'),
                                     'package': self.get('name')}
        if not 'schema' in kwargs:
            kwargs['schema'] = RemotePackage.PUT_RESPONSE_SCHEMA
        return super(RemotePackage, self).store(path, method='PUT', **kwargs)