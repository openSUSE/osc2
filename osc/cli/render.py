"""Provides methods and classes to render templates."""

import sys

from jinja2 import Environment, FileSystemLoader


class Renderer(object):
    """Renders a template."""

    def __init__(self, path=None, loader=None):
        """Constructs a new Renderer object.

        Either path or loader has to be specified.

        Keyword arguments:
        loader -- a jinja2 template loader instance (default: None)
        path -- list or str which represents template locations

        """
        if (path is None and loader is None
            or path is not None and loader is not None):
            raise ValueError('Either specify path oder loader')
        if path is not None:
            loader = FileSystemLoader(path)
        self._env = Environment(loader=loader)
        self._env.add_extension('jinja2.ext.do')

    def _custom_template_names(self, template):
        """Returns a list of custom template names.

        template is the name of the original template.

        """
        splitted = template.rsplit('/', 1)
        name = 'custom_' + splitted[-1]
        ret = [name]
        if len(splitted) == 2:
            ret.append(splitted[0] + '/' + name)
        return ret

    def _render(self, template, out, *args, **kwargs):
        """Renders template template.

        out is a file or file-like object to which the rendered
        template should be written to.
        *args and **kwargs are passed to jinja2 Template's render
        method.

        """
        names = self._custom_template_names(template)
        names.append(template)
        tmpl = self._env.select_template(names)
        text = tmpl.render(*args, **kwargs)
        try:
            out.write(text)
        except UnicodeEncodeError:
            text = text.encode('utf-8')
            out.write(text)

    def render(self, template, *args, **kwargs):
        """Renders template template.

        Writes the rendered template to sys.stdout.
        *args and **kwargs are passed to jinja2 Template's render
        method.

        """
        self._render(template, sys.stdout, *args, **kwargs)

    def render_error(self, template, *args, **kwargs):
        """Renders template template.

        Writes the rendered template to sys.stderr.
        *args and **kwargs are passed to jinja2 Template's render
        method.

        """
        self._render(template, sys.stderr, *args, **kwargs)
