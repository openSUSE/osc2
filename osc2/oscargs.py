"""This module provides a class to parse/resolve osc url-like
arguments.

Some notes about terminology:
- 'foo/bar' is called an component entry. The component entry 'foo/bar'
   consists of two components; the first component is 'foo' and the
   second component is 'bar'.
- 'api://project/package?' is also a component entry which consists of 3
   components; the first component is 'api://', the second is 'project'
   and the third component is 'package'. The '?' indicates that
   'package' is an optional component.
- 'wc_path' is called a wc path entry.
   A wc path is a path to a
     * project wc or
     * package wc or
     * file in a package wc
- 'plain_arg' is a plain argument entry. Any value can be passed to
   a plain argument entry ('foo', 'foo/bar', 'api://x/y' etc. are valid).

"""

import os
import re
import logging

from osc2.wc.project import Project
from osc2.wc.package import Package
from osc2.wc.util import (wc_is_project, wc_is_package, wc_read_project,
                          wc_read_package, wc_read_apiurl, wc_parent)


class ResolvedInfo(object):
    """Encapsulate resolved arguments"""

    def __init__(self, ignore_clashes=True):
        """Constructs a new ResolvedInfo object.

        Keyword arguments:
        ignore_clashes -- if True name clashes are ignored. A name clash occurs
                          if multiple oargs with the same "name" are specified.
                          By default the argument which is assigned to the
                          right most oarg is saved. If ignore_clashes is set
                          to False all arguments will be stored in a list
                          (default: True)

        """
        super(ResolvedInfo, self).__init__()
        self._data = {}
        self._ignore_clashes = ignore_clashes

    def add(self, name, value):
        """Add additional components.

        name is the name of the component and value
        the actual value.
        Note: if a component already exists it will
        be overriden with the new value.

        """
        if name in self._data and not self._ignore_clashes:
            l = self._data[name]
            if hasattr(l, 'extend'):
                # it is already a list
                l.append(value)
            else:
                self._data[name] = [l, value]
        else:
            self.set(name, value)

    def set(self, name, value):
        """Sets component name.

        name is the name of the (new) attribute and
        value its new value (existing values are
        overwritten).

        """
        self._data[name] = value

    def __getattr__(self, name):
        if name in self._data.keys():
            return self._data[name]
        return getattr(self._data, name)

    def __contains__(self, name):
        return name in self._data

    def __iter__(self):
        return self._data.iterkeys()

    def __str__(self):
        return str(self._data)


class AbstractEntry(object):
    """Base class for all entry kinds."""

    def match(self, arg):
        """Match entry against arg.

        If it does not match None is returned. Otherwise
        a dict is returned which contains the matches
        (some optional matches might be None).

        """
        raise NotImplementedError()

    def wc_resolve(self, path=''):
        """Try to read components from path.

        If path is specified it overrides the path which was passed
        to __init__.
        If all conditions are met (see class description for details)
        a dict is returned which contains the matches
        (some optional and _non_optional matches might be None).
        Otherwise None is returned.

        """
        return None


class ComponentEntry(AbstractEntry):
    """Manages Component objects."""

    def __init__(self, path=''):
        """Constructs a new Entry object.

        path, if specified, is a path to a project or package
        working copy. If the following conditions are met,
        path is taken into consideration for resolving:
        - 'project' and 'package' components are present _and_
          path is a package working copy
        or
        - a 'project' component is present _and_ (path is a
          project _or_ package working copy)

        """
        super(ComponentEntry, self).__init__()
        self._components = []
        self._path = path

    def append(self, component):
        """Add a Component object."""
        self._components.append(component)

    def _build_regex(self):
        regex = ''
        prev = None
        for c in self._components:
            sep = c.left_sep
            if sep and c.opt:
                sep += '?'
            if prev is not None and prev.api:
                # no separator if preceeding component was a api
                sep = ''
            regex += sep + c.regex
            prev = c
        regex = regex.lstrip('?')
        regex = '^' + regex
        regex += '$'
        return regex

    def match(self, arg):
        """Match entry against arg.

        If it does not match None is returned. Otherwise
        a dict is returned which contains the matches
        (some optional matches might be None).

        """
        regex = self._build_regex()
