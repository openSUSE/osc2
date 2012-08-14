"""Provides a base class from which all xml based remote models should
inherit.

Example usage:
 prj = RemoteProject.find('project_name')
 # add a new maintainer
 prj.add_person(userid='foobar', role='maintainer')
 # remove the first repository
 del prj.repository[0]
 # send changes back to the server
 prj.store()
"""

import logging
from tempfile import NamedTemporaryFile
import os
from cStringIO import StringIO

from lxml import etree, objectify

from osc.core import Osc
from osc.httprequest import HTTPError
from osc.util.xml import ElementClassLookup, get_parser, fromstring
from osc.util.io import copy_file, iter_read

__all__ = ['RemoteModel', 'RemoteProject', 'RemotePackage', 'Request',
           'RORemoteFile', 'RWRemoteFile']


def _get_http_method(request_obj, method):
    """Get the requested http method from the http object (internal)"""
    meth = getattr(request_obj, method.lower(), None)
    if meth is None:
        msg = "http request object doesn't support method: %s" % method
        raise ValueError(msg)
    return meth


class ElementFactory(object):
    """Adds a new element called "tag" to the provided "element"

    Note: it tries to add the new element next to existing elements
    (if they exists). Otherwise it's simply appended to "element".

    """

    def __init__(self, element, tag):
        """Constructs a new ElementFactory object.

        "element" is the element to which we will add a new element
        which is called "tag".

        """
        super(ElementFactory, self).__init__()
        self._element = element
        self._tag = tag

    def _attrib_filter(self, attribs):
        """Filter out attributes with value None.

        A filtered dict is returned.

        """
        # simply creating a new dict is not possible because
        # otherwise our testcases fail (we need an OrderedDict...)
        remove = [k for k, v in attribs.iteritems() if v is None]
        for k in remove:
            del attribs[k]

    def _add_data(self, data, attribs):
        data_elm = objectify.DataElement(data)
        self._attrib_filter(attribs)
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
        self._attrib_filter(attribs)
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
    In this case an instance is returned which adds a new element
    "tagname" to _this_ element.

    """
    def __getattr__(self, name):
        data = name.split('_', 1)
        if len(data) == 1 or not data[0] == 'add':
            return super(OscElement, self).__getattr__(name)
        factory = ElementFactory(self, data[1])
        return factory


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
            self._read_xml_data(xml_data)
        elif tag:
            self._xml = self._get_parser().makeelement(tag, **kwargs)
        else:
            raise ValueError("Either tag or xml_data is required")

    def _read_xml_data(self, xml_data):
        parser = self._get_parser()
        self._xml = fromstring(xml_data, parser=parser)

    def _get_parser(self):
        """Returns a parser object which is configured with OscElement as the
        default tree_class and uses a StringElement for all data elements.

        """
        return get_parser(tree_class=OscElement)

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
        if not self._schema:
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
        http_method = _get_http_method(request, method)
        if not 'data' in kwargs:
            kwargs['data'] = self.tostring()
        if not 'schema' in kwargs:
            kwargs['schema'] = self._store_schema
        kwargs['content_type'] = 'application/xml'
        return http_method(path, **kwargs)

    @classmethod
    def find(cls, path, method='GET', **kwargs):
        """Get the remote model from the server.

        path is the url path.

        Keyword arguments:
        method -- the http method (default: 'GET')
        kwargs -- parameters for the http request (like query parameters,
                  schema etc.)

        """
        request = Osc.get_osc().get_reqobj()
        http_method = _get_http_method(request, method)
        xml_data = http_method(path, **kwargs).read()
        return cls(xml_data=xml_data)

    @classmethod
    def exists(cls, *args, **kwargs):
        """Check if the remote resource exists.

        *args and **kwargs are the arguments.
        For details have a look at the subclass'
        find method.

        """
        try:
            cls.find(*args, **kwargs)
        except HTTPError as e:
            if e.code == 404:
                return False
            raise
        return True

    @classmethod
    def delete(cls, path, method='DELETE', **kwargs):
        """Delete a remote resource.

        path is the url path.
        Return True if the resource was successfully deleted.
        If the resource do not exist anymore (code 404) False
        is returned.

        Keyword arguments:
        method -- the http method (default: 'DELETE')
        kwargs -- parameters for the http request (like query parameters,
                  schema etc.)

        """
        request = Osc.get_osc().get_reqobj()
        http_method = _get_http_method(request, method)
        try:
            http_method(path, **kwargs).read()
        except HTTPError as e:
            if e.code == 404:
                return False
            raise
        return True


class RemoteProject(RemoteModel):
    PATH = '/source/%(project)s/_meta'
    DELETE_PATH = '/source/%(project)s'
    SCHEMA = ''
    # used to validate the response after the xml is stored
    PUT_RESPONSE_SCHEMA = ''

    def __init__(self, name='', **kwargs):
        store_schema = RemoteProject.PUT_RESPONSE_SCHEMA
        super(RemoteProject, self).__init__(tag='project', name=name,
                                            schema=RemoteProject.SCHEMA,
                                            store_schema=store_schema,
                                            **kwargs)

    @classmethod
    def find(cls, project, **kwargs):
        path = RemoteProject.PATH % {'project': project}
        if not 'schema' in kwargs:
            kwargs['schema'] = RemoteProject.SCHEMA
        return super(RemoteProject, cls).find(path, **kwargs)

    def store(self, **kwargs):
        path = RemoteProject.PATH % {'project': self.get('name')}
        return super(RemoteProject, self).store(path, method='PUT', **kwargs)

    @classmethod
    def delete(cls, project, **kwargs):
        path = RemoteProject.DELETE_PATH % {'project': project}
        return super(RemoteProject, cls).delete(path, **kwargs)


class RemotePackage(RemoteModel):
    PATH = '/source/%(project)s/%(package)s/_meta'
    DELETE_PATH = '/source/%(project)s/%(package)s'
    SCHEMA = ''
    # used to validate the response after the xml is stored
    PUT_RESPONSE_SCHEMA = ''

    def __init__(self, project='', name='', **kwargs):
        # project is not required
        if project:
            kwargs['project'] = project
        store_schema = RemotePackage.PUT_RESPONSE_SCHEMA
        super(RemotePackage, self).__init__(tag='package', name=name,
                                            schema=RemotePackage.SCHEMA,
                                            store_schema=store_schema,
                                            **kwargs)

    @classmethod
    def find(cls, project, package, **kwargs):
        path = RemotePackage.PATH % {'project': project, 'package': package}
        if not 'schema' in kwargs:
            kwargs['schema'] = RemotePackage.SCHEMA
        return super(RemotePackage, cls).find(path, **kwargs)

    def store(self, **kwargs):
        path = RemotePackage.PATH % {'project': self.get('project'),
                                     'package': self.get('name')}
        return super(RemotePackage, self).store(path, method='PUT', **kwargs)

    @classmethod
    def delete(cls, project, package, **kwargs):
        path = RemotePackage.DELETE_PATH % {'project': project,
                                            'package': package}
        return super(RemotePackage, cls).delete(path, **kwargs)


class Request(RemoteModel):
    GET_PATH = '/request/%(reqid)s'
    SCHEMA = ''

    def __init__(self, **kwargs):
        super(Request, self).__init__(tag='request', schema=Request.SCHEMA,
                                      store_schema=Request.SCHEMA, **kwargs)

    @classmethod
    def find(cls, reqid, **kwargs):
        path = Request.GET_PATH % {'reqid': reqid}
        if not 'schema' in kwargs:
            kwargs['schema'] = Request.SCHEMA
        return super(Request, cls).find(path, **kwargs)

    def store(self, **kwargs):
        path = '/request'
        f = super(Request, self).store(path, method='POST',
                                       cmd='create', **kwargs)
        self._read_xml_data(f.read())

    @classmethod
    def delete(cls, reqid, **kwargs):
        path = Request.GET_PATH % {'reqid': reqid}
        return super(Request, cls).delete(path, **kwargs)

    def _change_state(self, state, review=None, **kwargs):
        """Changes the state of the request.

        state is the new state of the request.

        Keyword arguments:
        review -- change state of review review (default: None)
        **kwargs -- optional parameters for the http request

        """
        path = Request.GET_PATH % {'reqid': self.get('id')}
        query = {'cmd': 'changestate', 'newstate': state}
        if review is not None:
            query['cmd'] = 'changereviewstate'
            attrs = review.keys()
            for kind in ('by_user', 'by_group', 'by_project', 'by_package'):
                query[kind] = review.get(kind, '')
        query.update(kwargs)
        request = Osc.get_osc().get_reqobj()
        request.post(path, **query)
        f = request.get(path)
        self._read_xml_data(f.read())

    def accept(self, **kwargs):
        """Accepts the request.

        Keyword arguments:
        comment -- a comment (default: '')
        review -- change state of review review (default: None)
        **kwargs -- optional parameters for the http request

        """
        self._change_state('accepted', **kwargs)

    def decline(self, **kwargs):
        """Declines the request.

        Keyword arguments:
        comment -- a comment (default: '')
        review -- change state of review review (default: None)
        **kwargs -- optional parameters for the http request

        """
        self._change_state('declined', **kwargs)

    def revoke(self, **kwargs):
        """Revokes the request.

        Keyword arguments:
        comment -- a comment (default: '')
        **kwargs -- optional parameters for the http request

        """
        self._change_state('revoked', **kwargs)

    def supersede(self, reqid, **kwargs):
        """Supersedes the request.

        reqid is the request id which supersedes this request.

        Keyword arguments:
        comment -- a comment (default: '')
        review -- change state of review review (default: None)
        **kwargs -- optional parameters for the http request

        """
        self._change_state('superseded', superseded_by=reqid, **kwargs)


class RORemoteFile(object):
    """Provides basic methods to read and to store a remote file.

    Note: it isn't possible to seek around the file, once the data is
    read it isn't possible to read it again. If you need to seeking and
    more advanced file support use RWRemoteFile.

    """

    def __init__(self, path, stream_bufsize=8192, method='GET',
                 mtime=None, mode=0644, lazy_open=True, **kwargs):
        """Constructs a new RemoteFile object.

        path is the remote path which is used for the http request.
        A ValueError is raised if mtime or mode are specified but
        are no integers.

        Keyword arguments:
        stream_bufsize -- read bytes which are returned when iterating over
                          this object (default: 8192)
        method -- the http method which is used for the request (default: GET)
        mtime -- the mtime of the file (only used by write_to) (default: None)
        mode -- the mode of the file (only used by write_to) (default: 0644)
        lazy_open -- open the url lazily that is when a read request is issued
                     (default: True)
        kwargs -- optional arguments for the http request (like query
                  parameters)

        """
        super(RORemoteFile, self).__init__()
        self.path = path
        self.stream_bufsize = stream_bufsize
        self.method = 'GET'
        self.kwargs = kwargs
        self._remote_size = -1
        self._fobj = None
        self.mtime = None
        try:
            if mtime is not None:
                self.mtime = int(mtime)
            self.mode = int(mode)
        except ValueError as e:
            raise ValueError("mtime and mode must be integers")
        if not lazy_open:
            self._init_read()

    def _init_read(self):
        request = Osc.get_osc().get_reqobj()
        http_method = _get_http_method(request, self.method)
        self._fobj = http_method(self.path, **self.kwargs)
        self._remote_size = int(self._fobj.headers.get('Content-Length', -1))

    def _read(self, size=-1):
        """internal method which performs the read.

        All method in _this_ class should use _read instead of read
        (otherwise it'll lead to problems if subclasses override the
        read method).

        """
        if self._fobj is None:
            self._init_read()
        return self._fobj.read(size)

    def read(self, size=-1):
        """Reads size bytes.

        If the size argument is omitted or negative read everything.

        """
        return self._read(size)

    def close(self):
        if self._fobj is not None:
            self._fobj.close()

    def write_to(self, dest, size=-1):
        """Write file to dest.

        If dest is a file-like object (that is it has a write(buf) method)
        it's write method will be called. If dest is a filename the data will
        be written to it (existing files will be overwritten, if the file
        doesn't exist it will be created).

        Keyword arguments:
        size -- write only size bytes (default: -1 (means write everything))

        """
        copy_file(self, dest, mtime=self.mtime, mode=self.mode,
                  bufsize=self.stream_bufsize, size=size, read_method='_read')

    def __iter__(self, size=-1):
        """Iterates over the file"""
        return iter_read(self, bufsize=self.stream_bufsize, size=size)


class RWRemoteFile(RORemoteFile):
    """Provides more advanced methods for reading and writing a remote file.

    It's possible to read, write and seek the file. Additionally convenience
    methods like readline, readlines are also provided.
    If the remote file is small than 8096 bytes the file is represented by
    a StringIO object (the size is configurable, see __init__). Otherwise the
    file is represented by a NamedTemporaryFile which is written to disk.

    """

    def __init__(self, path, append=False, wb_method='PUT', wb_path='',
                 schema='', tmp_size=8096, use_tmp=False, **kwargs):
        """Constructs a new RWRemoteFile object.

        path is the remote path which is used for the http request
        (to get the file, if needed).

        Keyword arguments:
        append -- append data to the existing file instead of overwriting it
                   (default: False)
        wb_method -- write back method for the http request (default: PUT)
        wb_path -- path which is used to store the file back (default: path)
        tmp_size -- if the remote file exceeds or equals this size limit a
                    tmpfile is used
        use_tmp -- always use a tmpfile (regardless of the tmp_size)
        schema -- filename to xml schema which is used to validate the repsonse
                  after the writeback
        kwargs -- see class RORemoteFile

        """
        super(RWRemoteFile, self).__init__(path, **kwargs)
        self.append = append
        self.wb_method = wb_method
        self.wb_path = wb_path
        self._schema = schema
        self.tmp_size = tmp_size
        self.use_tmp = use_tmp
        self._modified = False

    def __getattr__(self, name):
        if self._fobj is None:
            self._init_fobj(name != 'write')
        if name in ('write', 'writelines', 'truncate'):
            self._modified = True
        return getattr(self._fobj, name)

    def _init_fobj(self, read_required):
        read_required = read_required or self.append
        if read_required:
            self._init_read()
        if self._remote_size >= self.tmp_size or self.use_tmp:
            new_fobj = NamedTemporaryFile()
        else:
            new_fobj = StringIO()
        if read_required:
            # we read/write _everything_ (otherwise this class needs
            # a bit more logic - can be added if needed)
            self.write_to(new_fobj)
            # close it because it isn't needed anymore
            self._fobj.close()
        new_fobj.seek(0, os.SEEK_SET)
        self._fobj = new_fobj

    def read(self, size=-1):
        if self._fobj is None:
            self._init_fobj(True)
        return self._fobj.read(size)

    def write_back(self, force=False, **kwargs):
        """Write back data to the server.

        The write back only happens if the file was modified
        (that is the write, writelines or truncate method was
        called at least one time).

        Keyword arguments:
        force -- always write back data to server (regardless if it
                 was modified or not) (default: False)
        kwargs -- optional parameters for the writeback http request (like
                  query parameters)

        """
        if not self._modified and not force:
            return
        if self._fobj is None:
            self._init_fobj(read_required=True)
        request = Osc.get_osc().get_reqobj()
        http_method = _get_http_method(request, self.wb_method)
        if not 'schema' in kwargs:
            kwargs['schema'] = self._schema
        data = None
        filename = ''
        if hasattr(self._fobj, 'getvalue'):
            data = self._fobj.getvalue()
        else:
            filename = self._fobj.name
        self._fobj.flush()
        wb_path = self.wb_path or self.path
        http_method(wb_path, data=data, filename=filename, **kwargs)
        self._modified = False

    def close(self, **kwargs):
        """Close this file.

        Before the close write_back is called which may write
        the data back to the server.

        Keyword arguments:
        kwargs -- optional parameters for the write_back method

        """
        self.write_back(**kwargs)
        super(RWRemoteFile, self).close()


class RWLocalFile(RWRemoteFile):
    """Represents a local file which can be written back to the server."""

    def __init__(self, path, **kwargs):
        """Constructs a new RWLocalFile object.

        path is the local path to the file.
        A ValueError is raised if wb_path is not present
        or empty in kwargs.

        Keyword arguments:
        kwargs -- see RWRemoteFile (Note: tmp_size and use_tmp are ignored)

        """
        if not kwargs.get('wb_path', ''):
            raise ValueError('wb_path keyword argument is required')
        super(RWLocalFile, self).__init__(path, **kwargs)

    def _init_fobj(self, read_required):
        if self.append:
            self._fobj = open(self.path, 'a+')
        else:
            self._fobj = open(self.path, 'w+')
