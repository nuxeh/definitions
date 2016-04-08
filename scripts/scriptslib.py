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
import os
import urllib2
import urllib
import urlparse
import tarfile
import sys

class ScriptError(Exception):
    def __init__(self, message):
        self.msg = message
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
    '''Resolve a cache URL and return a string'''
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
        self.metas = {}

    def get_each(self):
        '''Yield an iterable for the whole list of metas'''
        for key in self.metas:
            yield self.metas[key]

    def get_name(self, name):
        '''Yield an iterable of metadata matched by name, e.g. `bash`'''
        for key in self.metas:
            if self.metas[key]['source-name'] == name:
		yield self.metas[key]

    def import_meta(self, meta_text):
        importers = (self.import_meta_ybd,
                     self.import_meta_morph)

        for i in importers:
            try:
                i(meta_text)
                return
            except (KeyError, Exception) as err:
                pass

        # Shouldn't get here
        sys.stderr.write('Metadata format not recognised.\n'
                         'Error:\n')
        raise err

    def import_meta_morph(self, meta_text):
        self._add_meta(yaml.load(meta_text))

    def import_meta_ybd(self, meta_text):
        source = yaml.load(meta_text)

        null = '0' * 32

        if 'repo' not in source:
            kind = 'stratum'
            contents = 'components'
            source['repo'] = 'upstream:definitions'
            source['ref'] = null # No ref info
        else:
            kind = 'chunk'
            contents = 'files'

        repo = parse_repo_alias(source['repo'])
        source_name = '-'.join(
                      source['products'][0]['artifact'].split('-')[:-1])

        # Needed until YBD provides cache-key in metadata
        if not 'cache-key' in source:
            source['cache-key'] = null

        for product in source['products']:

            self._add_meta({
                'kind':           kind,
                'source-name':    source_name,
                'artifact-name':  product['artifact'],
                'contents':       product[contents],
                'repo':           repo,
                'repo-alias':     source['repo'],
                'sha1':           source['ref'],
                'original_ref':   source['ref'],
                'cache-key':      source['cache-key']
                })

    def _add_meta(self, meta_dict):
        '''Validate and add a meta'''

        required_fields = ('repo', 'sha1', 'contents')
        for f in required_fields:
            if not f in meta_dict:
                raise Exception('Metadata format not recognised, '
                                'no value for \'%s\'' % f)
        self.metas[meta_dict['artifact-name']] = meta_dict


def meta_load_from_dir(meta_dir_path):
    '''Read Baserock metadata from a directory'''

    files = [f for f in os.listdir(meta_dir_path)
             if os.path.isfile(os.path.join(meta_dir_path, f))]

    meta = BaserockMeta()
    for f in files:
        if f.endswith('.meta') and f is not 'deployment.meta':
            meta.import_meta(open(os.path.join(meta_dir_path, f), 'r').read())

    return meta


def meta_load_from_tarball(system_tarball_path):
    ''' Read Baserock metadata from a system tarball

        Metadata is read directly from the tarball, and doesn't require
        extraction to a temporary directory'''

    meta = BaserockMeta()
    with tarfile.open(system_tarball_path) as tar:
        metas = [tarinfo for tarinfo in tar.getmembers()
                 if 'baserock/' in tarinfo.name
                and tarinfo.name.endswith('.meta')]

        if not metas:
            raise Exception('No Baserock metadata found '
                            'in %s' % system_tarball_path)

        for m in metas:
            if f is not 'deployment.meta':
                meta.import_meta(tar.extractfile(m).read())

    return meta
