#!/usr/bin/env python
# Copyright (C) 2012-2016 Codethink Limited
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
# with this program.  If not, see <http://www.gnu.org/licenses/>.


import sys
import glob
import os
import re
import contextlib
import tempfile
import scriptslib


verbose = False


def generate_manifest(args):
    '''Generate a content manifest for a system image.

    Command line arguments:

    * `SYSTEM-ARTIFACT` is a filename to the system artifact
      (root filesystem) for the built system.

    This command generates a manifest for a built system image.
    The manifest includes the constituent artifacts,
    a guess at the component version, the exact commit for
    the component (commit SHA1, repository URL, git symbolic
    ref), and the morphology filename.


    The manifest includes each constituent artifact, with several
    columns of data:
    
    * 7-char cache key with the artifact kind (system, stratum, chunk),
    artifact name, and version (if guessable) added
    * the git repository
    * the symbolic reference
    * a 7-char commit id

    Example:

        ./scripts/system-manifest.py [-v] /src/cache/artifacts/foo-rootfs

    '''

    global verbose

    if len(args) and args[0] == '-v':
	verbose = True

    if len(args) < (1 + int(verbose)):
        scriptslib.ScriptError(
            'usage:\n    system-manifest.py [-v] tarball_path')

    artifact = args[-1]

    generator = ManifestGenerator()
    generator.generate(artifact)


def status(message):
    if verbose:
	scriptslib.status(message)


class ProjectVersionGuesser(object):

    def __init__(self, interesting_files):
        self.interesting_files = interesting_files

    def file_contents(self, repo, ref, tree):
        filenames = [x for x in self.interesting_files if x in tree]
        for filename in filenames:
            # Retreive file from Baserock cache server
            yield filename, scriptslib.cache_get_file(repo, ref, filename)


class AutotoolsVersionGuesser(ProjectVersionGuesser):

    def __init__(self):
        ProjectVersionGuesser.__init__(self, [
            'configure.ac',
            'configure.in',
            'configure.ac.in',
            'configure.in.in',
        ])

    def guess_version(self, repo, ref, tree):
        version = None
        for filename, data in self.file_contents(repo, ref, tree):
            # First, try to grep for AC_INIT()
            version = self._check_ac_init(data)
            if version:
                status('Version of %s %s detected '
                       'via %s:AC_INIT: %s' % (repo, ref, filename, version))
                break

            # Then, try running autoconf against the configure script
            version = self._check_autoconf_package_version(
                repo, ref, filename, data)
            if version:
                status('Version of %s %s detected by processing '
                       '%s: %s' % (repo, ref, filename, version))
                break
        return version

    def _check_ac_init(self, data):
        data = data.replace('\n', ' ')
        for macro in ['AC_INIT', 'AM_INIT_AUTOMAKE']:
            pattern = r'.*%s\((.*?)\).*' % macro
            if not re.match(pattern, data):
                continue
            acinit = re.sub(pattern, r'\1', data)
            if acinit:
                version = acinit.split(',')
                if macro == 'AM_INIT_AUTOMAKE' and len(version) == 1:
                    continue
                version = version[0] if len(version) == 1 else version[1]
                version = re.sub('[\[\]]', '', version).strip()
                version = version.split()[0]
                if version:
                    if version and version[0].isdigit():
                        return version
        return None

    def _check_autoconf_package_version(self, repo, ref, filename, data):
        try:
            tempdir = tempfile.mkdtemp()
            tempfile = os.path.join(tempdir, filename)
            with open(tempfile, 'w') as f:
                f.write(data)
            exit_code, output, errors = subprocess.check_call(
                ['autoconf', tempfile],
                ['grep', '^PACKAGE_VERSION='],
                ['cut', '-d=', '-f2'],
                ['sed', "s/'//g"])
            version = None
            if output:
                output = output.strip()
                if output and output[0].isdigit():
                    version = output
            if exit_code != 0:
                status('Failed to detect version from '
                       '%s %s:%s' % (repo, ref, filename))
        finally:
            shutil.rmtree(tempdir)
        return version


class VersionGuesser(object):

    def __init__(self):
        self.guessers = [
            AutotoolsVersionGuesser()
        ]

    def guess_version(self, repo, ref):
        status('Guessing version of %s %s' % (repo, ref))
        version = None
        try:
            # List files on Baserock cache server
            tree = scriptslib.cache_ls(repo, ref)

            for guesser in self.guessers:
                version = guesser.guess_version(repo, ref, tree)
                if version:
                    break
        except BaseException as err:
            status('Failed to list files in %s %s' % (repo, ref))
        return version

class ManifestGenerator(object):

    def __init__(self):
        self.version_guesser = VersionGuesser()

    def generate(self, artifact):
        # Collect all meta information about the system, its strata
        # and its chunks that we are interested in.
	status('Extracting metadata from tarball...')
        metadata = scriptslib.meta_load_from_tarball(artifact)
        artifacts = []

        for metadata in metadata.get_each():
            # Try to guess the version of this artifact
            version = self.version_guesser.guess_version(
                      metadata['repo'], metadata['sha1'])
            if version is None:
                version = ''
            else:
                version = '-%s' % version

            fst_col = '%s.%s.%s%s' % (metadata['cache-key'][:7],
                                      metadata['kind'],
                                      metadata['artifact-name'],
                                      version)

            original_ref = metadata['original_ref']
            if (metadata['kind'] in ('system', 'stratum') and
                'baserock/builds/' in original_ref):
                original_ref = original_ref[: len('baserock/builds/') + 7]

            artifacts.append({
                'kind': metadata['kind'],
                'name': metadata['artifact-name'],
                'fst_col': fst_col,
                'repo': metadata['repo'],
                'original_ref': original_ref,
                'sha1': metadata['sha1'][:7]
            })
        
        # Generate a format string for dumping the information.
        fmt = self._generate_output_format(artifacts)
        print(fmt % ('ARTIFACT', 'REPOSITORY',
                     'REF', 'COMMIT'))

        # Print information about system, strata and chunks.
        self._print_artifacts(fmt, artifacts, 'system')
        self._print_artifacts(fmt, artifacts, 'stratum')
        self._print_artifacts(fmt, artifacts, 'chunk')

    def _generate_output_format(self, artifacts):
        colwidths = {}
        for artifact in artifacts:
            for key, value in artifact.iteritems():
                colwidths[key] = max(colwidths.get(key, 0), len(value))

        return '%%-%is\t' \
               '%%-%is\t' \
               '%%-%is\t' \
               '%%-%is' % (
                colwidths['fst_col'],
                colwidths['repo'],
                colwidths['original_ref'],
                colwidths['sha1'])

    def _print_artifacts(self, fmt, artifacts, kind):
        for artifact in sorted(artifacts, key=lambda x: x['name']):
            if artifact['kind'] == kind:
                print(fmt % (artifact['fst_col'],
                             artifact['repo'],
                             artifact['original_ref'],
                             artifact['sha1']))


if __name__ == "__main__":
    generate_manifest(sys.argv[1:])
