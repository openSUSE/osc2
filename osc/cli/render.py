"""Provides methods and classes to render templates."""

import sys
import datetime

from jinja2 import Environment, FileSystemLoader


TEXT_TEMPLATE = 'text.jinja2'


def dateformat(timestamp):
    """Returns formatted timestamp (isoformat)"""
    date = datetime.datetime.fromtimestamp(int(timestamp))
    return date.isoformat()


class Renderer(object):
    """Renders a template."""

    def __init__(self, path=None, loader=None, filters=None):
        """Constructs a new Renderer object.

        Either path or loader has to be specified.

        Keyword arguments:
        path -- list or str which represents template locations
        loader -- a jinja2 template loader instance (default: None)
        filters -- dict containing filters (default: {})

        """
        if (path is None and loader is None
            or path is not None and loader is not None):
            raise ValueError('Either specify path oder loader')
        if path is not None:
            loader = FileSystemLoader(path)
        self._env = Environment(loader=loader)
        self._env.add_extension('jinja2.ext.do')
        self._add_filters(filters)

    def _add_filters(self, filters):
        """Adds new filters to the jinja2 environment.

        filters is a dict of filters.

        """
        self._env.filters['dateformat'] = dateformat
        self._env.filters.update(filters or {})

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

    def render_text(self, text, *args, **kwargs):
        """Renders text.

        *args and **kwargs are passed to jinja2 Template's render
        method.

        """
        global TEXT_TEMPLATE
        self.render(TEXT_TEMPLATE, text=text, *args, **kwargs)

    def render_error(self, template, *args, **kwargs):
        """Renders template template.

        Writes the rendered template to sys.stderr.
        *args and **kwargs are passed to jinja2 Template's render
        method.

        """
        self._render(template, sys.stderr, *args, **kwargs)
