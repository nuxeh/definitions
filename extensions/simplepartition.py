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
# Partitioning error handling class - geometry error?
# Pretty printing / pretty input

"""
A simple Python module for creating partitioned devices or images

This creates partitions by making calls to the fdisk command line
tool.

It is intended to work on Linux, though may work on other operating
systems using fdisk from util-linux.

Requires fdisk <versions>

"""

import subprocess
import yaml
# staticmethod

class Extent(object):
    """
    A class to hold start and end points for other objects (Devices, Partitions)
    with sectors of a given size
    """

    def __init__(self, sector_size=512, start=0, end=0, size=0, fill=False):
        self.sector_size = int(sector_size)
        self.fill = False
        if fill:
            self.start = 0
            self.end = 0
            self.fill = True
        else if start and end:
            self.start = int(start)
            self.end = int(end)
        else if start and size:
            self.start = int(start)
            start.end = int(start) + int(end)

    def __str__(self):
        return ('<Extent: Start=%d, End=%d, Length(bytes)=%d, Fill=%s>' %
                (self.start, self.end, self.__len__()))

    def __max__(self):
        return self.end

    def __min__(self):
        return self.start

    def __len__(self):
        """
        Return the length in bytes
        """
        return (self.end - self.start) * sector_size

    def length_sectors(self):
        """
        Return the length in sectors
        """
        return (self.end - self.start)

class PartitionList(object):
    """
    An iterable object to contain partitions, and handle partition numbering
    """

    def __init__(self, extent):
        self.__partition_list = []
        self.extent = extent
        self.fill_partition_count = 0

    def append(self, partition):
        if isinstance(partition, Partition):
            self.__partition_list.append(partition)
        else:
            raise PartitioningError('PartitionList can only '
                                    'contain Partitions')

    def __iter__(self):
        return self

    def __next__(self):
        """ Return the next item in an iteration """
        if last:
            raise StopIteration

    def __getitem__(self, i):
        """ Return ith item in list """
        return self.__partition_list[i]

    def next(self):
        """ next() method for Python 2 compatibility """
        return self.__next__(self)