#        print regex, arg
        m = re.match(regex, arg)
        if m is None:
            return None
        return m.groupdict()

    def wc_resolve(self, path=''):
        """Try to read components from path.

        If path is specified it overrides the path which was passed
        to __init__.
        If all conditions are met (see class description for details)
        a dict is returned which contains the matches
        (some optional and _non_optional matches might be None).
        Otherwise None is returned.

        """
        path = path or self._path
        if not path:
            return None
        unresolved = dict([(comp.name, None) for comp in self._components])
        has_prj = 'project' in unresolved
        has_pkg = 'package' in unresolved and 'project' in unresolved
        if has_pkg:
            if wc_is_package(path):
                ret = {'apiurl': wc_read_apiurl(path),
                       'project': wc_read_project(path),
                       'package': wc_read_package(path)}
                unresolved.update(ret)
                return unresolved
        pkg_opt = True
        for comp in self._components:
            if comp.name == 'package':
                pkg_opt = comp.opt
        if has_prj and pkg_opt:
            if wc_is_project(path):
                ret = {'apiurl': wc_read_apiurl(path),
                       'project': wc_read_project(path)}
                unresolved.update(ret)
                return unresolved
        return None

    def __str__(self):
        return self._build_regex()


class WCPathEntry(AbstractEntry):
    """Represents a wc path entry.

    This class takes care that the definition of a wc path
    is satisfied for a passed wc path argument (specified by
    the user).

    """

    def __init__(self, name):
        """Constructs a new WCPathEntry object.

        name is the name of the attribute in the ResolvedInfo
        object.

        """
        super(WCPathEntry, self).__init__()
        self._name = name

    def match(self, path):
        """Checks if path is a wc path.

        If path is a wc path a WCPath object is returned
        otherwise None.

        """
        project_path = package_path = filename_path = None
        if not path:
            path = os.getcwd()
        path = os.path.normpath(path)
        par_dir = wc_parent(path)
        if wc_is_package(path):
            package_path = path
            project_path = par_dir
        elif wc_is_project(path):
            project_path = path
        elif par_dir is not None:
            if wc_is_package(par_dir):
                filename_path = path
                package_path = par_dir
                # check if package has a parent
                par_dir = wc_parent(package_path)
                if par_dir is not None and wc_is_project(par_dir):
                    project_path = par_dir
            elif wc_is_project(par_dir):
                project_path = par_dir
                package_path = path
            else:
                return None
        else:
            return None
        return {self._name: WCPath(project_path, package_path, filename_path)}

    def __str__(self):
        return 'wc_' + self._name


class PlainEntry(AbstractEntry):
    """Represents a plain entry."""

    def __init__(self, name):
        self._name = name

    def match(self, arg):
        """A match for a plain entry is always successful.

        None is never returned.

        """
        return {self._name: arg}

    def __str__(self):
        return 'plain_' + self._name


class AlternativeEntry(AbstractEntry):
    """Represents an alternative entry.

    An alternative entry is used to provide different
    syntaxes for an argument.
    It consists of several entries, whose supertype is
    AbstractEntry. The "match" method returns the match
    result of the first matching entry. The "wc_resolve"
    method is implemented analogously.

    """

    def __init__(self, *entries):
        """Constructs a new AlternativeEntry instance.

        *entries are instances of the class AbstractEntry.
        If no entries are provided, a ValueError is raised.

        """
        if not entries:
            raise ValueError('At least one entry is required')
        self._entries = entries

    @staticmethod
    def _firstNonNone(meths, *args, **kwargs):
        for meth in meths:
            res = meth(*args, **kwargs)
            if res is not None:
                return res
        return None

    def match(self, arg):
        """Return the match result of the first entry that matches arg."""
        meths = [getattr(entry, 'match') for entry in self._entries]
        return self._firstNonNone(meths, arg)

    def wc_resolve(self, *args, **kwargs):
        """Return the result of the first entry, where wc_resolve matches"""
        meths = [getattr(entry, 'wc_resolve') for entry in self._entries]
        return self._firstNonNone(meths, *args, **kwargs)

    def __str__(self):
        return OscArgs.ALTERNATIVE_SEP.join(
            [str(entry) for entry in self._entries])


