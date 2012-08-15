"""This module provides a class to parse/resolve osc url-like
arguments.

Some notes about terminology:
 'foo/bar' is called an entry. The entry 'foo/bar' consists of
 two components; the first component is 'foo' and the second
 component is 'bar'.
 'api://project/package?' is also an entry which consists of 3
 components; the first component is 'api://', the second is 'project'
 and the third component is 'package'. The '?' indicates that
 'package' is an optional component

"""

import re
import urlparse
import logging

from osc.wc.util import (wc_is_project, wc_is_package, wc_read_project,
                         wc_read_package, wc_read_apiurl)


class ResolvedInfo(object):
    """Encapsulate resolved arguments"""

    def __init__(self):
        super(ResolvedInfo, self).__init__()
        self._data = {}

    def add(self, name, value):
        """Add additional components.

        name is the name of the component and value
        the actual value.
        Note: if a component already exists it will
        be overriden with the new value.

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


class Entry(object):
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
        super(Entry, self).__init__()
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


class OscArgs(object):
    """Resolves url-like arguments into its components.

    Note: to avoid name clashes when defining 2 or more api entries
    use the following syntax:
     'api://project', 'api(tgt)://tgt_project/tgt_package'
    The ResolvedInfo object will contain a "apiurl" and a
    "tgt_apiurl" attribute.

    """
    APIURL_RE = "api\(?([^)]+)?\)?://"

    def __init__(self, *format_entries, **kwargs):
        """Constructs a new OscArgs instance.

        *format_entries contains the formatting entries.

        Keyword arguments:
        path -- path to a project or package working copy
                (default: ''). path might be used for component
                resolving.
        separators -- list of component separators (default: ['/', '@'])

        """
        super(OscArgs, self).__init__()
        self._logger = logging.getLogger(__name__)
        self._entries = []
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
                format_entry = format_entry[i+1:]
                i = 0
            i += 1
        # no separator left
        yield left_sep, format_entry

    def _parse_entries(self, format_entries, path, separators):
        """Parse each entry and each component into a Entry or
        Component object.

        """
        for entry in format_entries:
            e = Entry(path)
            m = re.match(OscArgs.APIURL_RE, entry)
            if m is not None:
                api = m.group(1) or ''
                e.append(Component(api, separators, api=True))
                entry = re.sub(OscArgs.APIURL_RE, '', entry)
            for sep, component in self._parse_component(entry, separators):
                r = Component(component, separators, left_sep=sep)
                e.append(r)
            self._entries.append(e)

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
        info = ResolvedInfo()
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
