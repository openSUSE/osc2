"""Provides classes and methods for defining commands in descriptive way.

The syntax for defining a command is similar to defining models in the django
framework (that's what inspired me).

Note: the CommandDescription classes must have "unique" names. In order to
achieve this chose a naming like this: <Command name><Subcommand name>. If
you specialize a command or subcommand use My<Command name> or
My<Command name><Subcommand name>. It will lead to errors/unexpected behaviour
if 2 classes from different modules have the same name.

"""

import textwrap
import inspect

import argparse


def commands():
    """Returns a function attribute dict.

    The dict maps a class name to a list of CommandDescription
    classes (that is it maps a command to a list of subcommands).

    """
    if not hasattr(commands, 'subcmds'):
        commands.subcmds = {}
    return commands.subcmds


class SubcommandFilterMeta(type):
    """Determine the "parent" command for a CommandDescription subclass."""

    filter_cls = None

    def __new__(cls, name, bases, attrs):
        if name == 'CommandDescription':
            return super(SubcommandFilterMeta, cls).__new__(cls, name, bases,
                                                            attrs)
        if cls.filter_cls is None:
            raise ValueError('filter_cls must not be None')
        real_bases, parent_cmds, ext_alias_cmd = cls._calculate_bases(bases)
        # check if we extend or alias an existing command
        extends_cmd = False
        if ext_alias_cmd and not 'cmd' in attrs:
            extends_cmd = True
        descr = super(SubcommandFilterMeta, cls).__new__(cls, name,
                                                         tuple(real_bases),
                                                         attrs)
        if extends_cmd:
            # replace with specialized description
            cls._replace_with_specialized(parent_cmds[0], descr)
        elif ext_alias_cmd:
            # append alias
            cls._append_alias(parent_cmds[0], descr)
        else:
            cls._append_subcommand(parent_cmds, descr)
        return descr

    @classmethod
    def _calculate_bases(cls, bases):
        """Calculates the real base and the parent command classes.

        bases is a list of base classes. A real base class is a base
        class which is used for inheritance and not for building a
        command <-> subcommand hierarchy (such a class is called
        parent command class).
        It returns the triple: real_bases, parent_cmds, ext_alias_cmd.
        ext_alias_cmd is either True or False. True indicates that this
        command either extends/specializes or aliases an (existing)
        command.

        A ValueError is raised if the class to be defined does not
        extends/specializes a command and cls.filter_cls is not part
        of the _direct_ inheritance hierarchy (this represents an
        invalid situation).

        """
        real_bases = []
        parent_cmds = []
        filter_subs = [base for base in bases
                       if issubclass(base, cls.filter_cls)]
        # just a small sanity check: it makes no sense to extend multiple
        # commands
        if len(filter_subs) != 1 and not cls.filter_cls in filter_subs:
            raise ValueError('exactly one cmd can be extended or aliased')
        ext_alias_cmd = (len(filter_subs) == 1
                         and not cls.filter_cls in filter_subs)
        for base in bases:
            if (base.__name__ == cls.filter_cls.__name__
                or ext_alias_cmd
                or not issubclass(base, cls.filter_cls)):
                real_bases.append(base)
            else:
                parent_cmds.append(base)
        if ext_alias_cmd:
            parent_cmds = filter_subs
        return real_bases, parent_cmds, ext_alias_cmd

    @classmethod
    def _replace_with_specialized(cls, base_cls, specialized_cls):
        """Replaces base_cls with specialized_cls in the commands mapping.

        base_cls is the base class of the specialized class
        specialized_cls.

        """
        name = base_cls.__name__
        for v in commands().itervalues():
            names = [base.__name__ for base in v]
            if name in names:
                i = names.index(name)
                v.pop(i)
                v.insert(i, specialized_cls)

    @classmethod
    def _append_alias(cls, base_cls, alias_cls):
        """Appends alias_cls to all lists where base_cls is present."""
        name = base_cls.__name__
        for v in commands().itervalues():
            names = [base.__name__ for base in v]
            if name in names:
                v.append(alias_cls)

    @classmethod
    def _append_subcommand(cls, parent_cmds, descr):
        """Appends descr to the subcommand list for each parent.

        parent_cmds is the list of parent classes. descr is
        the newly defined subcommand class. If descr.__name__
        is already present in a subcommand list no append is
        done.

        """
        for parent_cmd in parent_cmds:
            name = parent_cmd.__name__
            names = [s.__name__ for s in commands().setdefault(name, [])]
            if not descr.__name__ in names:
                commands()[name].append(descr)


