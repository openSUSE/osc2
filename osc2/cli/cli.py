"""Main entry point for the cli module."""

import os
import inspect
import logging
import urlparse
from ConfigParser import SafeConfigParser

from osc2.core import Osc
from osc2.cli import plugin
from osc2.cli.description import CommandDescription
from osc2.cli import render
from osc2.cli import parse


# TODO: move this into a different module
class UserAbort(Exception):
    """Exception is raised if user decides to abort."""


# TODO: move into config module
def _init(apiurl):
    """Initialize osc library.

    apiurl is the apiurl which should be used.

    """
    conf_filename = os.environ.get('OSC_CONFIG', '~/.oscrc')
    conf_filename = os.path.expanduser(conf_filename)
    cp = SafeConfigParser({'plaintext_password': True, 'aliases': ''})
    cp.read(conf_filename)
    apiurl = apiurl.strip('/')
    if apiurl == 'api':
        apiurl = 'https://api.opensuse.org'
    for section in cp.sections():
        aliases = cp.get(section, 'aliases', raw=True)
        aliases = aliases.split(',')
        if section.strip('/') == apiurl or apiurl in aliases:
            user = cp.get(section, 'user', raw=True)
            password = None
            if cp.has_option(section, 'pass'):
                password = cp.get(section, 'pass', raw=True)
            if cp.has_option(section, 'passx'):
                password = cp.get(section, 'pass', raw=True)
                password = password.decode('base64').decode('bz2')
            if (cp.has_option(section, 'keyring')
                    and cp.getboolean(section, 'keyring')):
                try:
                    import keyring
                    host = urlparse.urlparse(apiurl).hostname
                    password = keyring.get_password(host, user)
                except ImportError:
                    msg = ("keyring module not available but '%s' "
                           "stores password there") % conf_filename
                    raise ValueError(msg)
            if password is None:
                msg = "No password provided for %s" % section
                raise ValueError(msg)
            if '://' not in section:
                section = 'https://{0}'.format(section)
            Osc.init(section, username=user, password=password)
            return section


# base class for all osc toplevel commands
class OscCommand(CommandDescription):
    """open Build Service commandline tool"""


def illegal_options(*args, **kwargs):
    """Decorator which checks that certain options are not specified.

    *args is a tuple of illegal options. Each of them is checked
    whether "not opt" evaluates to True (if not an invalid option
    was specified).
    **kwargs is option name, value mapping. If opt != value
    evaluates to True an illegal option was specified.
    If an illegal option was specified a ValueError is raised.

    """
    def decorate(f):
        def checker(*f_args, **f_kwargs):
            def parse_illegal_options_doc(doc):
                doc = (doc or '').splitlines()
                res = []
                while doc:
                    cur = doc.pop(0).strip()
                    if cur.startswith('illegal options:'):
                        res.append(cur)
                        while doc:
                            cur = doc.pop(0).strip()
                            if cur:
                                res.append(cur)
                            else:
                                break
                        break
                return '\n'.join(res)
            params = inspect.getargspec(f)[0]
            if 'info' not in params:
                return f(*f_args, **f_kwargs)
            i = params.index('info')
            info = f_kwargs.get('info', f_args[i])
            for opt in args:
                if info.get(opt):
                    msg = parse_illegal_options_doc(f.__doc__) % {'opt': opt}
                    raise ValueError(msg)
            for opt, value in kwargs.iteritems():
                if info.get(opt) != value:
                    msg = parse_illegal_options_doc(f.__doc__) % {'opt': opt}
                    raise ValueError(msg)
            return f(*f_args, **f_kwargs)
        checker.func_name = f.func_name
        return checker
    return decorate


def import_ui():
    """Imports the commands"""
    import osc2.cli.request.ui
    import osc2.cli.review.ui
    import osc2.cli.list.ui
    import osc2.cli.checkout.ui
    import osc2.cli.update.ui
    import osc2.cli.commit.ui
    import osc2.cli.status.ui


