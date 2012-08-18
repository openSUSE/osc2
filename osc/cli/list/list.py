"""Provides various functions for the "list" command."""

from osc.cli.cli import illegal_options
from osc.source import Project, Package


PRJ_PKG_LIST_TEMPLATE = 'list/list_prj_pkg.jinja2'
FILE_LIST_TEMPLATE = 'list/list_file.jinja2'


def list(renderer, project, package, info):
    """Lists projects, packages or files."""
    if package is not None:
        list_package(renderer, project, package, info)
    else:
        list_project_or_all(renderer, project, info)


@illegal_options('deleted')
def list_package(renderer, project, package, info):
    """Lists package contents.

    illegal options: --%(opt)s is not supported at package level.

    """
    global FILE_LIST_TEMPLATE
    pkg = Package(project, package)
    query = {'apiurl': info.apiurl, 'rev': info.revision}
    if info.expand:
        query['expand'] = '1'
    if info.deleted:
        query['deleted'] = '1'
    if info.meta:
        query['meta'] = '1'
    directory = pkg.list(**query)
    renderer.render(FILE_LIST_TEMPLATE, directory=directory, info=info)


@illegal_options('verbose', 'expand', 'meta', revision='latest')
def list_project_or_all(renderer, project, info):
    """Lists projects content or all projects.

    illegal options: --%(opt)s is not supported at project or global level.

    """
    global PRJ_PKG_LIST_TEMPLATE
    if project is None:
        # FIXME: this is a bit hacky - better use a SourceListing class
        project = ''
    query = {'apiurl': info.apiurl}
    if info.deleted:
        query['deleted'] = '1'
    prj = Project(project)
    directory = prj.list(**query)
    renderer.render(PRJ_PKG_LIST_TEMPLATE, directory=directory, info=info)
