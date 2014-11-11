"""This module provides classes to manage a local package cache
and to fetch build dependencies from the api or a mirror.

"""

import os
from collections import namedtuple

import urlparse
from urlgrabber import grabber, mirror

from osc2.build import BuildResult
from osc2.util.listinfo import ListInfo
from osc2.util.notify import Notifier
from osc2.util.io import copy_file
from osc2.remote import RORemoteFile
from osc2.httprequest import HTTPError, build_url


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
        return super(NamePreferCacheManager, self)._calculate_filename(
            bdep, *args, **kwargs)

    def remove(self, bdep, *args, **kwargs):
        if bdep.get('name') in self._prefers.keys():
            # do not unlink package
            del self._prefers[bdep.get('name')]
            return
        super(NamePreferCacheManager, self).remove(bdep, *args, **kwargs)


def _download_url_builder(binfo, bdep):
    """Returns a download url.

    If binfo has no downloadurl attribute None is returned.
    In this case the fetcher does not consider this url.
    Otherwise a list [http(s)://host, path, query-dict] is
    returned.

    """
    if binfo.get('downloadurl') is None:
        return None, None, None
    data = urlparse.urlparse(binfo.get('downloadurl'))
    # remove path from downloadurl
    downloadurl = binfo.get('downloadurl').replace(data[2], '')
    path = "%s/%s/%s/%s/%s" % (data[2], bdep.get('project').replace(':', ':/'),
                               bdep.get('repository'), bdep.get('arch'),
                               bdep.get('filename'))
    # no queries
    return downloadurl, path, {}


class CustomMirrorGroup(mirror.MirrorGroup, object):
    """It's sole purpose is to override the _join_url methods for our needs."""

    def __init__(self, *args, **kwargs):
        """Constructs a new CustomMirrorGroup object.

        For *args and **kwargs see class urlgrabber.mirror.MirrorGroup.

        """
        super(CustomMirrorGroup, self).__init__(*args, **kwargs)
        self.used_mirror_urls = []

    def _join_url(self, base_url, rel_url):
        """Joins base_url with rel_url.

        In our scenario rel_url is always the empty str. The
        original version of the method would return base_url + '/' + rel_url
        which is wrong in this case.

        """
        return base_url

    def _get_mirror(self, *args, **kwargs):
        """Returns the next mirror (if one exists).

        This overrides _get_mirror in order to keep track of the
        used mirror urls.

        """
        url = super(CustomMirrorGroup, self)._get_mirror(*args, **kwargs)
        # store them in "human readable" format
        host, path, query = url['mirror']
        self.used_mirror_urls.append(build_url(host, path, **query))
        return url

    def urlopen(self):
        """Returns a RORemoteFile object.

        Overrides urlopen in order to make the interface a bit
        nicer (otherwise the caller would have to specify an empty
        url).

        """
        return super(CustomMirrorGroup, self).urlopen('')


class MirrorUrlOpener(object):
    """Used to open a mirror url."""

    def __init__(self, bdep):
        """Constructs a new MirrorUrlOpener object.

        bdep is a BuildDependency which should be fetched.

        """
        super(MirrorUrlOpener, self).__init__()
        self._bdep = bdep

    def urlopen(self, url, **kwargs):
        """Returns a RORemoteFile instance.

        Invoked by the CustomMirrorGroup object.
        url is a list with 3 elements: url[0] the host,
        url[1] the path and url[2] optional query parameters.

        Keyword arguments:
        **kwargs -- kwargs are ignored

        """
        host, path, query = url
        f = None
        try:
            f = RORemoteFile(path, apiurl=host, lazy_open=False, **query)
        except HTTPError as e:
            if f is not None:
                f.close()
            exc = grabber.URLGrabError(14, str(e))
            exc.orig_exc = e
            raise exc
        return f


