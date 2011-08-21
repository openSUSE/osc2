"""Provides classes to access the source
route"""

from lxml import objectify

from osc.util.xml import fromstring
from osc.remote import RORemoteFile
from osc.core import Osc


class Directory(objectify.ObjectifiedElement):
    def __iter__(self):
        return self.iterfind('entry')


class File(objectify.ObjectifiedElement):
    """Represents a file entry"""

    def file(self, **kwargs):
        """Returns a RORemoteFile object.

        This can be used to read/save the source file.

        Keyword arguments:
        **kwargs -- optional parameters for the http request

        """
        request = Osc.get_osc().get_reqobj()
        path = "/source/%(project)s/%(package)s/%(file)s"
        parent = self.getparent()
        data = {'project': parent.get('project'),
                'package': parent.get('name'), 'file': self.get('name')}
        # specifying a different rev probably makes no sense...
        if not 'rev' in kwargs:
            kwargs['rev'] = self.getparent().get('srcmd5')
        path = path % data
        mtime = int(self.get('mtime'))
        return RORemoteFile(path, mtime=mtime, **kwargs)


class Linkinfo(objectify.ObjectifiedElement):
    """Represents a linkinfo entry."""

    def is_expanded(self):
        """Return True package is expanded."""
        lsrcmd5 = self.get('lsrcmd5')
        xsrcmd5 = self.get('xsrcmd5')
        return xsrcmd5 is None and lsrcmd5 is not None

    def is_unexpanded(self):
        """Return True if package is unexpanded."""
        return not self.is_expanded()

    def has_error(self):
        """Return True if linkinfo has an error."""
        return self.get('error') is not None


class Project(object):
    """Class used to access /source/project data"""
    LIST_SCHEMA = ''

    def __init__(self, name):
        """Creates a new Project object.

        name is the name of the project.

        """
        super(Project, self).__init__()
        self.name = name

    def list(self, **kwargs):
        """List all packages for this project.

        Keyword arguments:
        **kwargs -- optional parameters for the http request

        """
        request = Osc.get_osc().get_reqobj()
        path = '/source/' + self.name
        if not 'schema' in kwargs:
            kwargs['schema'] = Project.LIST_SCHEMA
        f = request.get(path, **kwargs)
        entries = fromstring(f.read())
        r = []
        # using an xml representation for the <entry /> makes no
        # sense
        for e in entries.iterfind('entry'):
            r.append(Package(self.name, e.get('name')))
        return r


class Package(object):
    """Class used to access /source/project/package data"""
    LIST_SCHEMA = ''
    HISTORY_SCHEMA = ''

    def __init__(self, project, name):
        """Creates a new Package object.

        project is the project's name and name is the name
        of the package.

        """
        super(Package, self).__init__()
        self.project = project
        self.name = name

    def get(self, name):
        """Return attribute with name name."""
        return getattr(self, name)

    def list(self, **kwargs):
        """List all files for this package.
        Keyword arguments:
        **kwargs -- optional parameters for the http request

        """
        request = Osc.get_osc().get_reqobj()
        path = "/source/%s/%s" % (self.project, self.name)
        if not 'schema' in kwargs:
            kwargs['schema'] = Package.LIST_SCHEMA
        f = request.get(path, **kwargs)
        directory = fromstring(f.read(), directory=Directory, entry=File,
                               linkinfo=Linkinfo)
        # this is needed by the file class
        directory.set('project', self.project)
        return directory

    def log(self, **kwargs):
        """Get the commit log.

        Keyword arguments:
        **kwargs -- optional parameters for the http request

        """
        request = Osc.get_osc().get_reqobj()
        path = "/source/%s/%s/_history" % (self.project, self.name)
        if not 'schema' in kwargs:
            kwargs['schema'] = Package.HISTORY_SCHEMA
        f = request.get(path, **kwargs)
        return fromstring(f.read())
