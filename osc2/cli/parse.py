"""Provides methods and classes for parsing the commandline options."""

import os

import argparse

from osc2.oscargs import OscArgs


class CustomOscArgs(OscArgs):
    """A custom OscArgs class.

    Adds "unresolved" arguments to the info object.

    """
    def unresolved(self, info, name):
        info.add(name, None)


class _OscNamespace(argparse.Namespace):
    """Resolves osc url-like arguments."""

    def _path(self):
        """Returns a path.

        If the command is not context sensitive None
        is returned.

        """
        path = None
        if self.oargs_use_wc:
            path = os.getcwd()
        return path

    def _add_items(self, info):
        """Add parsed items to the info object."""
        if self.func_defaults is not None:
            for k, v in self.func_defaults.iteritems():
                info.add(k, v)
        # add options etc. to info object
        for i in self.__dict__.keys():
            if (i.startswith('oargs') or i in info or i in self.oargs
                    or i == 'func_defaults'):
                continue
            elif i.startswith('opt_oargs_'):
                self._resolve_option(info, i)
            else:
                info.add(i, getattr(self, i))

    def _resolve_option(self, info, opt):
        """Resolve parsable option

        info is the info object and opt an
        attribute of the info object.

        """
        name = opt.split('_', 2)[2]
        args = getattr(self, name)  # specified options (by the user)
        format_entries = getattr(self, opt)
        if not hasattr(args, 'extend'):
            msg = ('list expected: please set "nargs" in the option '
                   'definition and/or default=[]')
            raise ValueError(msg)
        if not args:
            # no args specified - nothing to parse
            return
        # check if the option was defined with action='append'
        if not hasattr(args[0], 'extend'):
            # that is option was only specified once (no action='append')
            # it should also hold len(args) == len(format_entries)
            args = [args]
        for arg in args:
            if len(arg) % len(format_entries) != 0:
                msg = ('unexpected args len: the option args should be an '
                       'integer multiple of the number of specified '
                       'format_entries')
                raise ValueError(msg)
        # everything looks good - start parsing
        res = []
        oargs = CustomOscArgs(*format_entries)
        while args:
            cur = args.pop(0)
            res.append(oargs.resolve(*cur, path=self._path()))
        # use set to overwrite the old list
        info.set(name, res)

    def _resolve_positional_args(self):
        """Resolve positional arguments.

        A ResolvedInfo object is returned. If it is not
        possible to resolve the positional arguments a
        ValueError is raised.

        """
        args = []
        format_entries = []
        for oarg in self.oargs:
            val = getattr(self, oarg, '')
            if hasattr(val, 'extend'):
                # len(val) arguments of "type" oarg
                # were specified by the user
                format_entries.extend([oarg] * len(val))
                args.extend(val)
            else:
                format_entries.append(oarg)
                args.append(val)
        oargs = CustomOscArgs(*format_entries, ignore_clashes=False)
        return oargs.resolve(*args, path=self._path())

    def resolve(self):
        """Resolve osc url-like arguments."""
        info = self._resolve_positional_args()
        self._add_items(info)
        return info


def _parser(root_cmd_cls):
    """Sets up and returns a new ArgumentParser object.

    root_cmd_cls specifies the root command class which is
    used to initialize the parser.

    """
    parser = argparse.ArgumentParser(description=root_cmd_cls.__doc__)
    root_cmd_cls.add_arguments(parser)
    return parser


def parse(root_cmd_cls, args):
    """Parses arguments specified by args

    If args is None sys.stdin is used. root_cmd_cls specifies
    the root command class which is used for setting up the
    argparse parser.
    An osc2.oscargs.ResolvedInfo object is returned. If the
    passed arguments cannot be resolved a ValueError is raised.

    """
    parser = _parser(root_cmd_cls)
    ns = _OscNamespace()
    parser.parse_args(args=args, namespace=ns)
    return ns.resolve()