class CommandDescription(object):
    # cannot use docstr here
    # Describe a command in a descriptive manner

    __metaclass__ = SubcommandFilterMeta

    cmd = None
    args = None
    # list which contains indices of optional positional args
    # (use case: the cmd is context sensitive so a positional argument
    # can be omitted)
    args_opt = None
    use_wc = False  # set to True if command is context sensitive
    help_str = None
    func = None  # function/callable which should be executed
    func_defaults = None  # kwargs mapping for default params

    @classmethod
    def add_arguments(cls, parser):
        """Add arguments to the parser.

        The parser is an argparse.ArgumentParser (or subparser)
        instance.
        Additionally options and subcommands are added to the
        parser parser.

        """
        defaults = {'oargs': [], 'oargs_use_wc': cls.use_wc,
                    'func': cls.func, 'func_defaults': cls.func_defaults}
        if cls.args is not None:
            oargs = cls.args.split()
            oargs_opt = cls._optional_arguments(oargs)
            defaults['oargs'] = oargs
            parser.set_defaults(**defaults)
            for arg in oargs:
                kwargs = {}
                if arg in oargs_opt:
                    # default value is the empty str (so it's still parsable
                    # by the oscargs module)
                    kwargs = {'nargs': '?', 'default': ''}
                parser.add_argument(arg, **kwargs)
        elif cls.func is not None:
            # TODO: investigate why it does not work with a simple
            #       else
            parser.set_defaults(**defaults)
        cls._add_options(parser)
        cls._add_subcommands(parser)

    @classmethod
    def _optional_arguments(cls, oargs):
        """Returns a list which contains optional arguments.

        oargs is a list of oargs str.
        A ValueError is raised if cls.args_opt references an
        index which does not fit into oargs' bounds.

        """
        args_opt = []
        for i in cls.args_opt or []:
            try:
                args_opt.append(oargs[i])
            except IndexError:
                msg = "args_opt: illegal index '%s' (out of bounds)" % i
                raise ValueError(msg)
        return args_opt

    @classmethod
    def _options(cls):
        """Yields a Option instance (if available)."""
        for key, _ in inspect.getmembers(cls):
            if key.startswith('opt_'):
                yield getattr(cls, key)

    @classmethod
    def _mutex_groups(cls, parser):
        """Yields a MutexGroup instance (if available).

        parser is the parser.

        """
        for key, _ in inspect.getmembers(cls):
            if key.startswith('mutex_'):
                mutex_group = getattr(cls, key)
                if hasattr(mutex_group, 'extend'):
                    # rewrite from list to MutexGroup instance
                    data = key.split('_')  # at least 2 elements
                    required = data[1] == 'req'
                    mutex_group = MutexGroup(mutex_group, parser, required)
                    setattr(cls, key, mutex_group)
                # the parser object might have changed
                # (for instance if add_arguments is called multiple times with
                # different parser instances)
                mutex_group.set_parser(parser)
                yield mutex_group

    @classmethod
    def _mutexgroup_or_parser(cls, opt, parser):
        """Returns an argparse mutually exclusive group or parser.

        opt is an Option instance and parser is the parser.

        """
        for mutex_group in cls._mutex_groups(parser):
            if opt in mutex_group:
                return mutex_group.group()
        return parser

    @classmethod
    def _add_options(cls, parser):
        """Adds options to the parser parser."""
        for opt in cls._options():
            if opt is None:
                # ignore (probably inherited) option
                continue
            p = cls._mutexgroup_or_parser(opt, parser)
            p.set_defaults(**opt.parse_info())
            p.add_argument(*opt.options(), **opt.kwargs)

    @classmethod
    def _add_subcommands(cls, parser):
        """Adds subcommands to the parser parser."""
        # add subcommands
        subcmds = commands().get(cls.__name__, [])
        if subcmds:
            subparsers = parser.add_subparsers()
            for sub_cls in subcmds:
                descr = sub_cls.description()
                kw = {'description': sub_cls.description(),
                      # keep indention and newlines in docstr
                      'formatter_class': argparse.RawDescriptionHelpFormatter}
                if sub_cls.help() is not None:
                    kw['help'] = sub_cls.help()
                subparser = subparsers.add_parser(sub_cls.cmd, **kw)
                sub_cls.add_arguments(subparser)

    @classmethod
    def description(cls):
        """Returns a description str or None."""
        if cls.__doc__ is None:
            return None
        return textwrap.dedent(cls.__doc__)

    @classmethod
    def help(cls):
        """Returns a help str or None.

        If cls.help_str is None it is tried to
        extract the first line from cls.description().

        """
        if cls.help_str is not None:
            return cls.help_str
        descr = cls.description()
        if descr is None:
            return None
        l = descr.splitlines()
        if l:
            return l[0]
        return None


SubcommandFilterMeta.filter_cls = CommandDescription


class Option(object):
    """Encapsulates data for an option."""

    def __init__(self, shortname, fullname, help='', oargs=None, **kwargs):
        """Creates a new Option object.

        shortname is the shortname and fullname the fullname of an
        option. The leading dash has to be ommitted.

        Keyword arguments:
        help -- an optional description for the option (default: '')
        oargs -- an optional oargs str (default: None)
        **kwargs -- optional arguments argparse's add_argument method

        """
        self.name = fullname
        self.shortname = ''
        if shortname:
            self.shortname = '-' + shortname
        self.fullname = '--' + fullname
        kwargs['help'] = help
        self.kwargs = kwargs
        self.oargs = oargs
        if self.oargs is not None:
            self.kwargs.setdefault('metavar', oargs)

    def parse_info(self):
        """Returns a dict.

        The dict maps an option name to an oargs str.

        """
        if self.oargs is None:
            return {}
        oargs = self.oargs.split()
        k = "opt_oargs_%s" % self.name
        return {k: oargs}

    def options(self):
        """Returns tuple.

        Either the tuple just contains the fullname or
        shortname and fullname.

        """
        if self.shortname:
            return (self.shortname, self.fullname)
        return (self.fullname, )


class MutexGroup(object):
    """Encapsulates list of mutually exclusive options."""

    def __init__(self, options, parser, required):
        """Constructs a new MutexGroup object.

        options is a list of mutually exclusive options.
        parser is the parser. If required is True it indicates
        that at exactly one option of the mutually exclusive
        group has to be specified.

        """
        self._options = options
        self._parser = parser
        self._group = None
        self._required = required

    def group(self):
        """Returns result of parser.add_mutually_exclusive_group()"""
        if self._group is None:
            kwargs = {'required': self._required}
            self._group = self._parser.add_mutually_exclusive_group(**kwargs)
        return self._group

    def set_parser(self, parser):
        """Sets the parser object."""
        if self._parser != parser:
            self._group = None
            self._parser = parser

    def __contains__(self, item):
        return item in self._options
