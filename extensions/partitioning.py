#!/usr/bin/python
# Copyright (C) 2012-2015  Codethink Limited
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


''' A write extension to help making partitioned images or devices '''


    def do_partitioning(self, location, temp_root, part_file):
        ''' The steps required to create a partitioned device or
            device image

            This includes:
            - Creating a partition table
            - Creating filesystems on partitions
            - Copying files to partitions
            - Directly writing files to the device
            - Creating the Baserock system on a partition

            These functions only do anything if configured to do so in a
            partition specification, see extensions/rawdisk.write.help '''

        partition_data_raw = self.load_partition_data(part_file)
        sector_size = self.get_sector_size(location)
        self.status(msg='Using a physical sector size of %d bytes'
                         % sector_size)
        partition_data = self.process_partition_data(
                         partition_data_raw, sector_size)

        self.create_partition_table(location, partition_data)
        partitions = partition_data['partitions']
        self.create_partition_filesystems(location, partitions, sector_size)
        self.create_partition_rootfs(temp_root, location,
                                     partitions, sector_size)
        self.partition_direct_copy(location, temp_root,
                                   partition_data, sector_size)

    def create_partition_filesystems(self, location, partitions, sector_size):
        ''' Read partition data and create all required filesystems '''

        self.status(msg="Creating filesystems...")

        for partition in partitions:
            filesystem = partition['format']
            if filesystem not in ('none', 'None', None):
                with self.create_loopback(location,
                                          partition['start'] *
                                          sector_size,
                                          partition['size']) as device:
                    self.status(msg='Creating filesystem on partition %d' %
                                     partition['number'])
                    self.create_filesystem(device, filesystem)

    def create_filesystem(self, block_device, fstype):
        ''' Create filesystems of various types on a device node '''

        recognised_filesystem_formats = ('btrfs', 'ext4', 'vfat')

        if fstype == 'btrfs':
            self.format_btrfs(block_device)
        elif fstype in recognised_filesystem_formats:
            try:
                self.status(msg='Creating %s filesystem' % fstype)
                subprocess.check_call(['mkfs.' + fstype, block_device])
            except BaseException:
                raise ExtensionError('Error creating %s filesystem on %s' %
                                     (fstype, block_device))
        else:
            raise ExtensionError('Unrecognised filesystem'
                                 ' format: %s' % fstype)

    def create_partition_rootfs(self, temp_root, location,
                                partitions, sector_size):
        ''' Create the Baserock root filesystem, and set up partitions

            Create a Baserock system on '/'. Additionally add entries for
            partitions to the system's /etc/fstab; copy files from the
            mountpoint in the rootfs to the appropriate partition, or
            create an empty mountpoint for it

            FIXME: Implement this using a class '''

        self.status(msg='Creating system...')

        with ExitStack() as stack:
            mountpoints = {partition['mountpoint']:
                                {'format': partition['format'],
                                 'uuid': self.get_uuid(location,
                                                       partition['start'] *
                                                       sector_size),
                'mount_dir': stack.enter_context(self.mount(
                             stack.enter_context(
                                  self.create_loopback(location,
                                                       partition['start'] *
                                                       sector_size,
                                                       partition['size']))))}
                           for partition in partitions
                           if 'mountpoint' in partition}

            root_mount = mountpoints['/']
            self.create_btrfs_system_layout(temp_root,
                                            root_mount['mount_dir'],
                                            'factory', root_mount['uuid'],
                                            mountpoints)

    def partition_direct_copy(self, location, temp_root,
                              partition_data, sector_size):
        ''' Copy files directly to a partition using `dd`

            Where raw files are specified within a partition, the offset
            is taken from the start of the partition, but if specified at
            the top level of the configuration file, the offset is taken
            from the start of the disc '''

        for partition in partition_data['partitions']:
            if 'raw_files' in partition:
                self.partition_dd(temp_root, location,
                                  partition['raw_files'],
                                  partition['start'] *
                                  sector_size, sector_size)
        if 'raw_files' in partition_data:
            self.partition_dd(temp_root, location,
                              partition_data['raw_files'], 0, sector_size)

    def partition_dd(self, temp_root, location, raw_files_data,
                     start_offset, sector_size):
        ''' `dd` files consecutively to an offset on a device

            By default files are written after the previous file in the
            specification, optionally any file can have a an offset set
            in bytes or sectors '''

        self.status(msg='Writing files directly to image...')

        file_offset = start_offset
        for raw_file in raw_files_data:
            if 'offset' in raw_file:
                # Sectors are assumed to be 512 bytes in the specification, so
                # no adjustment is needed here since we write to a byte offset
                file_offset = raw_file['offset'] * 512
            if 'offset_bytes' in raw_file:
                file_offset = self._parse_size(str(raw_file['offset_bytes']))
            source = os.path.join(temp_root,
                                  re.sub('^/', '', raw_file['file']))
            if os.path.exists(source):
                if not os.path.isdir(source):
                    self.status(msg='Writing %s, at offset %d bytes' %
                                     (source, file_offset))
                    subprocess.check_call(['dd', 'if=%s' % source, 'of=%s'
                                          % location, 'bs=1', 'seek=%s'
                                          % file_offset, 'conv=notrunc'])
                    subprocess.check_call('sync')
                    file_offset += os.stat(source).st_size
                else:
                    raise ExtensionError('Can only dd regular files, '
                                         'not directories')
            else:
                raise ExtensionError('File not found: %s' % source)
