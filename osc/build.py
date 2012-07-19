"""This modules provides classes and methods for build related stuff.

To access the remote build data use the class BuildResult.
"""

from cStringIO import StringIO

from lxml import etree, objectify

from osc.remote import RORemoteFile, RWRemoteFile
from osc.util.io import copy_file
from osc.util.xml import fromstring
from osc.util.cpio import CpioArchive
from osc.core import Osc

__all__ = ['BuildResult']


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
    def _perform_request(project, repository, arch, package, **kwargs):
        """Performs http request and returns response object.

        Keyword arguments:
        kwargs -- optional parameters for the http request (like query
                  parameters)

        """
        path = "/build/%s/%s/%s/%s" % (project, repository, arch, package)
        request = Osc.get_osc().get_reqobj()
        return request.get(path, **kwargs)

    @staticmethod
    def _create_xml(project, repository, arch, package, **kwargs):
        """Creates and returns a new BinaryList object.

        Keyword arguments:
        kwargs -- optional parameters for the http request (like query
                  parameters)

        """
        if not 'schema' in kwargs:
            kwargs['schema'] = BinaryList.SCHEMA
        f = BinaryList._perform_request(project, repository, arch, package,
                                        **kwargs)
        bl = fromstring(f.read(), binarylist=BinaryList, binary=Binary)
        bl.set('project', project)
        bl.set('package', package)
        bl.set('repository', repository)
        bl.set('arch', arch)
        return bl

    @staticmethod
    def _create_cpio(project, repository, arch, package, **kwargs):
        """Creates and returns a CpioArchive object.

        Keyword arguments:
        kwargs -- optional parameters for the http request (like query
                  parameters)

        """
        f = BinaryList._perform_request(project, repository, arch, package,
                                        **kwargs)
        return CpioArchive(fobj=f)

    @staticmethod
    def create(project, repository, arch, package='_repository', **kwargs):
        """Creates a new BinaryList object.

        project, repository and arch parameters are required.

        Keyword arguments:
        package -- specify an optional package (default: '_repository')
        kwargs -- optional parameters for the http request (like query
                  parameters)

        """
        # TODO: support other views (like cache) as well
        if kwargs.get('view', '') == 'cpio':
            return BinaryList._create_cpio(project, repository, arch, package,
                                           **kwargs)
        return BinaryList._create_xml(project, repository, arch, package,
                                      **kwargs)


