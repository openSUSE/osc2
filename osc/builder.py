"""This module provides a wrapper around the build script.

It can be used to perform a local build.
"""

import os
import subprocess


def su_cmd(cmd, options):
    """Constructs a new command str which invokes cmd with su.

    The options are options for cmd.

    """
    l = ['su', '--shell', cmd, 'root', '--']
    return l + options


def sudo_cmd(cmd, options):
    """Constructs a new command list which invokes cmd with su.

    The options are an options list for cmd.

    """
    l = ['sudo', cmd]
    return l + options


def hostarch():
    """Returns the hostarch of the machine."""
    # XXX: no testcases exist for this method
    arch = os.uname()[4]
    if arch == 'i686':
        return 'i586'
    elif arch == 'parisc':
        return 'hppa'
    return arch


class ListDelegate(object):
    """Delegate for a list.

    It's sole purpose is to simplify the Builder interface
    so that multiple options can be specified like this:
    builder.foo = 'foo'
    builder.foo += 'bar'

    """

    def __init__(self):
        """Constructs a new ListDelegate object"""
        self.clear()

    def clear(self):
        """Clears the list"""
        self._list = []

    def __iadd__(self, other):
        if hasattr(other, 'extend'):
            # treat other as list
            self._list.extend(other)
        else:
            self._list.append(other)
        return self

    def __getattr__(self, name):
        return getattr(self._list, name)

    def __iter__(self):
        return iter(self._list)


def can_build(hostarch, buildarch, cando):
    """Checks whether hostarch can build buildarch.

    hostarch is the arch of the buildhost and buildarch is
    the arch of the resulting binary _or_ the arch which
    is needed for building.
    cando is a dict. If no hostarch key exists in cando
    a ValueError is raised.
    True is returned if the hostarch can build the buildarch.
    Otherwise False is returned.

    """
    if not hostarch in cando.keys():
        raise ValueError("hostarch \"%s\" is not supported" % hostarch)
    return buildarch in cando[hostarch].keys()


def build_helper(hostarch, buildarch, cando):
    """Returns a build helper to build buildarch on hostarch.

    hostarch is the arch of the buildhost and buildarch is
    the arch of the resulting binary _or_ the arch which
    is needed for building.
    cando is a dict. If no hostarch key exists in cando
    a ValueError is raised. A ValueError is raised if hostarch
    cannot build buildarch.
    Either a helper is returned or the empty str if no
    helper is needed.

    """
    if not can_build(hostarch, buildarch, cando):
        msg = "hostarch \"%s\" cannot build buildarch \"%s\"" % (hostarch,
                                                                 buildarch)
        raise ValueError(msg)
    return cando[hostarch][buildarch]


# maps hostarch to a dict of supported buildarches which maps the
# supported arch to a "build helper" (like linux32) or to the empty str ''
CANDO = {'i586': {'i586': ''},
         'i686': {'i686': '', 'i586': ''},
         'x86_64': {'x86_64': '', 'i586': 'linux32', 'i686': 'linux32'},
         'ppc': {'ppc': ''},
         'ppc64': {'ppc64': '', 'ppc': 'powerpc32'},
         'ia64': {'ia64': ''}}


class Builder(object):
    """Wrapper around the build script."""

    # constants for the suwrapper
    SU = 'su'
    SUDO = 'sudo'

    def __init__(self, build_cmd='/usr/bin/build', su_cmd='su',
                 buildarch=None, cando=None, **opts):
        """Constructs a new Builder object.

        A ValueError is raised if the hostarch does not support the buildarch.

        Keyword arguments:
        build_cmd -- name or path to the build script (default: /usr/bin/build)
        su_cmd -- specifies which suwrapper should be used (if None is
                  specified no suwrapper is used) (default: Builder.SU)
        buildarch -- the arch we build for or the arch which is needed for
                     building (e.g. if an ARM package should be build on a
                     x86_64 host) (default: hostarch)
        cando -- maps a hostarch to a dict of supported buildarches
                 (default: global CANDO dict)
        **opts -- options for the build script

        """
        global CANDO
        super(Builder, self).__init__()
        self.__dict__['_build_cmd'] = build_cmd
        self.__dict__['_su_cmd'] = su_cmd
        can = CANDO.copy()
        can.update(cando or {})
        harch = hostarch()
        buildarch = buildarch or harch
        self.__dict__['_build_helper'] = build_helper(harch, buildarch, can)
        self.__dict__['_options'] = {}
        for opt, val in opts.iteritems():
            self.set(opt, val)

    def set(self, opt, val, append=False):
        """Sets option opt with value val.

        If val is None the option is removed/unset. In case of a multiple
        option val can also be a list of values.

        Keyword arguments:
        append -- do not overwrite old value(s) (default: False)

        """
        if not opt in self._options:
            self._options[opt] = ListDelegate()
        values = self._options[opt]
        if val is None:
            self._options.pop(opt, None)
        elif hasattr(val, 'extend'):
            # treat val as a list
            values.extend(val)
        elif append:
            values.append(val)
        else:
            values.clear()
            values.append(val)

    def opts(self):
        """Returns the option list."""
        l = []
        for opt in sorted(self._options.keys()):
            for val in self._options[opt]:
                l.append("--%s" % opt.replace('_', '-'))
                if val != True:
                    # option has a value
                    l.append(str(val))
        return l

    def cmd(self, build_descr=None):
        """Returns the complete cmd list.

        Keyword arguments:
        build_descr -- build description (default: None)

        """
        cmd = ''
        opts = self.opts()
        if build_descr is not None:
            opts.append(build_descr)
        if self._su_cmd == Builder.SU:
            cmd = su_cmd(self._build_cmd, opts)
        elif self._su_cmd == Builder.SUDO:
            cmd = sudo_cmd(self._build_cmd, opts)
        else:
            cmd = [self._build_cmd] + opts
        # check if we need a build helper like linux32
        if self._build_helper:
            cmd = [self._build_helper] + cmd
        return cmd

    def run(self, build_descr=None, **kwargs):
        """Executes the build script.

        The retcode of the build script is returned.

        Keyword arguments:
        build_descr -- build description (default: None)
        **kwargs -- optional arguments for the subprocess.call method

        """
        # make sure shell is disabled (for security reasons)
        kwargs['shell'] = False
        return subprocess.call(self.cmd(build_descr), **kwargs)

    def __delattr__(self, name):
        self.set(name, None)

    def __getattr__(self, name):
        return self._options[name]

    def __setattr__(self, name, value):
        if not hasattr(value, 'clear'):
            # otherwise it's a ListDelegate
            self.set(name, value)