class FetchListener(object):
    """Notifies a client about the fetching process.

    Additionally a client can stop the fetching process by raising
    a BuildDependencyFetchError exception (or a subclass) (Note:
    the caller of the fetcher has appropriately handle this exception).

    """

    def pre(self, binfo, finfo):
        """This method is called before the fetching process starts.

        finfo is a ListInfo instance (representing a FetchInfo). binfo
        is a BuildInfo instance.

        """
        raise NotImplementedError()

    def post(self, fetch_results):
        """This method is called after all bdeps are fetched.

        fetch_results is a list which contains FetchResult instances.
        Note this method is called even if the fetching process
        was unsuccessful (that is afterwards a BuildDependencyFetcherError
        might be raised).

        """
        raise NotImplementedError()

    def pre_fetch(bdep, fr):
        """This method is called before a specificy bdep is fetched.

        bdep is a BuildDependency instance and fr is a FetchResult
        instance or None. This method is at least called 2 times for
        a bdep.
        It is also possible that there are subsequent pre_fetch calls
        without any intermediate post_fetch calls. Also there might
        be more pre_fetch calls than post_fetch calls (for instance
        if a bdep cannot be delivered via cpio pre_fetch is called
        but post_fetch is not).

        """
        raise NotImplementedError()

    def post_fetch(self, fr):
        """This method is called after a bdep is fetched, written to the cache.

        bdep is a BuildDependency instance and fr is a FetchResult
        instance or None. This method is at least called 2 times for
        a bdep.

        """
        raise NotImplementedError()


class FetchNotifier(Notifier):
    """Notifies all registered FetchListener."""

    def pre(self, *args, **kwargs):
        self._notify('pre', *args, **kwargs)

    def post(self, *args, **kwargs):
        self._notify('post', *args, **kwargs)

    def pre_fetch(self, *args, **kwargs):
        self._notify('pre_fetch', *args, **kwargs)

    def post_fetch(self, *args, **kwargs):
        self._notify('post_fetch', *args, **kwargs)


class BuildDependencyFetchError(Exception):
    """Raised if a bdep or multiple bdeps cannot be fetched."""

    def __init__(self, bdeps, errors=''):
        """Constructs a new BuildDependencyFetchError object.

        bdeps is a list of the missing BuildDependency objects.

        Keyword arguments:
        errors -- an error str (usually the contents of the .errors
                  file from the cpio archive) (default: '')

        """
        super(BuildDependencyFetchError, self).__init__()
        self.bdeps = bdeps
        self.errors = errors


