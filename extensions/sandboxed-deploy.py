#!/usr/bin/env python

import sandboxlib
import tempfile
import tarfile
import shutil
import os
import sys

sandbox_tar_path = '../deployment-sandbox-armv8l64.tar'

def run_deployment_in_sandbox(sandbox_dir):

    mounts = []
    
    sandbox = sandboxlib.executor_for_platform()
    sandbox.run_sandbox_with_redirection(
        ['mkfs.btrfs', '--version'],
        filesystem_root=sandbox_dir,
        stdout=sys.stdout, stderr=sys.stdout,
        extra_mounts=mounts)

    sandbox.run_sandbox_with_redirection(
        ['ping', '8.8.8.8', '-c', '5'],
        filesystem_root=sandbox_dir,
        network='isolated',
        stdout=sys.stdout, stderr=sys.stdout,
        extra_mounts=mounts)

    sandbox.run_sandbox_with_redirection(
        ['whoami'],
        filesystem_root=sandbox_dir,
        network='isolated',
        stdout=sys.stdout, stderr=sys.stdout,
        extra_mounts=mounts)


if os.path.exists(sandbox_tar_path):
    try:
        sandbox_dir = tempfile.mkdtemp()
        print ('Extracting sandbox tarball to %s' % sandbox_dir)
        sandbox_tar = tarfile.open(sandbox_tar_path)
        sandbox_tar.extractall(path=sandbox_dir)

	run_deployment_in_sandbox(sandbox_dir)

#    except BaseException as e:
        #shutil.rmtree(sandbox_dir)
#        raise e
    finally:
	pass
        shutil.rmtree(sandbox_dir)
else:
    print('Deployment sandbox not found. Please build it.')


