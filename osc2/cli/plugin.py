"""Provides methods for the plugin mechanism.

The user interface can be customized/extended with the help of
plugins. Instead of inventing our own plugin mechanism we will
use python distribute's/setuptools' existing plugin mechanism.
Therefore every plugin has to packaged using python-distribute
(or python-setuptools). A detailed example how to write a custom
plugin will follow soon.

"""

import logging

import pkg_resources


OSC_UI_ENTRYPOINT = 'osc_ui'


def logger():
    """Returns a logging.Logger object."""
    return logging.getLogger(__name__)


def load_plugins():
    """Loads all ui plugins.

    If the loaded entry point provides an init method
    it is called.

    """
    global OSC_UI_ENTRYPOINT
    for ep in pkg_resources.iter_entry_points(OSC_UI_ENTRYPOINT):
        module = ep.load()
        module.init()
        logger().debug("loaded plugin: %s" % ep.name)
