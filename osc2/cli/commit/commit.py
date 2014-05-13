"""Provides classes and functions to commit a wc or files in a wc."""

import os

from osc2.wc.base import TransactionListener
from osc2.wc.package import UnifiedDiff
from osc2.cli.util.env import edit_message


UPDATE_FILE_TEMPLATE = 'update/update_file.jinja2'
UPDATE_PACKAGE_TEMPLATE = 'update/update_package.jinja2'


class RendererCommitTransactionListener(TransactionListener):
    """Informs transaction via the renderer."""

    def __init__(self, renderer, *args, **kwargs):
        """Constructs a new RendererCommitTransactionListener object.

        renderer is the renderer. *args and **kwargs
        are parameters for the superclass' __init__ method.

        """
        super(RendererCommitTransactionListener, self).__init__(*args,
                                                                **kwargs)
        self._renderer = renderer

    def begin(self, name, uinfo):
        self._renderer.render_text("starting transaction: \"%s\"" % name)

    def finished(self, name, aborted=False, abort_reason=''):
        if aborted:
            text = "aborted transaction: \"%s\" - %s" % (name, abort_reason)
            self._renderer.render_text(text)
        else:
            self._renderer.render_text("finished transaction: \"%s\"" % name)

    def transfer(self, transfer_type, filename):
        text = "transfer: %s %s" % (transfer_type, filename)
        self._renderer.render_text(text)

    def processed(self, entity, new_state, old_state):
        text = "processed \"%s\": state: %s" % (entity, new_state)
        self._renderer.render_text(text)


class AppendingUnifiedDiff(UnifiedDiff):
    """Builds a (big) str representing the diff."""

    def __init__(self, *args, **kwargs):
        """Constructs a new AppendingUnifiedDiff object."""
        super(AppendingUnifiedDiff, self).__init__(*args, **kwargs)
        self.diff_data = ''

    def process(self, data):
        self.diff_data += ''.join(data)


class WCCommitController(object):
    """Can be used to commit a project or package or wc file."""

    def commit(self, renderer, path, message, info):
        """Commits path."""
        filenames = []
        todo = {}
        if path.filename is not None:
            filenames.append(path.filename)
        tl = RendererCommitTransactionListener(renderer)
        prj = path.project_obj(transaction_listener=[tl])
        pkg = None
        if prj is not None and path.package is not None:
            pkg = prj.package(path.package)
            todo[path.package] = filenames
        else:
            pkg = path.package_obj(transaction_listener=[tl])
        if message is None:
            message = self._message(pkg, filenames)
        if prj is not None:
            prj.commit(package_filenames=todo, comment=message)
        else:
            pkg.commit(*filenames, comment=message)

    def _message(self, pkg, filenames):
        """Returns a message.

        pkg is a Package instance or None.

        """
        diff = ''
        if pkg is not None:
            ud = AppendingUnifiedDiff()
            pkg.diff(ud, *filenames)
            ud.diff()
            diff = ud.diff_data
        return edit_message(footer=diff)
