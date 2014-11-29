"""Provides classes and functions to update a wc."""

from osc2.wc.base import TransactionListener


UPDATE_FILE_TEMPLATE = 'update/update_file.jinja2'
UPDATE_PACKAGE_TEMPLATE = 'update/update_package.jinja2'


class RendererUpdateTransactionListener(TransactionListener):
    """Informs transaction via the renderer."""

    def __init__(self, renderer, prj=None, pkg=None, *args, **kwargs):
        """Constructs a new RendererUpdateTransactionListener object.

        renderer is the renderer. *args and **kwargs
        are parameters for the superclass' __init__ method.

        Keyword arguments:
        prj -- an optional Project object (default: None)
        pkg -- an optional Package object (default: None)

        """
        super(RendererUpdateTransactionListener, self).__init__(*args,
                                                                **kwargs)
        self._renderer = renderer
        self._transactions = []
        self._project = ''
        self._package = ''

    def begin(self, name, uinfo):
        if name == 'prj_update':
            self._project = uinfo.name
        elif name == 'update':
            self._package = uinfo.name
        self._renderer.render_text("starting transaction: \"%s\"" % name)

    def finished(self, name, aborted=False, abort_reason=''):
        if aborted:
            text = "aborted transaction: \"%s\" - %s" % (name, abort_reason)
            self._renderer.render_text(text)
        else:
            self._renderer.render_text("finished transaction: \"%s\"" % name)
        if name == 'prj_update':
            self._project = ''
        elif name == 'update':
            self._package = ''

    def transfer(self, transfer_type, filename):
        pass

    def processed(self, entity, new_state, old_state):
        global UPDATE_FILE_TEMPLATE
        if self._package:
            self._renderer.render(UPDATE_FILE_TEMPLATE, filename=entity,
                                  new_state=new_state, old_state=old_state,
                                  package=self._package)
        elif self._project:
            self._renderer.render(UPDATE_PACKAGE_TEMPLATE, package=entity,
                                  new_state=new_state, old_state=old_state,
                                  project=self._project)


class WCUpdateController(object):
    """Can be used to update a project or package."""

    def __init__(self):
        """Constructs a new WCUpdateController instance."""
        super(WCUpdateController, self).__init__()
        self._renderer = None

    def update(self, renderer, path, info):
        """Updates a project or a list of packages"""
        self._renderer = renderer
        tl = RendererUpdateTransactionListener(self._renderer)
        prj = path.project_obj(transaction_listener=[tl])
        if prj is not None:
            packages = []
            if path.package is not None:
                packages.append(path.package)
            self._update_project(prj, info, *packages)
        else:
            pkg = path.package_obj(transaction_listener=[tl])
            self._update_package(pkg, info)

    def _update_project(self, prj, info, *packages):
        """Updates a project wc."""
        query = self._build_query(info)
        prj.update(*packages, **query)

    def _update_package(self, pkg, info):
        """Updates a package wc."""
        query = self._build_query(info)
        pkg.update(**query)

    def _build_query(self, info):
        """Builds query dict."""
        query = {}
        if not info.unexpand:
            query['expand'] = '1'
        if info.revision is not None:
            query['revision'] = info.revision
        return query
