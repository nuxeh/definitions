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

    def import_meta(self, meta_text):
        importers = (self.import_meta_ybd,
                     self.import_meta_morph)

        for i in importers:
            try:
                i(meta_text)
                return
            except BaseException:
                pass

        # Shouldn't get here
        raise Exception('Metadata format not recognised.')

    def import_meta_morph(self, meta_text):
        self._add_meta(yaml.load(meta_text))

    def import_meta_ybd(self, meta_text):
        source = yaml.load(meta_text)

        if 'repo' not in source:
            return # Probably a stratum (no morph equivalent meta)

        repo = parse_repo_alias(source['repo'])
        source_name = '-'.join(
                      source['products'][0]['artifact'].split('-')[:-1])

        for meta in source['products']:

            self._add_meta({
                'kind':          'chunk',
                'source_name':   source_name,
                'artifact_name': meta['artifact'],
                'repo':          repo,
                'sha1':          source['ref'],
                'repo-alias':    source['repo'],
                'contents':      meta['files']
                })

    def _add_meta(self, meta_dict):
        '''Validate and add a meta'''

        required_fields = ('repo', 'sha1', 'contents')
        for f in required_fields:
            if meta_dict[f] is None:
                raise Exception('Metadata format not recognised, '
                                'no value for \'%s\'' % f)
        self.metas.append(meta_dict)


def meta_load_from_dir(meta_dir_path):
    '''Return a dict representing a Baserock meta string'''
    files = [f for f in os.listdir(meta_dir_path)
            if os.isfile(join(meta_dir_path, f))]

    meta = BasrockMeta()
    for f in files:
        meta.import_meta(open(os.join(meta_dir_path, f)).read())
