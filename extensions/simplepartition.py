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

from copy import deepcopy
import re
import subprocess
import yaml
# staticmethod

class Extent(object):
    """
    A class to hold start and end points for other objects

    Start and end points are measured in sectors. This class transparently
    handles the inclusive nature of the start and end sectors of blocks of
    storage. A null case provides the possibility of a zero-length Extent.
    """

    def __init__(self, start=0, length=0, end=0):
        if length and not start:
                raise PartitioningError('Extent requires a non-zero start '
                                        'point and length')
        if start and length:
            self.start = int(start)
            self.end = int(start) + int(length) - 1
        else:
            self.start = int(start)
            self.end = int(end)

        self.filled_space = 0

    def __max__(self):
        return self.end

    def __min__(self):
        return self.start

    def __len__(self):
        return self.end - self.start + 1

    def __add__(self, other):
        """Return the sum of two extents"""
        return Extent(start=self.start,
                      length=(len(self) + len(other)))

    def __iadd__(self, other):
        """+="""
        self.end += len(other)
        return self

    def __sub__(self, other):
        if other > self:
            raise PartitioningError('subtrahend is greater than minuend')
        return Extent(start=self.start,
                      length=(len(self) - len(other)))

    def __isub__(self, other):
        if other > self:
            return Extent() # TODO: necessary?
        self.end -= len(other)
        return self

    def __gt__(self, other):
        return len(self) > len(other)

    def __lt__(self, other):
        return not self > other

    def __str__(self):
        return ('<Extent: Start=%d, End=%d, Length=%d>' %
                (self.start, self.end, len(self)))

    def pack(self, other):
        """
        Return a new Extent aligned to self's first unused sector

        This is done by length, to quantify fitting an area of disc space
        inside the other. The filled space in self is calculated and updated.
        """
        length_other = len(other)
        first_free_sector = self.start + self.filled_space
        if length_other + self.filled_space > len(self):
            raise PartitioningError('Not enough free space to pack Extent')
        self.filled_space += length_other
        return Extent(start=first_free_sector, length=length_other)

    def free_space(self):
        return len(self) - self.filled_space


class PartitionList(object):
    """
    An iterable object used to contain partitions, and process data about them

    The PartitionList calculates the geometry for each partition in the list,
    when accessed, so returned partitions have up-to-date geometry and
    numbering. This class eases the calculation of partition sizes and
    numbering, as for numbering, and Partitions with a 'fill' size, the result
    depends on each of the other partitions in the list.
    """

    def __init__(self, device):
        """
        Initialisation function

        @param device: A Device object
        @type device:  Device
        """
        self.device = device
        self.extent = device.extent # TODO: just store device
        self.max_allowed_partitions = device.max_allowed_partitions
        self.sector_size = device.sector_size

        self.__partition_list = []
        self.__iter_index = 0

    def append(self, partition):
        print 'append...'
        if isinstance(partition, Partition):
            for part in self.__partition_list:
                dup_attrib = part.compare(partition)
                if dup_attrib:
                    raise PartitioningError('Duplicated partition attribute '
                                            '\'%s\'' % dup_attrib)
            self.__partition_list.append(partition)
        else:
            raise PartitioningError('PartitionList can only '
                                    'contain Partition objects')

    def __iter__(self):
        """Return an iterable object"""
        self.__iter_index = 0
        return self

    def __next__(self):
        """Return the next item in an iteration"""
        if self.__iter_index == len(self.__partition_list):
            raise StopIteration
        else:
            partition = self[self.__iter_index]
            self.__iter_index += 1
            return partition
        
    def next(self):
        """next() method for Python 2 compatibility"""
        return self.__next__()

    def __getitem__(self, i):
        """Return an updated copy of the partition list"""
        part_list = self.__update_partition_list()
        return part_list[i]

    def free_space(self):
        """
        Calculate the amount of unused space left by the partitions currently
        in the list
        """
        part_list = self.__update_partition_list()
        self.extent.filled_space = 0
        for part in part_list:
            self.extent.pack(part.extent)
        return self.extent.free_space()

    def __update_partition_list(self):
        """
        Return an updated copy of the partition list
        
        This includes allocating an extent and numbering for the returned
        partition object. A copy of the partition list is made so that the
        returned partition object is a copy of the stored Partition object
        rather than a reference to it, thus leaving the partitions stored
        in the list intact if modified after return.
        """
        print 'get partition list......'
        part_list = deepcopy(self.__partition_list)

        fill_partitions = set(partition for partition in part_list
                              if partition.size == 'fill')
        print part_list
        print fill_partitions

        used_numbers = set()
        requested_numbers = set(partition.number for partition in part_list
                                if hasattr(partition, 'number'))

        # Get free space and the size of 'fill' partitions
        self.extent.filled_space = 0
        for part in part_list:
            if part.size != 'fill':
                extent = Extent(start=1,
                                length=self.get_length_sectors(part.size))
                self.extent.pack(extent)
        if len(fill_partitions):
            fill_size = self.extent.free_space() / len(fill_partitions)
            print fill_size

        # Set size of fill partitions
        for part in fill_partitions:
            part.size = fill_size

        # Allocate aligned Extents and partition numbers
        self.extent.filled_space = 0
        for part in part_list:
            extent = Extent(start=1,length=self.get_length_sectors(part.size))
            part.extent = self.extent.pack(extent)

            # Find the next unused partition number if not assigned
            if hasattr(part, 'number'):
                num = part.number
            else:
                for n in range(1, self.max_allowed_partitions + 1):
                    if n not in used_numbers and n not in requested_numbers:
                        num = n

            part.number = num
            used_numbers.add(num)

        return part_list

    def get_length_sectors(self, size_bytes):
        """Get a length in sectors, aligned to 4096 byte boundaries"""
        return (int(size_bytes) / self.sector_size +
               ((int(size_bytes) % 4096) != 0) *
               (4096 / self.sector_size))

    def __str__(self):
        return '<PartitionList: Length=%d>' % len(self)

    def __len__(self):
        return len(self.__partition_list)
    
    def __setitem__(self, i, value):
        """ Update the ith item in the list """
        self.append(partition)


