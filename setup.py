#!/usr/bin/python

import os
from setuptools import setup, find_packages
from distutils.command.build import build
from pydoc import writedoc


class BuildDocumentation(build, object):
    def _generate_docs(self):
        # FIXME: this is really hacky
        olddir = os.getcwd()
        html_dir = os.path.join('docs', 'html')
        if not os.path.exists(html_dir):
            os.makedirs(html_dir)
        os.chdir(html_dir)
        writedoc('osc2')
        os.rename('osc2.html', 'index.html')
        modules = ('build', 'core', 'httprequest', 'oscargs', 'remote',
                   'source', 'util', 'util.io', 'util.xml', 'wc', 'wc.base',
                   'wc.convert', 'wc.package', 'wc.project', 'wc.util')
        for mod in modules:
            writedoc('osc2.' + mod)
        os.chdir(olddir)

    def run(self, *args, **kwargs):
        super(BuildDocumentation, self).run(*args, **kwargs)
        self._generate_docs()


setup(name='osc2',
      description='Library for accessing the openSUSE BuildService',
      long_description=('osc2 is a library written in python to access the '
                        'openSUSE BuildService. It also provides code to '
                        'checkout projects and packages and to work with '
                        'in a VCS-like manner (commit, update, revert etc.).'),
      author='Marcus Huewe',
      author_email='suse-tux@gmx.de',
      url='http://github.com/openSUSE/osc2',
      download_url='http://github.com/openSUSE/osc2/tarball/master',
      packages=[
        'osc2', 'osc2.util', 'osc2.wc', 'osc2.cli', 'osc2.cli.util',
        'osc2.cli.request', 'osc2.cli.list', 'osc2.cli.status',
        'osc2.cli.commit', 'osc2.cli.checkout', 'osc2.cli.update',
        'osc2.cli.review',
      ],
      test_suite='test.suite',
      entry_points={'console_scripts': ['osc2 = osc2.cli.cli:main']},
      license='GPL',
      cmdclass={'build': BuildDocumentation})