class Component(object):
    """Represents a regex for a component"""
    APIURL_RE = "(?P<%s>.+)://"
    COMPONENT_RE = "(?P<%s>[^%s]+)"

    def __init__(self, format, separators, left_sep='', api=False):
        """Constructs a new Regex object.

        format is a component. separators is a list of
        component separators.

        Keyword arguments:
        api -- if True APIURL_RE will be used (default: False)
        left_sep -- the left side separator of this component (default: '')

        """
        super(Component, self).__init__()
        self.opt = format.endswith('?')
        self.api = api
        self.name = format.rstrip('?')
        self.left_sep = left_sep
        self.regex = Component.COMPONENT_RE % (self.name, ''.join(separators))
        if self.api:
            if self.name:
                self.name += '_'
            self.name += 'apiurl'
            self.regex = Component.APIURL_RE % self.name
        if self.opt:
            self.regex += '?'


class WCPath(object):
    """Represents a wc path."""

    def __init__(self, project_path, package_path, filename_path):
        """Constructs a new WCPath object.

        project_path is the path to the project wc. package_path is
        the path to the package wc. filename_path is the path to
        the wc filename. Either project_path or package_path or
        both aren't None.

        """
        self.project_path = project_path
        self.package_path = package_path
        self.filename_path = filename_path
        self.project = self.package = self.filename = None
        if self.project_path is not None:
            self.project = wc_read_project(self.project_path)
        if self.package_path is not None:
            if wc_is_package(self.package_path):
                self.package = wc_read_package(self.package_path)
            else:
                self.package = os.path.basename(self.package_path)
        if self.filename_path is not None:
            self.filename = os.path.basename(self.filename_path)

    def project_obj(self, *args, **kwargs):
        """Returns a Project object if possible.

        *args and **kwargs are optional arguments for Project's
        __init__ method. If no Project can be returned None is
        returned.

        """
        if self.project_path is None:
            return None
        return Project(self.project_path, *args, **kwargs)

    def package_obj(self, *args, **kwargs):
        """Returns a Package object if possible.

        *args and **kwargs are optional arguments for Package's
        __init__ method. If no Package can be returned None is
        returned.

        """
        if self.package_path is None or not wc_is_package(self.package_path):
            return None
        return Package(self.package_path, *args, **kwargs)


