"""Provides some utility functions to get data from a
working copy without constructing a Project or Package
instance.

"""

import os

__all__ = ['wc_is_project', 'wc_is_package', 'wc_read_project',
           'wc_read_package', 'wc_read_apiurl']

# maybe we should define this somewhere else
_STORE = '.osc'

def _storedir(path):
    """Return the storedir path"""
    global _STORE
    return os.path.join(path, _STORE)

def _storefile(path, filename):
    """Return the path to the storefile"""
    return os.path.join(_storedir(path), filename)

def _has_storedir(path):
    """Test if path has a storedir (internal function)"""
    storedir = _storedir(path)
    return os.path.isdir(path) and os.path.isdir(storedir)

def _missing_storefiles(path, *files):
    """Test if the path/storedir contains all *files.

    All missing files will be returned. If the returned
    list is empty all *files are available.

    """
    if not _has_storedir(path):
        return list(files)
    storedir = _storedir(path)
    missing = []
    for filename in files:
        storefile = os.path.join(storedir, filename)
        if not os.path.isfile(storefile):
            missing.append(filename)
    return missing

def _read_storefile(path, filename):
    """Read the content of the path/storedir/filename.

    If path/storedir/filename does not exist or is no file
    a ValueError is raised.
    Leading and trailing whitespaces, tabs etc. are stripped.

    """
    if _missing_storefiles(path, filename):
        # file does not exist or is no file
        msg = "'%s' is no valid storefile" % filename
        raise ValueError(msg)
    storefile = _storefile(path, filename)
    with open(storefile, 'r') as f:
        return f.read().strip()

def wc_is_project(path):
    """Test if path is a project working copy."""
    missing = _missing_storefiles(path, '_apiurl', '_project', '_package')
    if not missing:
        # it is a package dir
        return False
    elif len(missing) == 1 and '_package' in missing:
        return True
    return False

def wc_is_package(path):
    """Test if path is a package working copy."""
    return not _missing_storefiles(path, '_apiurl', '_project', '_package')

def wc_read_project(path):
    """Return the name of the project.

    path is the path to the project or package working
    copy.
    If the storefile does not exist or is no file
    a ValueError is raised.

    """
    return _read_storefile(path, '_project')

def wc_read_package(path):
    """Return the name of the package.

    path is the path to the package working copy.
    If the storefile does not exist or is no file
    a ValueError is raised.

    """
    return _read_storefile(path, '_package')

def wc_read_apiurl(path):
    """Return the apiurl for this working copy.

    path is the path to the project or package
    working copy.
    If the storefile does not exist or is no file
    a ValueError is raised.

    """
    return _read_storefile(path, '_apiurl')
