"""Convert old working copy format to the new format."""

import os

from osc2.wc.project import Project
from osc2.wc.package import Package
from osc2.wc.util import (wc_read_files, wc_pkg_data_filename, _storefile,
                          _write_storefile, _VERSION, wc_read_project,
                          wc_write_project,
                          _read_storefile, wc_read_packages,
                          missing_storepaths, wc_read_apiurl,
                          wc_pkg_data_mkdir, _storedir)


def convert_package(path, ext_storedir=None, **kwargs):
    """Convert working copy to the new format.

    path is the path to the package working copy.

    Keyword arguments:
    project -- name of the project (default: '')
    package -- name of the package (default: '')
    apiurl -- apiurl is the apiurl (default: '')
    ext_storedir -- path to the external storedir (default: None)

    """
    data_path = wc_pkg_data_filename(path, '')
    if not os.path.exists(data_path):
        os.mkdir(data_path)
    project = kwargs.get('project', '')
    if missing_storepaths(path, '_project'):
        if not project:
            raise ValueError('project argument required')
        wc_write_project(path, project)
    project = wc_read_project(path)
    deleted = []
    added = []
    conflicted = []
    if os.path.exists(_storefile(path, '_to_be_deleted')):
        deleted = _read_storefile(path, '_to_be_deleted').split()
        os.unlink(_storefile(path, '_to_be_deleted'))
    if os.path.exists(_storefile(path, '_to_be_added')):
        added = _read_storefile(path, '_to_be_added').split()
        os.unlink(_storefile(path, '_to_be_added'))
    if os.path.exists(_storefile(path, '_in_conflict')):
        conflicted = _read_storefile(path, '_in_conflict').split()
        os.unlink(_storefile(path, '_in_conflict'))
    try:
        files = wc_read_files(path)
    except ValueError:
        files = None
    if files is not None:
        files._xml.set('project', project)
        for entry in files:
            filename = entry.get('name')
            store = _storefile(path, filename)
            data = wc_pkg_data_filename(path, filename)
            if os.path.exists(store):
                os.rename(store, data)
            if filename in added:
                files.set(filename, 'A')
            elif filename in deleted:
                files.set(filename, 'D')
            elif filename in conflicted:
                files.set(filename, 'C')
            else:
                files.set(filename, ' ')
        for filename in added:
            if files.find(filename) is None:
                files.add(filename, 'A')
        files.write()
    if _storefile(path, '_osclib_version'):
        os.unlink(_storefile(path, '_osclib_version'))
    if ext_storedir is not None:
        # move all files to the new location
        storedir = _storedir(path)
        for filename in os.listdir(_storefile(path, '')):
            old = os.path.join(storedir, filename)
            new = os.path.join(ext_storedir, filename)
            os.rename(old, new)
        os.rmdir(storedir)
        os.symlink(os.path.relpath(ext_storedir, path), storedir)
    Package.repair(path, ext_storedir=ext_storedir, **kwargs)


def convert_project(path, project='', apiurl='', **package_states):
    """Convert working copy to the new format.

    path is the path to the project working copy.

    Keyword arguments:
    project -- the name of the project (default: '')
    apiurl -- the apiurl of the project (default: '')
    **package_states -- a package to state mapping (default: {})

    """
    Project.repair(path, project=project, apiurl=apiurl, no_packages=True,
                   **package_states)
    _write_storefile(path, '_version', str(_VERSION))
    project = wc_read_project(path)
    apiurl = wc_read_apiurl(path)
    packages = wc_read_packages(path)
    for entry in packages:
        package = entry.get('name')
        package_path = os.path.join(path, package)
        storedir = wc_pkg_data_mkdir(path, package)
        convert_package(package_path, project=project, package=package,
                        apiurl=apiurl, ext_storedir=storedir)
