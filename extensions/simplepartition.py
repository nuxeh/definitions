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


# jsonschema

''' A simple Python module for creating partitioned devices or images

    It is intended to work on Linux, though may work on other operating
    systems using fdisk from util-linux '''

import subprocess
import yaml

class Partition(object):
    '''
    A class to describe a partition in a disk or image

    The required attributes are loaded as key-value pairs from a dict.

    Required attributes:
      * size: String describing the size of the partition in bytes (TODO human readable?).
              This may also be 'fill' to expand this partition to fill used space (TODO: normalise)
      * format: A string describing the filesystem format for the
                partition, or 'none' to skip filesystem creation
      * fdisk_type: A number describing the hexadecimal code used by fdisk
                    to describe the partition type (TODO: string + validate)

    Optional attributes:
      * description: A string describing the partition
      * boot: Boolean describing whether the bootable flag should be set
      * mountpoint: String describing the mountpoint for the partition (TODO: strip / ?)
      * number: Number used to override partition numbering for the
                partition (MBR only)
    '''

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    self.boot_flag = False
    raw_files = []

# subclass / override baserock specific things, i.e. filesystem creation, dd

class PartitionInfo(object):
    '''
    A class to describe a disk or image, and the partition layout
    used inside it

    The required attributes are loaded from a dict, containing key-value
    pairs describing the required attributes. This may be loaded
    from a YAML specification using the module function loadYAML().

    Attributes:
      * disk_size: Number or string describing the total disk size in
                   bytes (TODO: or 'fill' for a real device ?)
      * start_sector: The first 512 byte sector of the first partition
      * partition_table_format: A string describing the type of partition
                                table used on the device
      * partitions: A list containing the attributes for each partition
                    object as a dict (see class Partition)
    '''

    def __init__(self, ):
        # List to hold partitions
        self.partitions = []

        self.numPartitions()

        self.updatePartitions()

    def addPartition(self, kwargs):
        '''
        Add a partition by dict of attributes
        '''
        partition = Partition(**kwargs)
        self.partitions.append(partition)

    def appendPartition(self, partition):
        '''
        Add a partition as an instance of Partition
        '''
        if isinstance(partition, Partition) 
            self.partitions.append(partition)

    def _updatePartitions(self):
        for partition in partitions:
            self.addPartition(partition)

    def getPartitionByMountpoint(self, mountpoint):
        '''
        Get the partition object by its mountpoint
        '''
                

def loadYAML(yamlFile):
    '''
    Load partition data from a yaml specification

    The YAML file describes the attributes documented in the PartitionInfo
    and Partition classes. A simple example might be:
            
    '''
    print 'Reading partition specification: %s' % part_file
    with open(yamlFile, 'r') as f:
        kwargs = yaml.safe_load(f)
    


