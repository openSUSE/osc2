"""Main entry point for the cli module."""

import os
import inspect
import logging
from ConfigParser import SafeConfigParser

import argparse

from osc.core import Osc
from osc.oscargs import OscArgs
from osc.cli.description import CommandDescription
from osc.cli import render


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
        info.add(name, res)

    def resolve(self):
        """Resolve osc url-like arguments."""
        args = [getattr(self, k, '') for k in self.oargs]
        oargs = CustomOscArgs(*self.oargs)
        info = oargs.resolve(*args, path=self._path())
        self._add_items(info)
        return info


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
            password = cp.get(section, 'pass', raw=True)
            if cp.has_option(section, 'passx'):
                password = cp.get(section, 'pass', raw=True)
                password = password.decode('base64').decode('bz2')
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
            if not 'info' in params:
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
    import osc.cli.request.ui
    import osc.cli.review.ui
    import osc.cli.list.ui
    import osc.cli.checkout.ui
    import osc.cli.update.ui


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
            if not arg in info and arg in required_args:
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


def _parser():
    """Sets up and returns a new ArgumentParser object."""
    parser = argparse.ArgumentParser(description=OscCommand.__doc__)
    OscCommand.add_arguments(parser)
    return parser


def _parse():
    """Parses arguments from sys.stdin.

    An osc.oscargs.ResolvedInfo object is returned. If the
    pass arguments cannot be resolved a ValueError is raised.

    """
    parser = _parser()
    ns = _OscNamespace()
    parser.parse_args(namespace=ns)
    return ns.resolve()


if __name__ == '__main__':
    import_ui()
    logger = logging.StreamHandler()
    logger.setLevel(logging.DEBUG)
    logging.getLogger('osc.httprequest').addHandler(logger)
    logging.getLogger('osc.httprequest').setLevel(logging.DEBUG)
    logging.getLogger('osc.cli.request.request').addHandler(logger)
    logging.getLogger('osc.cli.request.request').setLevel(logging.DEBUG)
    logging.getLogger('osc.cli.review.review').addHandler(logger)
    logging.getLogger('osc.cli.review.review').setLevel(logging.DEBUG)
    info = _parse()
    apiurl = 'api'
    if 'apiurl' in info:
        apiurl = info.apiurl
    info.add('apiurl', _init(apiurl))
    info.func(info)
