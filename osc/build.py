"""This modules provides classes and methods for build related stuff.

To access the remote build data use the class BuildResult.
"""

from lxml import etree, objectify

from osc.core import Osc

def _get_parser():
    """Returns a parser object which uses OscElementClassLookup as
    the lookup class.

    """
    parser = objectify.makeparser()
    lookup = OscElementClassLookup()
    parser.set_element_class_lookup(lookup)
    return parser

class OscElementClassLookup(etree.PythonElementClassLookup):
    """A data element should be represented by a StringElement"""

    def __init__(self):
        fallback = objectify.ObjectifyElementClassLookup()
        super(OscElementClassLookup, self).__init__(fallback=fallback)

    def lookup(self, doc, root):
        if root.tag == 'status':
            return Status
        elif root.tag == 'binarylist':
            return BinaryList
        return None

class Status(objectify.ObjectifiedElement):
    """Represents a status tag"""

    def __getattr__(self, name):
        try:
            return super(Status, self).__getattr__(name)
        except AttributeError:
            if name == 'details':
                return ''
            raise

class BinaryList(objectify.ObjectifiedElement):
    """Represents a binarylist + some additional data"""
    SCHEMA = ''

    @staticmethod
    def create(project, repository, arch, package='_repository', **kwargs):
        """Creates a new BinaryList object.

        project, repository and arch parameters are required.

        Keyword arguments:
        package -- specify an optional package (default: '_repository')
        kwargs -- optional parameters for the http request (like query
                  parameters)

        """
        path = '/build/%s/%s/%s/%s' % (project, repository, arch, package)
        request = Osc.get_osc().get_reqobj()
        if 'schema' in kwargs:
            kwargs['schema'] = BinaryList.SCHEMA
        f = request.get(path, **kwargs)
        parser = _get_parser()
        bl = objectify.fromstring(f.read(), parser=parser)
        bl.set('project', project)
        bl.set('repository', repository)
        bl.set('arch', arch)
        return bl

class Binary(objectify.ObjectifiedElement):
    """Represents a binary tag + some additional data"""

    def file(self):
        """Returns a RemoteFile object.
        
        This can be used to read/save the binary file.

        """
        path = '/build/%s/%s/%s/%s' % (self.get('project'),
                                       self.get('repository'),
                                       self.get('arch'),
                                       self.get('filename'))


class BuildResult(object):
    """Provides methods to access the remote build result"""

    def __init__(self, project, package='', repository='', arch=''):
        """Constructs a new object.

        project is the project for which the build result should be
        retrieved.

        Keyword arguments:
        package -- limit results to this package (default: '')
        repository -- limit results to this repository (default: '')
        arch -- limit results to this arch (default: '')

        Note: some commands require a package or repository or arch
        parameter. If those weren't specified here it's possible to
        specify them when the specific method is invoked (if they're
        not present a ValueError is raised).

        """
        self.project = project
        self.package = package
        self.repository = repository
        self.arch = arch

    def result(self, **kwargs):
        """Get the build result.

        Keyword arguments:
        package -- limit results to package (default: '')
        repository -- limit results repository
        arch -- limit results to arch
        kwargs -- optional arguments for the http request
        Note: package, repository and arch may override the
        current package, repository and arch instance attributes.

        """
        package = kwargs.pop('package', self.package)
        repository = kwargs.pop('repository', self.repository)
        arch = kwargs.pop('arch', self.arch)
        request = Osc.get_osc().get_reqobj()
        path = "/build/%s/_result" % self.project
        f = request.get(path, package=package, repository=repository,
                        arch=arch)
        parser = _get_parser()
        results = objectify.fromstring(f.read(), parser=parser)
        return results

    def _prepare_kwargs(self, kwargs, *required):
        for i in required:
            if not i in kwargs and getattr(self, i, ''):
                kwargs[i] = getattr(self, i)
            else:
                raise ValueError("missing parameter: %s" % i)

    def binarylist(self, **kwargs):
        """Get the binarylist.

        Note: package, repository and arch parameters are required
        (unless already specified during __init__). If missing a
        ValueError is raised

        Keyword arguments:
        package -- override package attribute (default: '')
        repository -- override repository attribute
        arch -- override arch attribute
        kwargs -- optional arguments for the http request

        """
        self._prepare_kwargs(kwargs, 'repository', 'arch')
        return BinaryList.create(self.project, kwargs.pop('repository'),
                                 kwargs.pop('arch'), **kwargs)