class SimplePartitioning():

    @staticmethod
    def get_sector_size(location):
        ''' Get the logical sector size of a device or image '''

        fdisk_output = subprocess.check_output(['fdisk', '-l', location])
        r = re.compile('.*Sector size.*?(\d+) bytes', re.DOTALL)
        m = re.match(r, fdisk_output)
        if m:
            return int(m.group(1))
        else:
            raise ExtensionError('Can\'t get sector size for %s' % location)

    @staticmethod
    def get_disk_size():
        # Get the size of a real device

    def load_partition_data(self, part_file):

    def process_partition_data(self, partition_data, sector_size):
        ''' Calculate offsets, sizes, and numbering for each partition

            This function takes a dict described by the YAML partition
            specification and returns a modified dict with additional
            information added to it, in order to fully describe the required
            partition layout. It also checks for some potential issues in the
            provided partition specification '''

        partitions = partition_data['partitions']
        requested_numbers = set(partition['number']
                            for partition in partitions
                            if 'number' in partition)

        pt_format = partition_data['partition_table_format']
        if pt_format == 'gpt':
            allowed_partitions = 128
        else:
            allowed_partitions = 4

        if pt_format not in ('dos', 'mbr', 'gpt'):
            raise ExtensionError(msg='Unrecognised partition table type')

        # Process partition numbering and boot flag
        used_numbers = set()
        seen_mountpoints = set()
        for partition in partitions:
            # Find the next unused partition number
            for n in xrange(1, allowed_partitions + 1):
                if n not in used_numbers and n not in requested_numbers:
                    part_num = n
                    break
                elif n == allowed_partitions:
                    raise ExtensionError('A maximum of %d partitions is '
                                         'supported for %s partition '
                                         'tables' %
                                         (allowed_partitions, pt_format))

            if 'number' in partition:
                if pt_format == 'gpt':
                    raise ExtensionError('Partition numbering can\'t be '
                                         'overridden when using a GPT')
                part_num_req = partition['number']
                if 1 <= part_num_req <= allowed_partitions:
                    if part_num_req not in used_numbers:
                        part_num = part_num_req
                    else:
                        raise ExtensionError('Repeated partition number')
                else:
                    raise ExtensionError('Requested partition number %s. '
                                         'A maximum of %d partitions is '
                                         'supported for %s partition '
                                         'tables' % (part_num_req,
                                          allowed_partitions, pt_format))

            partition['number'] = part_num
            used_numbers.add(part_num)

            # Boot flag
            if 'boot' in partition:
                partition['boot'] = self.parse_boolean(partition['boot'])
            else:
                partition['boot'] = False

            # Check for duplicated mountpoints
            if 'mountpoint' in partition:
                mountpoint = partition['mountpoint']
                if mountpoint in seen_mountpoints:
                    raise ExtensionError('Duplicated mountpoint: %s' %
                                          mountpoint)
                if mountpoint == '/' and partition['format'] != 'btrfs':
                    raise ExtensionError('Root filesystem should be btrfs')
                seen_mountpoints.add(mountpoint)

        # Check for root mountpoint
        if not '/' in seen_mountpoints:
            raise ExtensionError('No root partition specified, '
                                 'please add a partition with '
                                 'mountpoint \'/\'')

        # Process partition sizes
        start = (partition_data['start_offset'] * 512) / sector_size
        # Sector quantities in the specification are assumed to be 512 bytes
        # This converts to the real sector size
        min_start_bytes = 1024**2
        if (start * sector_size) < min_start_bytes:
            raise ExtensionError('Start offset should be greater than '
                                 '%d, for %d byte sectors' %
                                 (min_start_bytes / sector_size,
                                  sector_size))
        # Check the disk's first partition starts on a 4096 byte boundary
        # this ensures alignment, and avoiding a reduction in performance
        # on disks which use a 4096 byte physical sector size
        if (start * sector_size) % 4096 != 0:
            self.status(msg='WARNING: Start sector is not aligned to '
                            '4096 byte sector boundaries')

        disk_size = self.get_disk_size()
        if not disk_size:
            raise ExtensionError('DISK_SIZE is not defined')

        disk_size_sectors = disk_size / sector_size
        if pt_format == 'gpt':
            # GPT partition table is duplicated at the end of the device.
            # GPT header takes one sector, whatever the sector size,
            # with a 16384 byte 'minimum' area for partition entries,
            # supporting up to 128 partitions (128 bytes per entry).
            # The duplicate GPT does not include the 'protective' MBR
            gpt_size_sectors = (sector_size + (16 * 1024)) / sector_size
            total_usable_sectors = disk_size_sectors - gpt_size_sectors
        else:
            total_usable_sectors = disk_size_sectors

        offset = start
        for partition in partitions:
            if partition['size'] != 'fill':
                size_bytes = self._parse_size(str(partition['size']))

                # Calculate sector size, aligned to 4096 byte boundaries
                size_sectors = (size_bytes / sector_size +
                               ((size_bytes % 4096) != 0) *
                               (4096 / sector_size))

                offset += size_sectors
                partition['size_sectors'] = size_sectors
                partition['size'] = size_sectors * sector_size

        if len(['' for partition in partitions
                   if partition['size'] == 'fill']) > 1:
            raise ExtensionError('Only one partition can '
                                 'have \'size: fill\'')

        free_sectors = total_usable_sectors - offset

        offset = start
        total_size = 0
        last_sector = 0
        for partition in partitions:
            # Process filled partition
            if partition['size'] == 'fill':
                if free_sectors < 1:
                    raise ExtensionError(msg='Not enough space to create '
                                             'fill partition')
                partition['size_sectors'] = free_sectors
                partition['size'] = free_sectors * sector_size
                self.status(msg='Filling partition %s to size: %d bytes' %
                                 (partition['number'], partition['size']))
            # Process partition start and end points
            partition['start'] = offset
            size_sectors = partition['size_sectors']
            last_sector = offset + (size_sectors - 1)
            partition['end'] = last_sector
            offset += size_sectors

        # Size checks
        self.status(msg='Requested image size: %s bytes '
                        '(%d sectors of %d bytes)' %
                        (last_sector * sector_size, last_sector, sector_size))

        unused_space = total_usable_sectors - last_sector
        self.status(msg='Unused space: %d bytes (%d sectors)' %
                         (unused_space * sector_size, unused_space))

        if last_sector > total_usable_sectors:
            raise ExtensionError('Requested total size exceeds '
                                 'disk image size DISK_SIZE')

        self.status(msg='Partition summary:')
        for partition in partitions:
            self.status(msg='Number:   %s' % str(partition['number']))
            self.status(msg='  Start:  %s sectors' % str(partition['start']))
            self.status(msg='  End:    %s sectors' % str(partition['end']))
            self.status(msg='  Ftype:  %s' % str(partition['fdisk_type']))
            self.status(msg='  Format: %s' % str(partition['format']))
            self.status(msg='  Size:   %s bytes' % str(partition['size']))

        # Sort the partitions by partition number
        new_partitions = sorted(partitions, key=lambda partition:
                                partition['number'])

        new_partition_data = partition_data
        new_partition_data['partitions'] = new_partitions
        return new_partition_data

    def create_partition_table(self, location, partition_data):
        ''' Use fdisk to create a partition table '''

        pt_format = partition_data['partition_table_format'].lower()
        self.status(msg="Creating %s partition table on %s" %
                        (pt_format.upper(), location))

        # Create a new partition table
        if pt_format in ('mbr', 'dos'):
            cmd = "o\n"
        elif pt_format == 'gpt':
            cmd = "g\n"

        for partition in partition_data['partitions']:
            part_num = partition['number']
            # Create partitions
            if partition['fdisk_type'] != 'none':
                cmd += "n\n"
                if pt_format in ('mbr', 'dos'):
                    cmd += "p\n"
                cmd += (str(part_num) + "\n"
                        "" + str(partition['start']) + "\n"
                        "" + str(partition['end']) + "\n")

                # Set partition types
                cmd += "t\n"
                if part_num > 1:
                    # fdisk does not ask for a partition
                    # number when setting the type of the
                    # first created partition
                    cmd += str(part_num) + "\n"
                cmd += str(partition['fdisk_type']) + "\n"

                # Set bootable flag
                if partition['boot']:
                    cmd += "a\n"
                    if part_num > 1:
                        cmd += str(part_num) + "\n"

        # Write changes
        cmd += ("w\n"
                "q\n")
        p = subprocess.Popen(["fdisk", location],
                             stdin=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        p.communicate(cmd)
