"""This module provides a wrapper around the build script.

It can be used to perform a local build.
"""

import subprocess


def su_cmd(cmd, options):
    """Constructs a new command str which invokes cmd with su.

    The options are options for cmd.

    """
    l = ['su', '--shell', escape(cmd), 'root', '--']
    return l + options


def sudo_cmd(cmd, options):
    """Constructs a new command list which invokes cmd with su.

    The options are an options list for cmd.

    """
    l = ['sudo', escape(cmd)]
    return l + options


def escape(value):
    """Escapes value.

    This method simply puts double quotes around value (unless it is
    an int).

    """
    try:
        return str(int(value))
    except ValueError:
        pass
    # ok it is a string
    return '"' + value + '"'


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


class Builder(object):
    """Wrapper around the build script."""

    # constants for the suwrapper
    SU = 'su'
    SUDO = 'sudo'

    def __init__(self, build_cmd='/usr/bin/build', su_cmd='su', **opts):
        """Constructs a new Builder object.

        Keyword arguments:
        build_cmd -- name or path to the build script (default: /usr/bin/build)
        su_cmd -- specifies which suwrapper should be used (if None is
                  specified no suwrapper is used) (default: Builder.SU)
        **opts -- options for the build script

        """
        super(Builder, self).__init__()
        self.__dict__['_build_cmd'] = build_cmd
        self.__dict__['_su_cmd'] = su_cmd
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
        """Returns the option list.

        Note all values except ints will be escaped with double
        quotes.

        """
        l = []
        for opt in sorted(self._options.keys()):
#            print opt, self._options[opt]
            for val in self._options[opt]:
                l.append("--%s" % opt.replace('_', '-'))
                if val != True:
                    # option has a value
                    l.append(escape(val))
        return l

    def cmd(self):
        """Returns the complete cmd list."""
        cmd = ''
        if self._su_cmd == Builder.SU:
            return su_cmd(self._build_cmd, self.opts())
        elif self._su_cmd == Builder.SUDO:
            return sudo_cmd(self._build_cmd, self.opts())
        return [self._build_cmd] + self.opts()

    def run(self, **kwargs):
        """Executes the build script.

        The retcode of the build script is returned.

        Keyword arguments:
        **kwargs -- optional arguments for the subprocess.call method

        """
        # make sure shell is disabled (for security reasons)
        kwargs['shell'] = False
        return subprocess.call(self.cmd(), **kwargs)

    def __delattr__(self, name):
        self.set(name, None)

    def __getattr__(self, name):
        return self._options[name]

    def __setattr__(self, name, value):
        if not hasattr(value, 'clear'):
            # otherwise it's a ListDelegate
            self.set(name, value)