class Binary(objectify.ObjectifiedElement):
    """Represents a binary tag + some additional data"""

    def file(self, **kwargs):
        """Returns a RORemoteFile object.

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
        results = fromstring(f.read(), status=Status)
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
        return fromstring(f.read())


class BuildInfo(object):
    """Provides methods to work with a buildinfo element."""

    def __init__(self, project='', package='', repository='', arch='',
                 xml_data='', binarytype='', data=None, **kwargs):
        """Constructs a new BuildInfo object.

        A ValueError is raised if xml_data is specified and project or
        package or repository or arch.
        A ValueError is raised if no binarytype is specified and the
        buildinfo has no file element.

        Keyword arguments:
        project -- the project (default: '')
        package -- the package (default: '')
        repository -- the repository (default: '_repository')
        arch -- the architecture (default: '')
        xml_data -- a xml str which contains a buildinfo element (default: '')
        binarytype -- the package type of the bdep elements (rpm, deb etc.)
                      (default: '')
        data -- a specfile or cpio archive which is POSTed to the server
                (default: None)
        **kwargs -- optional parameters for the http request

        """
        if ((project or package or repository or arch) and xml_data
            or not (project and repository and arch) and not xml_data):
            msg = 'Either project, package, repository, arch or xml_data'
            raise ValueError(msg)
        elif not xml_data:
            package = package or '_repository'
            path = "/build/%s/%s/%s/%s/_buildinfo" % (project, repository,
                                                      arch, package)
            request = Osc.get_osc().get_reqobj()
            if data is None:
                f = request.get(path, **kwargs)
            else:
                f = request.post(path, data=data, **kwargs)
            xml_data = f.read()
        self._xml = fromstring(xml_data, bdep=BuildDependency)
        self._calculate_binarytype(binarytype)

    def _calculate_binarytype(self, binarytype):
        """Calculates the binarytype of the bdep elements.

        A ValueError is raised if the binarytype cannot be
        calculated (that is the xml has no file element
        or the passed binarytype is None/the empty str).

        """
        binarytype = binarytype or self._xml.get('binarytype')
        if binarytype:
            self._xml.set('binarytype', binarytype)
            return
        spec = self._xml.find('file')
        if spec is None:
            msg = 'specify binarytype (cannot be calculated from xml)'
            raise ValueError(msg)
        data = spec.text.rsplit('.', 1)
        if len(data) != 2:
            # TODO: support Arch's PKGBUILD
            raise ValueError('unsupported file type')
        ext = data[1]
        if ext in ('spec', 'kiwi'):
            binarytype = 'rpm'
        elif ext == 'dsc':
            binarytype = 'deb'
        else:
            raise ValueError("unsupported file ext: \"%s\"" % ext)
        self._xml.set('binarytype', binarytype)

    def _bdep_filter(self, attr):
        """Filters bdeps by attribute attr.

        A bdep object is yielded if attribute attr is set
        to "1".

        """
        for bdep in self._xml.iterfind('bdep'):
            if bdep.get(attr) == '1':
                yield bdep

    def preinstall(self):
        """Returns generator to preinstall bdeps"""
        return self._bdep_filter('preinstall')

    def noinstall(self):
        """Returns generator to noinstall bdeps"""
        return self._bdep_filter('noinstall')

    def cbinstall(self):
        """Returns generator to cbinstall bdeps"""
        return self._bdep_filter('cbinstall')

    def cbpreinstall(self):
        """Returns generator to cbpreinstall bdeps"""
        return self._bdep_filter('cbpreinstall')

    def vminstall(self):
        """Returns generator to vminstall bdeps"""
        return self._bdep_filter('vminstall')

    def runscripts(self):
        """Returns generator to runscripts bdeps"""
        return self._bdep_filter('runscripts')

    def write_to(self, dest):
        """Write buildinfo xml to dest.

        Either dest is a path to a file or a file-like object
        (that is it has a write method).

        """
        xml_data = etree.tostring(self._xml, pretty_print=True)
        sio = StringIO(xml_data)
        copy_file(sio, dest)

    def __getattr__(self, name):
        return getattr(self._xml, name)


class BuildDependency(objectify.ObjectifiedElement):
    """Represents a build dependency (bdep element)."""

    def get(self, name, *args, **kwargs):
        if name not in ('filename', 'binarytype'):
            return super(BuildDependency, self).get(name, *args, **kwargs)
        elif name == 'binarytype':
            return self._calculate_binarytype()
        elif 'binary' in self.keys():
            # no need to construct the filename (this is set by the backend)
            return self.get('binary')
        # construct filename (refactor code in rpm, deb etc. module)
        binarytype = self.get('binarytype')
        if binarytype == 'rpm':
            return self.rpmfilename()
        elif binarytype == 'deb':
            return self.debfilename()

    def _calculate_binarytype(self):
        """Returns the binarytype.

        A ValueError is raised if the binarytype cannot be
        calculated.

        """
        binarytype = super(BuildDependency, self).get('binarytype')
        parent = self.getparent()
        if binarytype is None and parent is None:
            raise ValueError("binarytype and parent are None")
        elif binarytype is None:
            return parent.get('binarytype')
        return binarytype

    def rpmfilename(self):
        """Returns a rpm filename.

        A ValueError is raised if the binarytype is not rpm.

        """
        if self.get('binarytype') != 'rpm':
            raise ValueError('illegal rpmfilename call')
        return "%s-%s-%s.%s.rpm" % (self.get('name'), self.get('version'),
                                    self.get('release'), self.get('arch'))

    def debfilename(self):
        """Returns a deb filename.

        A ValueError is raised if the binarytpe is not deb.

        """
        if self.get('binarytype') != 'deb':
            raise ValueError('illegal debfilename call')
        if self.get('release') is None:
            # release is optional
            return "%s_%s_%s.deb" % (self.get('name'), self.get('version'),
                                     self.get('arch'))
        return "%s_%s-%s_%s.deb" % (self.get('name'), self.get('version'),
                                    self.get('release'), self.get('arch'))

    @staticmethod
    def fromdata(binarytype, arch, name, version, release='', project='',
                 repository=''):
        """Creates a new BuildDependency object.

        binarytype is the binarytype, arch the arch, name the name, version
        the version of the dependency.
        If binarytype is rpm and a release is not specified a ValueError is
        raised.

        Keyword arguments:
        release -- optional release (default: '')
        project -- the project to which the dependency belongs to (default: '')
        repository -- the repository where the dependency can be found
                      (default: '')

        """
        if binarytype == 'rpm' and not release:
            raise ValueError("binarytype rpm requires a release")
        xml = fromstring('<bdep />', bdep=BuildDependency)
        xml.set('binarytype', binarytype)
        xml.set('name', name)
        xml.set('version', version)
        if release:
            xml.set('release', release)
        xml.set('arch', arch)
        if project:
            xml.set('project', project)
        if repository:
            xml.set('repository', repository)
        return xml
