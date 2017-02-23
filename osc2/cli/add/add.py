"""Provides functions to add packages or files to the working copy."""

from collections import Sequence

from osc2.cli.cli import illegal_options


def add(path, info):
    paths = path
    if not isinstance(paths, Sequence):
        paths = [path]
    for path in paths:
        if path.package is None and path.filename is None:
            # in this case path.project cannot be None
            msg = "package and/or filename required"
            raise ValueError(msg)
        prj = path.project_obj()
        pkg = path.package_obj()
        if pkg is not None:
            filenames = []
            if path.filename:
                filenames.append(path.filename)
            add_files(pkg, info, *filenames)
        elif prj is not None:
            add_package(prj, path.package, info)


@illegal_options('package_only')
def add_files(pkg, info, *filenames):
    """Adds the files specified via filenames to the package pkg.

    illegal options: --%(opt)s is only support on project level

    """
    if not filenames:
        raise ValueError("At least one filename is required")
    for filename in filenames:
        pkg.add(filename)


def add_package(prj, package, info):
    """Adds the specified package to the project prj.

    If info.package_only is False, all files in the package directory
    are added to the package aswell.

    """
    prj.add(package, no_files=info.package_only)