class Partition(object):
    """
    A class to describe a partition in a disk or image

    The required attributes are loaded as key-value pairs from a dict.

    Required attributes:
        size: String describing the size of the partition in bytes (TODO human readable?).
              This may also be 'fill' to expand this partition to fill used space (TODO: normalise)
        format: A string describing the filesystem format for the
                partition, or 'none' to skip filesystem creation
        fdisk_type: A number describing the hexadecimal code used by fdisk
                    to describe the partition type (TODO: string + validate)

    Optional attributes:
        description: A string describing the partition
        boot: Boolean describing whether the bootable flag should be set
        mountpoint: String describing the mountpoint for the partition (TODO: strip / ?)
        number: Number used to override partition numbering for the
                partition (MBR only)
        TODO: label
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

# subclass / override baserock specific things, i.e. filesystem creation, dd

class Device(object):
    """
    A class to describe a disk or image, and the partition layout
    used inside it

    The required attributes are loaded from a dict, containing key-value
    pairs describing the required attributes. This may be loaded
    from a YAML specification using the module function loadYAML().

    Attributes:
        location: The location of the device or disk image
        size: The size in bytes (or a TODO human readable string) describing
              the total amount of space the partition table on the device
              will occupy
        parts: A list of Partition objects describing the partitions on the
               device
        disk_size: Number or string describing the total disk size in
                   bytes (TODO: or 'fill' for a real device ?)
        start_sector: The first 512 byte sector of the first partition
        partition_table_format: A string describing the type of partition
                                table used on the device
        partitions: A list containing the attributes for each partition
                    object as a dict (see Partition)
    """

# fillable device?

    def __init__(self, location, size, **kwargs):
        self.parts = PartitionList()
        if 'partition_table_format' not in kwargs:
            self.partition_table_format = 'gpt'
        if 'start_offset' not in kwargs:
            self.start_offset = 2048

        # Get sector size
        self.sector_size = simplepartition.getSectorSize(location)

        # Populate Device attributes from keyword dict
        self.__dict__.update(**kwargs)

        if self.partition_table_format.lower() == 'gpt':
            self.max_allowed_partitions = 128
        else:
            self.max_allowed_partitions = 4

        # Process Device size
        start = (self.start_offset * 512) / self.sector_size
        # Sector quantities in the specification are assumed to be 512 bytes
        # This converts to the real sector size
        min_start_bytes = 1024**2
        if (start * self.sector_size) < min_start_bytes:
            raise PartitioningError('Start offset should be greater than '
                                    '%d, for %d byte sectors' %
                                    (min_start_bytes / self.sector_size,
                                     self.sector_size))
        # Check the disk's first partition starts on a 4096 byte boundary
        # this ensures alignment, and avoiding a reduction in performance
        # on disks which use a 4096 byte physical sector size
        if (start * self.sector_size) % 4096 != 0:
            print('WARNING: Start sector is not aligned '
                  'to 4096 byte sector boundaries')

        disk_size_sectors = self.size / self.sector_size
        if self.partition_table_format == 'gpt':
            # GPT partition table is duplicated at the end of the device.
            # GPT header takes one sector, whatever the sector size,
            # with a 16384 byte 'minimum' area for partition entries,
            # supporting up to 128 partitions (128 bytes per entry).
            # The duplicate GPT does not include the 'protective' MBR
            gpt_size = (self.sector_size + (16 * 1024)) / self.sector_size
            # total usable sectors
            self.extent = Extext(start=start,
                                 end=(disk_size_sectors - gpt_size))
        else:
            self.extent = Extent(start=start, end=disk_size_sectors)




        self.updatePartitions()

        self.location = location
        self.size = getBytes(size) #TODO

        self.parts = PartitionList()

        self.__mountpoints = set()
    
    def addPartition(self, **kwargs):
        '''
        Add a partition by dict of attributes

        See the Partition class for details of the required attributes
        '''
        partition = Partition(**kwargs)
        # TODO non-duplicable in PartitionList
        if hasattr(partition, 'mountpoint'):
            if partition.mountpoint in self.__mountpoints:
                raise PartitioningError('Duplicated mountpoint: %s' %
                                         mountpoint)
        self.__mountpoints.add(partition.mountpoint)

        

        if len(self.parts) < self.max_allowed_partitions:
            self.parts.append(partition)
        else:
            raise PartitioningError('Cannot add partition: Maximum number of '
                                    'partitions has been reached')

    def updatePartitions(self, partitions=None):
        """
        Populate parts with Partition objects

        @param partitions: List of partition attributes
        @type partitions:  list
        """
        self.parts = PartitionList()
        if partitions:
            self.partitions = partitions
        for partition in self.partitions:
            self.addPartition(partition)

    def getPartitionByMountpoint(self, mountpoint):
        '''
        Get the partition object by its mountpoint
        '''

    def commit(self):
        """
        Write the partition table to disk
        """
        simplepartition.commit(self)

    def __str__(self):
        return 'Device: location=%s, size=%s' % (self.location, self.size)


class PartitioningError(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


# Creating images?

class simplepartition():

    def loadYAML(yamlFile):
        '''
        Load partition data from a yaml specification

        The YAML file describes the attributes documented in the PartitionInfo
        and Partition classes. A simple example might be:

        @param yaml_file: Path to a YAML file to load
        @type yaml_file:  str

        @return Device
        @rtype Device
            
        '''
        with open(yamlFile, 'r') as f:
            kwargs = yaml.safe_load(f)
        return Device(location, size, **kwargs)
    
    @staticmethod
    def commitDevice(device):
        """
        Write the partition table to device

        @param device: A device object to perform the partitioning on
        @type device:  Device
        """
        pt_format = device.partition_table_format.lower
        print("Creating %s partition table on %s" %
                        (pt_format.upper(), device.location))

        # Create a new partition table
        if pt_format in ('mbr', 'dos'):
            cmd = "o\n"
        elif pt_format == 'gpt':
            cmd = "g\n"

        for partition in device.parts:
            # Create partitions
            if partition.fdisk_type != 'none':
                cmd += "n\n"
                if pt_format in ('mbr', 'dos'):
                    cmd += "p\n"
                cmd += (str(partition.number) + "\n"
                        "" + str(partition.start) + "\n"
                        "" + str(partition.end) + "\n")

                # Set partition types
                cmd += "t\n"
                if partition.number > 1:
                    # fdisk does not ask for a partition
                    # number when setting the type of the
                    # first created partition
                    cmd += str(partition.number) + "\n"
                cmd += str(partition.fdisk_type) + "\n"

                # Set bootable flag
                if partition.boot:
                    cmd += "a\n"
                    if partition.number > 1:
                        cmd += str(partition.number) + "\n"

        # Write changes
        cmd += ("w\n"
                "q\n")
        p = subprocess.Popen(["fdisk", device.location],
                             stdin=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        p.communicate(cmd)

    def getSectorSize(self, location):
        """
        Get the logical sector size of a device or image, in bytes
        """
        return int(self.__filterFdiskListOutput('.*Sector size.*?(\d+) bytes',
                                                location))

    def getDiskSize(self, location):
        """
        Get the total size of a real block device or image, in bytes
        """
        return int(self.__filterFdiskListOutput('.*Disk.*?(\d+) bytes',
                                                location))

    def __filterFdiskListOutput(self, regex, location):
        r = re.compile(regex, re.DOTALL)
        m = re.match(r, subprocess.check_output(['fdisk', '-l', location]))
        if m:
            return m.group(1)
        else:
            raise ExtensionError('Error reading information from fdisk')

    def verifyDevice(self, device): # TODO sector size
        ''' Calculate offsets, sizes, and numbering for each partition

            This function takes a dict described by the YAML partition
            specification and returns a modified dict with additional
            information added to it, in order to fully describe the required
            partition layout. It also checks for some potential issues in the
            provided partition specification '''

        requested_numbers = set(partition['number']
                            for partition in parts
                            if 'number' in partition)

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