class Partition(object):
    """
    A class to describe a partition in a disk or image

    The required attributes are loaded as key-value pairs from a kwargs dict.

    Required attributes:
        size: String describing the size of the partition in bytes
        (TODO human readable?).
              This may also be 'fill' to indicate that this partition should
              be expanded to fill all unused space. Where there is more than
              one fill partition, unused space is divided equally between the
              fill partitions.
        fdisk_type: A number describing the hexadecimal code used by fdisk
                    to describe the partition type (TODO: string + validate)

    Optional attributes:
        format: A string describing the filesystem format for the
                partition, or 'none' to skip filesystem creation
        description: A string describing the partition, for documentation
        boot: Boolean string describing whether to set the bootable flag
        mountpoint: String describing the mountpoint for the partition
        number: Number used to override partition numbering for the
                partition (MBR only)
        TODO: label
    """

    def __init__(self, size=0, fdisk_type=0x81, **kwargs):
        if not size and 'size' not in kwargs:
            raise PartitioningError('Partition must have a non-zero size')
        self.__dict__.update(**kwargs)
        self.fdisk_type = fdisk_type
        self.size = size

    def __str__(self):
        return ('Partition\n'
                'size: %s\n'
                'fdisk type: %s' % (self.size, hex(self.fdisk_type)))

    def compare(self, other):
        """Check for mutually exclusive attributes"""
        non_duplicable = ['number', 'mountpoint']
        for attrib in non_duplicable:
            if hasattr(self, attrib) and hasattr(other, attrib):
                if getattr(self, attrib) == getattr(other, attrib):
                    return attrib
        return False


class Device(object):
    """
    A class to describe a disk or image, and the partition layout
    used inside it

    Attributes are loaded from kwargs, containing key-value
    pairs describing the required attributes. These may be loaded
    from a YAML specification using the global function loadYAML().

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

    min_start_bytes = 1024**2

    def __init__(self, location, size, **kwargs):

        if 'partition_table_format' not in kwargs:
            self.partition_table_format = 'gpt'
        if 'start_offset' not in kwargs:
            self.start_offset = 2048

        self.size = size

        if self.size < self.min_start_bytes + 1:
            raise PartitioningError('Device size must be greater than %d '
                                    'bytes' % self.min_start_bytes)
        
        # Get sector size
        self.sector_size = self.getSectorSize(location)
        self.location = location

        # Populate Device attributes from keyword args
        self.__dict__.update(**kwargs)

        if self.partition_table_format.lower() == 'gpt':
            self.max_allowed_partitions = 128
        else:
            self.max_allowed_partitions = 4

        # Process Device size
        start = (self.start_offset * 512) / self.sector_size
        # Sector quantities in the specification are assumed to be 512 bytes
        # This converts to the real sector size
        if (start * self.sector_size) < self.min_start_bytes:
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
            self.extent = Extent(start=start,
                                 end=(disk_size_sectors - gpt_size))
        else:
            self.extent = Extent(start=start, end=disk_size_sectors)

        self.updatePartitions()

    def updatePartitions(self, partitions=None):
        """
        Populate parts with Partition objects from a list of attributes

        @param partitions: List of partition attributes
        @type partitions:  list
        """
        self.partition_list = PartitionList(self)
        if partitions:
            self.partitions = partitions
        if hasattr(self, 'partitions'):
            for partition_args in self.partitions:
                print partition_args
                self.addPartition(**partition_args)

    def addPartition(self, **kwargs):
        '''
        Add a partition by dict of attributes

        See the Partition class for details of the required attributes
        '''
        partition = Partition(**kwargs)
        if len(self.partition_list) < self.max_allowed_partitions:
            self.partition_list.append(partition)
        else:
            raise PartitioningError('Exceeded maximum number of partitions '
                                    'for %s partition table (%d)' %
                                    (self.partition_table_format.upper(),
                                     self.max_allowed_partitions))

    # TODO: split out
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
            raise PartitioningError('Error reading information from fdisk')

    @staticmethod
    def commit(self):
        """
        Write the partition table to disk

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

    def __str__(self):
        return '<Device: location=%s, size=%s>' % (self.location, self.size)



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
#               size_sectors = (size_bytes / sector_size +
#                              ((size_bytes % 4096) != 0) *
#                              (4096 / sector_size))

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


class PartitioningError(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


