# Copyright (C) 2016 Codethink Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# Small library of useful things for the scripts that live here.

import yaml
import subprocess
import urllib2
import urllib
import urlparse
import tarfile
import sys

class ScriptError(Exception):
    def __init__(self, message):
        status(message)
        sys.exit(1)

def status(message):
    sys.stderr.write('%s\n' % message)

aliases = {
  'baserock:': 'git://%(trove)s/baserock/',
  'freedesktop:': 'git://anongit.freedesktop.org/',
  'github:': 'git://github.com/',
  'gnome:': 'git://git.gnome.org/',
  'upstream:': 'git://%(trove)s/delta/'
}

def parse_repo_alias(repo, trove_host='git.baserock.org'):
    global aliases
    remote = repo[:repo.find(':') + 1]
    aliases = {k: v % {'trove': trove_host} for k, v in aliases.iteritems()}
    try:
        return repo.replace(remote, aliases[remote])
    except KeyError as e:
        raise Exception("Unknown repo-alias \"%s\"" % repo)


def cache_get_file(repo_url, ref, filename):
    '''Obtain a single file from a repo on the Baserock cache server'''
    return _cache_request('files?repo=%s&ref=%s&filename=%s' % tuple(
                        [urllib.quote(s) for s in (repo_url, ref, filename)]))

def cache_ls(repo_url, ref):
    '''Get a list of files in a repo on the Baserock cache server'''
    return _cache_request('trees?repo=%s&ref=%s' % tuple(
                           [urllib.quote(s) for s in (repo_url, ref)]))

def _cache_request(path):
    server_url = 'http://git.baserock.org:8080/'
    url = urlparse.urljoin(server_url, '/1.0/%s' % path)
    fetch = urllib2.urlopen(url)
    return fetch.read()


def definitions_root():
    return subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"]).strip()

def load_yaml_file(yaml_file):
    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)


class BaserockMeta(object):
    '''An object representing Baserock metadata contained in a Baserock
       system image, for available metadata formats'''

    def __init__(self):
        self.metas = []

    def get_metas(self):
        return self.metas

    def meta_import(self, meta_text):
        importers = (self.meta_import_ybd,
                     self.meta_import_morph)

        for i in importers:
            try:
                i(meta_text)
                return
            except BaseException:
                pass

        # Shouldn't get here
        raise Exception('Metadata format not recognised.')

    def meta_import_morph(self, meta_text):
        self.add_meta(yaml.load(meta_text))

    def meta_import_ybd(self, meta_text):
        source = yaml.load(meta_text)

        repo = parse_repo_alias(source['repo'])
        source_name = '-'.join(
                      source['products'][0]['artifact'].split('-')[:-1])

        for meta in source['products']:

            self.add_meta({
                'kind':          'stratum',
                'source_name':   source_name,
                'artifact_name': meta['artifact'],
                'repo':          repo,
                'sha1':          source['ref'],
                'repo-alias':    source['repo'],
                'contents':      meta['files']
                })

    def add_meta(self, meta_dict):
        '''Validate and add a meta'''

        required_fields = ('repo', 'sha1', 'contents')
        for f in required_fields:
            if meta_dict[f] is None:
                raise Exception('Metadata format not recognised, '
                                'no value for \'%s\'' % f)
        self.metas.append(meta_dict)

def meta_load(meta_text):
    '''Return a dict representing a Baserock meta string'''

    return BaserockMeta().meta_import(meta_text).get_metas()

def meta_load_from_tarball(system_tarball_path):
    ''' Read baserock metadata from a system tarball
    
        Metadata is read directly from the tarball, and doesn't require
        extraction to a temporary directory'''

    with tarfile.open(system_tarball_path) as tar:
        metas = [tarinfo for tarinfo in tar.getmembers()
                 if tarinfo.name.startswith('baserock/')
                and tarinfo.name.endswith('.meta')]

        if not metas:
            raise Exception('No Baserock metadata found '
                            'in %s' % system_tarball_path)

        m = BaserockMeta()
        for meta in metas:
            m.meta_import(tar.extractfile(meta).read())

    return m.get_metas()