class BuildDependencyFetcher(object):
    """This class can be used to fetch build dependencies."""

    FetchResult = namedtuple('FetchResult',
                             ['bdep', 'available', 'mirror_urls',
                              'mirror_match'],
                             verbose=False)

    def __init__(self, cmgr, url_builder=None, listener=None):
        """Constructs a new BuildDependencyFetcher object.

        cmgr is a CacheManager.

        Keyword arguments:
        url_builder -- list of methods which are used to build mirror
                       urls (default: [])
        listener -- list of FetchListener instances (default: [])

        """
        super(BuildDependencyFetcher, self).__init__()
        self._cmgr = cmgr
        if url_builder is None:
            url_builder = []
        self._url_builder = url_builder
        self._url_builder.append(_download_url_builder)
        if listener is None:
            listener = []
        self._notifier = FetchNotifier(listener)
        self.fetch_results = []
        self._cpio_todo = {}

    def _append_cpio(self, arch, bdep):
        """Appends bdep to the cpio download todo list.

        arch is the "default" architecture (usually binfo.arch).
        bdep is a BuildDependency instance.

        """
        prpap = "%s/%s/%s/%s" % (bdep.get('project'), bdep.get('repository'),
                                 bdep.get('repoarch', arch),
                                 bdep.get('package', '_repository'))
        self._cpio_todo.setdefault(prpap, []).append(bdep)

    def _calculate_fetchinfo(self, binfo):
        """Calculates fetchinfo list.

        A ListInfo object is returned which contains the available and
        missing bdeps. binfo is a BuildInfo instance.

        """
        finfo = ListInfo('available', 'missing')
        for bdep in binfo.bdep[:]:
            if self._cmgr.exists(bdep):
                finfo.append(bdep, 'available')
            else:
                finfo.append(bdep, 'missing')
        return finfo

    def find_fetch_result(self, bdep):
        """Returns the FetchResult for the given bdep.

        If no FetchResult is found None is returned.

        """
        for fr in self.fetch_results:
            if bdep == fr.bdep:
                return fr
        return None

    def _fetch(self, binfo, bdep):
        """Fetches bdep from a mirror and stores it in the cache.

        binfo is a BuildInfo and bdep is a BuildDependency object.

        """
        urls = []
        for url_builder in self._url_builder:
            components = url_builder(binfo, bdep)
            if not [i for i in components if i is None]:
                urls.append({'mirror': components})
        mgroup = CustomMirrorGroup(MirrorUrlOpener(bdep), mirrors=urls)
        # in this case there is no fetch result
        self._notifier.pre_fetch(bdep, None)
        f = None
        try:
            f = mgroup.urlopen()
        except grabber.URLGrabError:
            if f is not None:
                f.close()
            fr = BuildDependencyFetcher.FetchResult(bdep, False,
                                                    mgroup.used_mirror_urls,
                                                    False)
            self._notifier.post_fetch(bdep, fr)
            return fr
        # everything looks good - write file to cache
        self._cmgr.write(bdep, f)
        fr = BuildDependencyFetcher.FetchResult(bdep, True,
                                                mgroup.used_mirror_urls,
                                                True)
        self._notifier.post_fetch(bdep, fr)
        return fr

    def _fetch_cpio(self, defer_error=False):
        """Fetches bdeps from the api in a cpio archive.

        It tries to fetch all bdeps from the self._cpio_todo dict.
        A BuildDependencyFetchError is raised if a bdep cannot be
        fetched.

        Keyword arguments:
        defer_error -- if True it does not fail immediately if a bdep is
                       not found and tries to fetch the remaining bdeps
                       (default: False)

        """
        errors = ''
        missing_bdeps = []
        for prpap in sorted(self._cpio_todo.keys()):
            project, repo, arch, package = prpap.split('/', 4)
            br = BuildResult(project, package, repo, arch)
            binary = []
            # maps a cpio entry name to the corresponding bdep
            cpio_bdep = {}
            bdeps = self._cpio_todo[prpap]
            for bdep in bdeps:
                if package == '_repository':
                    name = bdep.get('name')
                    binary.append(name)
                    cpio_bdep[name + '.' + bdep.get('binarytype')] = bdep
                else:
                    binary.append(bdep.get('filename'))
                    cpio_bdep[bdep.get('filename')] = bdep
                self._notifier.pre_fetch(bdep, self.find_fetch_result(bdep))
            archive = br.binarylist(view='cpio', binary=binary)
            for archive_file in archive:
                if archive_file.hdr.name == '.errors':
                    errors += "\n" + archive_file.read().strip()
                    continue
                bdep = cpio_bdep[archive_file.hdr.name]
                self._cmgr.write(bdep, archive_file)
            # check if we got all files
            for bdep in bdeps:
                exists = self._cmgr.exists(bdep)
                fr = self.find_fetch_result(bdep)
                if fr is None:
                    # fr might be None if fetch was invoked with
                    # use_mirrors=False
                    fr = BuildDependencyFetcher.FetchResult(bdep, exists, [],
                                                            False)
                    self.fetch_results.append(fr)
                if exists:
                    self._notifier.post_fetch(bdep, fr)
                else:
                    missing_bdeps.append(fr)
            if missing_bdeps and not defer_error:
                break
        if missing_bdeps:
            raise BuildDependencyFetchError(missing_bdeps, errors.strip())

    def fetch(self, binfo, defer_error=False, use_mirrors=True):
        """Fetches all missing bdeps.

        binfo is a BuildInfo project whose build dependencies are
        fetched (if they do not exist in the cache).
        A BuildDependencyFetchError is raised if bdep cannot
        be downloaded.

        Keyword arguments:
        defer_error -- if True it does not fail immediately if a bdep is
                       not found and tries to fetch the remaining bdeps
                       (default: False)
        use_mirrors -- if False the bdeps will only be fetched from the api
                       (default: True)

        """
        finfo = self._calculate_fetchinfo(binfo)
        self._notifier.pre(binfo, finfo)
        for bdep in finfo.missing:
            if use_mirrors:
                fr = self._fetch(binfo, bdep)
                self.fetch_results.append(fr)
                if not fr.available:
                    self._append_cpio(binfo.arch, bdep)
            else:
                self._append_cpio(binfo.arch, bdep)
        self._fetch_cpio(defer_error)
        self._notifier.post(self.fetch_results)
