"""Provides functions to show the status of a wc or file."""

import os


STATUS_FILE_TEMPLATE = 'status/status_file.jinja2'
STATUS_PACKAGE_TEMPLATE = 'status/status_package.jinja2'


def status(renderer, path, info):
    """Shows the status."""
    if path.filename is not None:
        _file_status(renderer, path.package_obj(), info, path.filename)
    elif path.package is not None:
        _package_status(renderer, None, path.package_obj(), info)
    elif path.project is not None:
        _project_status(renderer, path.project_obj(), info)


def _file_status(renderer, pkg, info, filename):
    global STATUS_FILE_TEMPLATE
    states = _package_states(pkg, filename)
    renderer.render(STATUS_FILE_TEMPLATE, states=states, info=info,
                    path_prefix='')


def _package_status(renderer, prj, pkg, info):
    global STATUS_PACKAGE_TEMPLATE
    package = pkg.name
    package_state = ''
    if prj is not None:
        package_state = prj._status(package)
    states = {}
    # pkg might be none if this is called from _project_status and
    # the package is missing  (state !)
    if pkg is not None:
        states = _package_states(pkg, path=pkg.path)
    renderer.render(STATUS_PACKAGE_TEMPLATE, states=states, package=package,
                    package_state=package_state, info=info,
                    path_prefix=pkg.name)


def _project_status(renderer, prj, info):
    global STATUS_PACKAGE_TEMPLATE
    for package in prj.packages():
        pkg = prj.package(package)
        if pkg is None:
            package_state = prj._status(package)
            renderer.render(STATUS_PACKAGE_TEMPLATE, states={},
                            package=package, package_state=package_state,
                            info=info, path_prefix='')
        else:
            _package_status(renderer, prj, prj.package(package), info)


def _package_states(pkg, *filenames, **kwargs):
    """Returns a dict.

    The dict maps a filename to state.

    Keyword arguments:
    path -- path is required if no filenames are specified (default: os.curdir)

    """
    if pkg is None:
        return {}
    if not filenames:
        filenames = pkg.files()
        # collect unversioned files and directories
        filenames.extend([i for i in os.listdir(kwargs.get('path', os.curdir))
                          if not i.startswith('.') and i not in filenames])
    return dict([[filename, pkg.status(filename)] for filename in filenames])
