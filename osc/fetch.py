"""This module provides classes to manage a local package cache
and to fetch build dependencies from the api or a mirror.

"""

import os

from osc.util.io import copy_file


class CacheManager(object):
    """Base class for a local cache manager.

    The cache manager provides an interface for storing build
    dependencies and retrieving the path to the a specific
    BuildDependency.

    """

    def __init__(self, root):
        """Constructs a new CacheManager object.

        root is a path to the cache dir. A ValueError is
        raised if root exists and is no dir or if root is not
        writable.

        """
        exists = os.path.exists(root)
        if exists and not os.path.isdir(root):
            raise ValueError("root \"%s\" exists but is no dir" % root)
        elif exists and not os.access(root, os.W_OK):
            raise ValueError("root \"%s\" exists but is not writable" % root)
        self._root = root

    def exists(self, bdep):
        """Returns True if bdep exists in the cache, False otherwise.

        bdep is a BuildDependency instance.

        """
        raise NotImplementedError()

    def filename(self, bdep):
        """Returns a filename for bdep (filename to the cache file).

        bdep is a BuildDependency instance. A ValueError is raised
        if bdep does not exist in the cache.

        """
        raise NotImplementedError()

    def remove(self, bdep):
        """Remove the file represented by bdep from the cache.

        bdep is a BuildDependency instance. A ValueError is raised
        if bdep does not exist in the cache.

        """
        raise NotImplementedError()

    def write(self, bdep, source):
        """Write source to cache.

        bdep is a BuildDependency instance. source is a filename or
        file-like object. A ValueError is raised if bdep already exists
        in the cache.

        """
        raise NotImplementedError()


class FilenameCacheManager(CacheManager):
    """Trivial cache manager implementation.

    The files are stored in a simple <project>/<repo>/<arch>/<package>
    hierarchy.

    """

    def __init__(self, root):
        super(FilenameCacheManager, self).__init__(root)

    def _calculate_filename(self, bdep):
        """Returns the calculated filename for bdep.

        bdep is a BuildDependency instance.

        """
        return os.path.join(self, self._root, bdep.get('project'),
                            bdep.get('repository'), bdep.get('arch'),
                            bdep.get('filename'))

    def _exists(self, bdep, error=False):
        """Returns True if bdep exists in the cache otherwise False.

        Keyword arguments:
        error -- if error is True and bdep does not exist in the cache a
                 ValueError is raised (default: False)

        """
        fname = self._calculate_filename(bdep)
        exists = os.path.exists(fname)
        if not exists and error:
            msg = "bdep for file \"%s\" does not exist" % bdep.get('filename')
            raise ValueError(msg)
        return exists

    def exists(self, bdep):
        return self._exists(bdep, error=False)

    def filename(self, bdep):
        # a ValueError is raised if bdep does not exist
        self._exists(bdep, error=True)
        return self._calculate_filename(bdep)

    def remove(self, bdep):
        # a ValueError is raised if bdep does not exist
        self._exists(bdep, error=True)
        fname = self._calculate_filename(bdep)
        os.unlink(fname)
        # check if we can remove some dirs
        dirname = os.path.dirname(fname)
        if not os.listdir(dirname):
            # remove arch
            os.rmdir(dirname)
        dirname = os.path.dirname(dirname)
        if not os.listdir(dirname):
            # remove repo
            os.rmdir(dirname)
        dirname = os.path.dirname(dirname)
        if not os.listdir(dirname):
            # remove project
            os.rmdir(dirname)

    def write(self, bdep, source):
        if self.exists(bdep):
            msg = "bdep for file \"%s\" already exists" % bdep.get('filename')
            raise ValueError(msg)
        fname = self._calculate_filename(bdep)
        dirname = os.path.dirname(fname)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        copy_file(source, fname)


class NamePreferCacheManager(FilenameCacheManager):
    """Prefer build dependencies by name.

    A pkgname->filename dict can be passed to the constructor and if for
    instance a filename for the build dependency with name "pkgname" is
    requested the corresponding filename is returned (regardless if a
    package with the same name and exact version, release, project, arch
    exists in the cache).

    """

    def __init__(self, root, **prefers):
        """Constructs a new NamePreferCacheManager object.

        root is a path to the cache dir. A ValueError is
        raised if root exists and is no dir or if root is not
        writable.

        Keyword arguments:
        **prefers -- name->filename mapping (see class' docstr for the details)
                     (default: {})

        """
        super(NamePreferCacheManager, self).__init__(root)
        self._prefers = prefers

    def _calculate_filename(self, bdep, *args, **kwargs):
        if bdep.get('name') in self._prefers.keys():
            return self._prefers[bdep.get('name')]
        return super(NamePreferCacheManager, self)._calculate_filename(bdep,
                                                                       *args,
                                                                       **kwargs
                                                                      )

    def remove(self, bdep, *args, **kwargs):
        if bdep.get('name') in self._prefers.keys():
            # do not unlink package
            del self._prefers[bdep.get('name')]
            return
        super(NamePreferCacheManager, self).remove(bdep, *args, **kwargs)
