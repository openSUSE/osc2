"""This modules provides classes and methods for build related stuff.

To access the remote build data use the class BuildResult.
"""

from lxml import etree, objectify

from osc.remote import RORemoteFile, RWRemoteFile
from osc.util.xml import get_parser
from osc.core import Osc

__all__ = ['BuildResult']

def _get_parser():
    """Returns an objectify parser object."""
    tag_class = {'status': Status, 'binarylist': BinaryList,
                 'binary': Binary}
    return get_parser(**tag_class)


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
        path = "/build/%s/%s/%s/%s" % (project, repository, arch, package)
        request = Osc.get_osc().get_reqobj()
        if not 'schema' in kwargs:
            kwargs['schema'] = BinaryList.SCHEMA
        f = request.get(path, **kwargs)
        parser = _get_parser()
        bl = objectify.fromstring(f.read(), parser=parser)
        bl.set('project', project)
        bl.set('package', package)
        bl.set('repository', repository)
        bl.set('arch', arch)
        return bl

class Binary(objectify.ObjectifiedElement):
    """Represents a binary tag + some additional data"""

    def file(self, **kwargs):
        """Returns a RemoteFile object.
        
        This can be used to read/save the binary file.

        Keyword arguments:
        **kwargs -- optional parameters for the http request

        """
        path = "/build/%(project)s/%(repository)s/%(arch)s/%(package)s/" \
               "%(fname)s"
        parent = self.getparent()
        data = {'project': parent.get('project'),
                'package': parent.get('package'),
                'repository': parent.get('repository'),
                'arch': parent.get('arch'), 'fname': self.get('filename')}
        path = path % data
        return RORemoteFile(path, **kwargs)

class BuildResult(object):
    """Provides methods to access the remote build result"""
    RESULT_SCHEMA = ''
    BUILDDEPINFO_SCHEMA = ''

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
        super(BuildResult, self).__init__()
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
        if not 'schema' in kwargs:
            kwargs['schema'] = BuildResult.RESULT_SCHEMA
        f = request.get(path, package=package, repository=repository,
                        arch=arch, **kwargs)
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

        Keyword arguments:
        kwargs -- optional arguments for the http request

        """
        return BinaryList.create(self.project, self.repository, self.arch,
                                 self.package or '_repository', **kwargs)

    def log(self, **kwargs):
        """Get the buildlog.

        If repository, arch or package weren't specified during the __init__
        call a ValueError is raised.

        Keyword arguments:
        **kwargs -- optional parameters for the http request

        """
        if not (self.repository and self.arch and self.package):
            raise ValueError("repository, arch, package are mandatory for log")
        request = Osc.get_osc().get_reqobj()
        path = "/build/%s/%s/%s/%s/_log" % (self.project, self.repository,
                                            self.arch, self.package)
        return RWRemoteFile(path, **kwargs)

    def builddepinfo(self, reverse=False, **kwargs):
        """Get the builddepinfo.

        If reverse is True a reverse builddepinfo lookup is done.

        Keyword arguments:
        **kwargs -- optional parameters for the http request

        """
        package = self.package or '_repository'
        path = "/build/%s/%s/%s/%s/_builddepinfo" % (self.project,
                                                     self.repository,
                                                     self.arch, package)
        request = Osc.get_osc().get_reqobj()
        view = 'pkgnames'
        if reverse:
            view = 'revpkgnames'
        if not 'schema' in kwargs:
            kwargs['schema'] = BuildResult.BUILDDEPINFO_SCHEMA
        f = request.get(path, view=view, **kwargs)
        # no custom parser needed atm
        return objectify.fromstring(f.read())
