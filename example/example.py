"""Example script demonstrating the new library.

Usage:
example.py co api://project/package?
example.py up (in working copy)
example.py up 1|0 (in working copy)
example.py st (in working copy)
example.py di (in package working copy)
example.py ls api://project/package? 1|0
example.py ls 1|0 (in working copy)

1|0 enables/disables source expanding.

"""

import os
import sys
from ConfigParser import SafeConfigParser

from osc.core import Osc
from osc.oscargs import OscArgs
from osc.source import Package as SourcePackage
from osc.source import Project as SourceProject
from osc.wc.base import TransactionListener
from osc.wc.project import Project
from osc.wc.package import Package, UnifiedDiff
from osc.wc.util import wc_is_project, wc_is_package


class MyTransactionListener(TransactionListener):
    def begin(self, name, uinfo):
        print "starting \"%s\" transaction" % name

    def finished(self, name, aborted=False, abort_reason=''):
        if aborted:
            print "aborted \"%s\" transaction: %s" % (name, abort_reason)
        else:
            print "finished \"%s\" transaction" % name

    def transfer(self, transfer_type, filename):
        print "%s: \"%s\"" % (transfer_type, filename)

    def processed(self, filename, new_state):
        print "processed: \"%s\" (state: \"%s\")" % (filename, new_state)


class MyUnifiedDiff(UnifiedDiff):
    def process(self, data):
        for i in data:
            sys.stdout.write(i)


def _init(apiurl):
    conf_filename = os.environ.get('OSC_CONFIG', '~/.oscrc')
    conf_filename = os.path.expanduser(conf_filename)
    cp = SafeConfigParser({'plaintext_password': True, 'aliases': ''})
    cp.read(conf_filename)
    apiurl = apiurl.strip('/')
    if apiurl == 'api':
        apiurl = 'https://api.opensuse.org'
    for section in cp.sections():
        aliases = cp.get(section, 'aliases', raw=True)
        aliases = aliases.split(',')
        if section.strip('/') == apiurl or apiurl in aliases:
            user = cp.get(section, 'user', raw=True)
            password = cp.get(section, 'pass', raw=True)
            if cp.has_option(section, 'passx'):
                password = cp.get(section, 'pass', raw=True)
                password = password.decode('base64').decode('bz2')
            Osc.init(section, username=user, password=password)
            return section

def _checkout(info):
    path = os.path.join(os.getcwd(), info.project)
    if not os.path.exists(path):
        Project.init(path, info.project, info.apiurl)
    packages = []
    if hasattr(info, 'package'):
        packages.append(info.package)
    prj = Project(path, transaction_listener=[MyTransactionListener()])
    prj.update(*packages)

def _update(info):
    path = os.getcwd()
    par_path = os.path.join(path, os.pardir)
    expand = ''
    if hasattr(info, 'expand'):
        expand = info.expand
    if hasattr(info, 'package') and not wc_is_project(par_path):
        pkg = Package(path, transaction_listner=[MyTransactionListener()])
        pkg.update(expand=expand)
    elif hasattr(info, 'package') and wc_is_project(par_path):
        prj = Project(par_path, transaction_listener=[MyTransactionListener()])
        prj.update(*[info.package], expand=expand)
    elif wc_is_project(path):
        prj = Project(path, transaction_listener=[MyTransactionListener()])
        prj.update(expand=expand)

def _status(info):
    path = os.getcwd()
    if hasattr(info, 'package'):
        pkg = Package(path)
        for filename in sorted(os.listdir(path)):
            print "%s\t%s" % (pkg.status(filename), filename)
    else:
        prj = Project(path)
        for package in sorted(os.listdir(path)):
            print "%s\t%s" % (prj._status(package), package)

def _diff(info):
    path = os.getcwd()
    pkg = Package(path)
    ud = MyUnifiedDiff()
    pkg.diff(ud)
    ud.diff()

def _list(info):
    expand = ''
    if hasattr(info, 'expand'):
        expand = info.expand
    if hasattr(info, 'package'):
        spkg = SourcePackage(info.project, info.package)
        directory = spkg.list(expand=expand)
        title = "%s: %s" % (os.path.join(info.project, info.package),
                            directory.get('srcmd5'))
    else:
        title = info.project + ':'
        sprj = SourceProject(info.project)
        directory = sprj.list(expand=expand)
    print title
    for entry in directory:
        print entry.get('name')

def _fixup_args(args, num):
    # FIXME: adjust oscargs module so that this is not needed anymore
    for i in xrange(num):
        if len(args) < num:
            args.insert(0, '')

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        raise ValueError('too few arguments')
    cmd = args.pop(0)
    args = list(args)
    if cmd == 'co':
        oargs = OscArgs('api://project/package?')
        _fixup_args(args, 1)
        method = _checkout
    elif cmd == 'up':
        oargs = OscArgs('api://project/package?', 'expand?')
        _fixup_args(args, 2)
        method = _update
    elif cmd == 'st':
        oargs = OscArgs('api://project/package?')
        _fixup_args(args, 1)
        method = _status
    elif cmd == 'di':
        # atm only in package dir
        oargs = OscArgs('api://project/package')
        _fixup_args(args, 1)
        method = _diff
    elif cmd == 'ls':
        oargs = OscArgs('api://project/package?', 'expand?')
        _fixup_args(args, 2)
        method = _list
    else:
        print "invalid command \"%s\"" % cmd
        sys.exit(1)
    try:
        info = oargs.resolve(*args, path=os.getcwd())
    except ValueError as e:
        print 'invalid arguments'
        print e
        sys.exit(2)
    info.apiurl = _init(info.apiurl)
    method(info)
    sys.exit(0)