class OscArgs(object):
    """Resolves url-like arguments into its components.

    Note: to avoid name clashes when defining 2 or more api entries
    use the following syntax:
     'api://project', 'api(tgt)://tgt_project/tgt_package'
    The ResolvedInfo object will contain a "apiurl" and a
    "tgt_apiurl" attribute.

    """
    APIURL_RE = "api\(?([^)]+)?\)?://"
    ALTERNATIVE_SEP = '|'

    def __init__(self, *format_entries, **kwargs):
        """Constructs a new OscArgs instance.

        *format_entries contains the formatting entries.

        Keyword arguments:
        path -- path to a project or package working copy
                (default: ''). path might be used for component
                resolving.
        separators -- list of component separators (default: ['/', '@'])
        ignore_clashes -- ignore name clashes in the format_entries
                          (default: True)

        """
        super(OscArgs, self).__init__()
        self._logger = logging.getLogger(__name__)
        self._entries = []
        self._ignore_clashes = kwargs.pop('ignore_clashes', True)
        self._parse_entries(format_entries, kwargs.pop('path', ''),
                            kwargs.pop('separators', ['/', '@']))

    def _parse_component(self, format_entry, separators):
        """Yields a 2 tuple.

        The first entry is the left side separator and the second
        entry is the name of the component. The left side separator
        might be None (if the component is the first component in the
        format_entry str).
        format_entry is the format_entry str and separators a list
        of component separators.

        """
        left_sep = ''
        i = 0
        while i < len(format_entry):
            if format_entry[i] in separators:
                component = format_entry[:i]
                yield left_sep, component
                # set new left_sep
                left_sep = format_entry[i]
                format_entry = format_entry[i + 1:]
                i = 0
            i += 1
        # no separator left
        yield left_sep, format_entry

    def _parse_entries(self, format_entries, path, separators):
        """Create for each entry in format_entries the corresponding object.

        path is a path or the empty str and separators is a list
        of separators.

        """
        for entry in format_entries:
            e = self._parse_entry(entry, path, separators)
            self._entries.append(e)

    def _parse_entry(self, entry, path, separators):
        """Returns an instance, whose supertype is AbstractEntry, for entry.

        path is a path or the empty str and separators is a list
        of separators.

        """
        if self.ALTERNATIVE_SEP in entry:
            entries = [i.strip()
                       for i in entry.split(self.ALTERNATIVE_SEP)]
            if not entries or '' in entries:
                raise ValueError('illegal alternative entry')
            es = []
            for entry in entries:
                es.append(self._parse_entry(entry, path, separators))
            return AlternativeEntry(*es)
        elif entry.startswith('wc_'):
            name = entry.split('_', 1)[1]
            if not name:
                raise ValueError('illegal identifier for a wc entry')
            return WCPathEntry(name)
        elif entry.startswith('plain_'):
            name = entry.split('_', 1)[1]
            if not name:
                raise ValueError('illegal identifier for a plain entry')
            return PlainEntry(name)
        e = ComponentEntry(path)
        m = re.match(OscArgs.APIURL_RE, entry)
        if m is not None:
            api = m.group(1) or ''
            e.append(Component(api, separators, api=True))
            entry = re.sub(OscArgs.APIURL_RE, '', entry)
        for sep, component in self._parse_component(entry, separators):
            r = Component(component, separators, left_sep=sep)
            e.append(r)
        return e

    def unresolved(self, info, name):
        """Resolve unresolved components "manually".

        Subclasses may override this method to assign a
        default value to a unresolved component.

        """
        pass

    def _check_resolved(self, info, resolved):
        """Check for unresolved components.

        If a component is not resolved (that is its value in the
        resolved dict is None) the unresolved method is called
        which can assign a default value (for instance). It is
        up to the implementation of the unresolved method whether
        the unresolved component is added to the info object or not.
        All resolved data is added to the info object.

        """
        unresolved = []
        for k, v in resolved.iteritems():
            if v is None:
                unresolved.append(k)
            else:
                info.add(k, v)
        for name in unresolved:
            self.unresolved(info, name)

    def _resolve(self, args, use_wc=False, path=''):
        entries = self._entries[:]
        args = list(args)
        info = ResolvedInfo(self._ignore_clashes)
        while args:
            arg = args.pop(0)
            self._logger.debug("argument: " + arg)
            if not entries:
                raise ValueError('Too many args')
            entry = entries.pop(0)
            self._logger.debug("entry: %s" % entry)
            resolved = None
            if use_wc:
                resolved = entry.wc_resolve(path)
            if resolved is not None:
                # push arg back unless arg == ''
                if arg:
                    args.insert(0, arg)
                self._check_resolved(info, resolved)
                continue
            resolved = entry.match(arg)
            if resolved is None:
                msg = "'%s' and %s do not match" % (arg, entry)
                raise ValueError(msg)
            self._check_resolved(info, resolved)
        if entries:
            raise ValueError('Too few args')
        return info

    def resolve(self, *args, **kwargs):
        """Resolve each entry in *args.

        If an entry cannot be resolved a ValueError is
        raised. Otherwise a ResolvedInfo object is returned.

        Keyword arguments:
        path -- if specified it overrides the path which was passed
                to __init__ (default: '')

        """
        try:
            info = self._resolve(args, use_wc=False)
        except ValueError:
            path = kwargs.pop('path', '')
            info = self._resolve(args, use_wc=True, path=path)
        return info