def call(func):
    """Calls function func.

    The actual parameters from info are bound to func's
    formal parameters.

    """
    def call_func(info):
        kwargs = {}
        args, _, _, defaults = inspect.getargspec(func)
        if defaults is None:
            defaults = []
        if 'info' in args:
            kwargs['info'] = info
            args.remove('info')
        if 'renderer' in args:
            kwargs['renderer'] = renderer()
            args.remove('renderer')
        required_args = args[:len(args) - len(defaults)]
        for arg in args:
            # skip self and cls - that's just a convention
            if arg in ('self', 'cls'):
                continue
            if arg not in info and arg in required_args:
                msg = ("cannot call \"%s\": cannot bind \"%s\" parameter"
                       % (func.__name__, arg))
                raise ValueError(msg)
            kwargs[arg] = info.get(arg)
        return func(**kwargs)
    call_func.__doc__ = func.__doc__
    return staticmethod(call_func)


def renderer():
    """Sets up and returns an Renderer object."""
    if not hasattr('renderer', 'renderer'):
        # FIXME: this is a bit hacky and won't work in
        # a normal "deployment"
        path = os.path.dirname(render.__file__)
        renderer.renderer = render.Renderer(path)
    return renderer.renderer


def execute_alias(cmd, args):
    """Executes the "cmd args".

    cmd is the command and args are optional (user specified)
    arguments.

    """
    if hasattr(args, 'extend'):
        args = ' '.join(args)
    cmd = "%s %s" % (cmd, args)
    execute(tuple(cmd.split()))


class TextualAlias(object):
    """This class can be used to define a textual alias.

    A textual alias is an alias for an existing command + options.
    In order to define a textual alias a new class has to be created
    and has to inherit from this class and from OscCommand or a subclass.

    It is important that this class precedes the OscCommand (or subclass)
    class in the linearization of the new class. Otherwise this class'
    add_arguments method is not called.
    Example:
        class Correct(TextualAlias, SomeOscCommand): pass
        class Wrong(SomeOscCommand, TextualAlias): pass

    """

    args = '(plain_args)R'
    alias = ''
    func = call(execute_alias)

    @classmethod
    def add_arguments(cls, parser):
        cls.func_defaults = {'cmd': cls.alias}
        super(TextualAlias, cls).add_arguments(parser)

    @staticmethod
    def fromstring(cmd, alias, help_str=''):
        """Builds a textual alias from a str.

        cmd is the name of new command and alias is the command
        which should be executed.

        Keyword arguments:
        help_str -- an optional help str which is displayed to the user
                    (default: "<cmd>: alias for <alias>")

        """
        name = cmd.title() + 'Alias'
        bases = (TextualAlias, CommandDescription, OscCommand)
        if not help_str:
            help_str = "%s: alias for %s" % (cmd, alias)
        attrs = {'cmd': cmd, 'alias': alias, 'help_str': help_str,
                 '__module__': __name__}
        cls = type(name, bases, attrs)


def execute(args=None):
    """Executes a command specified by args.

    Keyword arguments:
    args -- represents the command to be executed (default: None
            that is the command is read from stdin)

    """
    info = parse.parse(OscCommand, args)
    apiurl = 'api'
    if 'apiurl' in info:
        apiurl = info.apiurl
    info.set('apiurl', _init(apiurl))
    info.func(info)


def main(args=None):
    """Main entry point for CLI."""
    import_ui()
    plugin.load_plugins()
    logger = logging.StreamHandler()
    logger.setLevel(logging.DEBUG)
    logging.getLogger('osc.httprequest').addHandler(logger)
    logging.getLogger('osc.httprequest').setLevel(logging.DEBUG)
    logging.getLogger('osc.cli.request.request').addHandler(logger)
    logging.getLogger('osc.cli.request.request').setLevel(logging.DEBUG)
    logging.getLogger('osc.cli.review.review').addHandler(logger)
    logging.getLogger('osc.cli.review.review').setLevel(logging.DEBUG)
    logging.getLogger('osc.cli.description').addHandler(logger)
    logging.getLogger('osc.cli.description').setLevel(logging.WARN)
    execute(args)

if __name__ == '__main__':
    main()
