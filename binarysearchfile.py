# (C) 2024, Tom Eulenfeld, MIT license
"""
File layout:
Byte offset length
        +0    4    magic bytes,
                       1st byte is identifier of the classes defined here,
                       2nd byte is identifier of derived classes,
                       3rd byte is version of the classes defined here,
                       4th byte is version of derived classes,
                       therefore derived classes should only change 2nd and 4th magic byte
        +4    2    metaoffset (int, N), pointer to metadata, description of records
        +6    2    dataoffset (int, M), pointer to start of data records
        +8    N-8  textual header
       N+0    2    number of record fields (int, R)
        +2    1    type of first record field (int), defined in DTYPE class property
        +3    2    size of first record field (int)
       ...         type and size are given for all R record fields until byte M, sum of sizes is S
       M+0    S    first record with R fields with given size
       ...         All data records follow sequentially
       EOF
"""


from collections import namedtuple
from contextlib import contextmanager
from dataclasses import dataclass
import os.path
from warnings import warn


__version__ = '0.1.0'


def _rint(f, l):
    return int.from_bytes(f.read(l))


def _humanb(size, p=2):
    suf = ('', 'k', 'M', 'G', 'T')
    i = 0
    while size > 1024:
        i += 1
        size = size / 1024
    return f'{size:.{p}f} {suf[i]}Byte'


def _binarysearch(f, x, hi, left=True):
    lo = 0
    while lo < hi:
        mid = (lo+hi)//2
        if left and f(mid) < x or (not left and not x < f(mid)):
            lo = mid+1
        else:
            hi = mid
    return lo - (left == False)


def _byte_length(v):
    return (v.bit_length() + 7) // 8


DTypeDef = namedtuple('DType', ['name', 'len', 'encode', 'decode'])
DTYPE = {
    0: DTypeDef('ascii', len,
                encode=lambda v, s: v.encode('latin1').ljust(s, b' '),
                decode=lambda v: v.rstrip(b' ').decode('latin1')),
    1: DTypeDef('utf-8', lambda v: len(v.encode('utf-8')),
                encode=lambda v, s: v.encode('utf-8').ljust(s, b' '),
                decode=lambda v: v.rstrip(b' ').decode('utf-8')),
    10: DTypeDef('int', _byte_length,
                 encode=lambda v, s: v.to_bytes(s),
                 decode=lambda v: int.from_bytes(v)),
    11: DTypeDef('signedint', lambda v: _byte_length(2 * abs(v)),
                 encode=lambda v, s: v.to_bytes(s, signed=True),
                 decode=lambda v: int.from_bytes(v, signed=True))
}


@dataclass
class _Attr:
    """Class for keeping track of file attributes"""
    fname: str
    reclen: int = None
    recsize: int = None
    dataoffset: int = None
    metaoffset: int = None

    @property
    def len(self):
        if self.recsize in (0, None):
            return 0
        else:
            return (self.totalsize - self.dataoffset) // self.recsize

    @property
    def totalsize(self):
        return os.path.getsize(self.fname)


class BinarySearchFile():
    # may be overriden or extended
    DTYPE = DTYPE
    # should be overriden
    magic = b'\xfe\xfe\x01\x01'
    # 4B follow
    #   2B offset to metadata
    #   2B offset to data
    headerstart = b'BinarySearchFile'
    record = (0, 10)

    def __init__(self, fname):
        self.f = None
        self.header = None
        self.size = None
        self.attr = _Attr(fname=fname)

    @contextmanager
    def _open(self):
        if self.f is not None:
            yield self.f
        else:
            with open(self.attr.fname, 'rb') as self.f:
                yield self.f
            self.f = None

    @classmethod
    def check_magic(cls, fname, n=1):
        """Check first n bytes of magic string of file fname"""
        try:
            with open(fname, 'rb') as f:
                magic = f.read(4)
                return magic[:n] == cls.magic[:n]
        except:
            return False

    def _check_magic(self):
        with self._open() as f:
            f.seek(0)
            magic = f.read(4)
            if type(self) == BinarySearchFile:
                return magic[0] == self.magic[0]
            else:
                return magic[:2] == self.magic[:2]

    def read_header(self):
        """Read and return header of file, set properties attr, record, size"""
        if self.attr.reclen is None:
            with self._open() as f:
                if not self._check_magic():
                    warn(f'Wrong magic bytes in file {self.attr.fname}')
                # overide class attributes
                self.attr.metaoffset = _rint(f, 2)
                self.attr.dataoffset = _rint(f, 2)
                self.header = f.read(
                    self.attr.metaoffset - len(self.magic) - 4)
                assert f.tell() == self.attr.metaoffset
                self.attr.reclen = _rint(f, 2)
                self.record = []
                self.size = []
                for i in range(self.attr.reclen):
                    self.record.append(_rint(f, 1))
                    self.size.append(_rint(f, 2))
                self.attr.recsize = sum(self.size)
            if not self._sizecheck():
                warn(f'The size of file {self.attr.fname} is inconsistent')
        return self.header

    def __len__(self):
        self.read_header()
        return self.attr.len

    def _sizecheck(self):
        return self.attr.dataoffset + self.attr.len * self.attr.recsize == self.attr.totalsize

    def _get_key(self, i=None):
        """Get record key i or the key of the next record"""
        if i is not None:
            self.f.seek(self.attr.dataoffset + i * self.attr.recsize)
        bytes_ = self.f.read(self.size[0])
        return self.DTYPE[self.record[0]].decode(bytes_)

    def _get_data(self, i=None):
        """Get record i or the next record"""
        if i is not None:
            self.f.seek(self.attr.dataoffset + i * self.attr.recsize)
        data = tuple(self.DTYPE[record].decode(self.f.read(size))
                     for record, size in zip(self.record, self.size))
        return data

    def search(self, key, first=True):
        """Search for key and return the record number

        :param first: Wether too search for first or last occurence"""
        with self._open():
            self.read_header()
            recnum = _binarysearch(self._get_key, key, len(self), left=first)
            if key != self._get_key(recnum):
                raise ValueError(f'Key {key} not present in index')
        return recnum

    def get(self, key, first=True):
        """Search for key and return the full record

        :param first: Wether too search for first or last occurence"""
        with self._open():
            recnum = self.search(key, first=first)
            return self._get_data(recnum)

    def __getitem__(self, item):
        return self.get(item)

    def getall(self, key):
        """Search for key and return all records with this key"""
        with self._open():
            recnum = self.search(key)
            alldata = []
            fkey = key
            while key == fkey:
                alldata.append(self._get_data(recnum))
                recnum += 1
                fkey = self._get_key()
            return alldata

    def read(self, item=None):
        """Read and return all records"""
        with self._open():
            self.read_header()
            if item is None:
                self.f.seek(self.attr.dataoffset)
                return [self._get_data() for _ in range(len(self))]
            elif isinstance(item, int):
                self.f.seek(self.attr.dataoffset + item * self.attr.recsize)
                return self._get_data()
            i, j = item
            self.f.seek(self.attr.dataoffset + i * self.attr.recsize)
            return [self._get_data() for _ in range(i, j)]

    def write(self, data, header=b''):
        """Recreate file and write data records

        :param header: additional bytes appended to class property headerstart"""
        with open(self.attr.fname, 'wb') as f:
            f.write(self.magic)
            f.write(b'    ')  # reserve 4 bytes for metaoffset and dataoffset
            f.write(self.headerstart + header)
            metaoffset = f.tell()

            f.write(len(self.record).to_bytes(2))
            size = []
            for i, d in enumerate(zip(*sorted(data))):
                num = self.record[i]
                len_ = self.DTYPE[num].len
                if isinstance(len_, int):
                    s = len_
                else:
                    s = max(len_(d1) for d1 in d)
                size.append(s)
                f.write(num.to_bytes(1))
                f.write(s.to_bytes(2))

            dataoffset = f.tell()
            f.seek(len(self.magic))
            f.write(metaoffset.to_bytes(2))
            f.write(dataoffset.to_bytes(2))
            f.seek(dataoffset)

            for d in sorted(data):
                for i, field in enumerate(d):
                    encode = self.DTYPE[self.record[i]].encode
                    f.write(encode(field, size[i]))
        self.attr = _Attr(fname=self.attr.fname)
        self.header = None

    def update(self, data, header=None):
        """Update file with data records

        Note: The whole file is read and recreated from scratch to guarantee
        the correct sorting.

        :param header: additional bytes appended to class property headerstart
        """
        odata = self.read()
        if header is None:
            header = self.header
        else:
            header = self.headerstart + header
        return self.write(odata + data, header=header)

    def __str__(self):
        if not os.path.exists(self.attr.fname):
            return f'File {self.attr.fname} does not exist'
        self.read_header()
        return (f'{type(self).__name__}\n'
                f'     fname: {self.attr.fname}\n'
                f'   records: {len(self):_d}\n'
                f'      size: {_humanb(self.attr.totalsize)}\n'
                f'   recsize: {self.attr.recsize} Byte  {tuple(self.size)}\n')


class BinarySequentialFile():
    DTYPE = DTYPE

    magic = b'\xfe\xfe\x01\x01'
    headerstart = b'BinarySequentialFile'
    record = (0, 10)
    size = (20, 2)

    def __init__(self, fname, header=b''):
        self.f = None
        self.header = header
        self.attr = _Attr(fname=fname)
        self.open()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @classmethod
    def check_magic(cls, fname, n=1):
        try:
            with open(fname, 'rb') as f:
                magic = f.read(4)
                return magic[:n] == cls.magic[:n]
        except:
            return False

    def _check_magic(self):
        self.f.seek(0)
        magic = self.f.read(4)
        if type(self) == BinarySequentialFile:
            return magic[0] == self.magic[0]
        else:
            return magic[:2] == self.magic[:2]

    def _read_header(self):
        f = self.f
        if not self._check_magic():
            warn(f'Wrong magic bytes in file {self.attr.fname}')
        # overide class attributes
        self.attr.metaoffset = _rint(f, 2)
        self.attr.dataoffset = _rint(f, 2)
        self.header = f.read(self.attr.metaoffset - len(self.magic) - 4)
        assert f.tell() == self.attr.metaoffset
        self.attr.reclen = _rint(f, 2)
        self.record = []
        self.size = []
        for i in range(self.attr.reclen):
            self.record.append(_rint(f, 1))
            self.size.append(_rint(f, 2))
        self.attr.recsize = sum(self.size)
        if not self._sizecheck():
            warn(f'The size of file {self.attr.fname} is inconsistent')

    def _write_header(self):
        f = self.f
        attr = self.attr
        f.write(self.magic)
        f.write(b'    ')  # reserve 4 bytes for metaoffset and dataoffset
        self.header = self.headerstart + self.header
        f.write(self.header)
        attr.metaoffset = f.tell()
        attr.reclen = len(self.record)
        f.write(attr.reclen.to_bytes(2))
        for i in range(len(self.record)):
            num = self.record[i]
            s = self.size[i]
            f.write(num.to_bytes(1))
            f.write(s.to_bytes(2))
        attr.recsize = sum(self.size)
        attr.dataoffset = f.tell()
        f.seek(len(self.magic))
        f.write(attr.metaoffset.to_bytes(2))
        f.write(attr.dataoffset.to_bytes(2))
        f.seek(attr.dataoffset)

    def open(self):
        exists_before = os.path.exists(self.attr.fname)
        if not exists_before:
            f = open(self.attr.fname, mode='w')
            f.close()
        self.f = open(self.attr.fname, mode='r+b')
        if not exists_before:
            self._write_header()
        else:
            self._read_header()

    def close(self):
        self.f.close()

    def __len__(self):
        return self.attr.len

    def _sizecheck(self):
        return self.attr.dataoffset + self.attr.len * self.attr.recsize == self.attr.totalsize

    def _get_data(self, i=None):
        if i is not None:
            self.f.seek(self.attr.dataoffset + i * self.attr.recsize)
        data = tuple(self.DTYPE[record].decode(self.f.read(size))
                     for record, size in zip(self.record, self.size))
        return data

    def __getitem__(self, item):
        return self.read(item)

    def __setitem__(self, item, data):
        return self.write(data, i=item)

    def read(self, i=None):
        """Read specified record or all records"""
        if i is None:
            self.f.seek(self.attr.dataoffset)
            return [self._get_data() for _ in range(len(self))]
        elif isinstance(i, int):
            return self._get_data(i=i)
        if isinstance(i, slice):
            j, k, stride = i.indices(len(self))
            if abs(stride) != 1:
                raise ValueError('stride has to be 1 or -1')
            elif stride == -1:
                j, k = k+1, j+1
        else:
            raise ValueError('Index not supported')
        self.f.seek(self.attr.dataoffset + j * self.attr.recsize)
        return [self._get_data() for _ in range(j, k)][::stride]

    def write(self, data, i=None):
        """Write record at specified or next position"""
        if i is not None:
            self.f.seek(self.attr.dataoffset + i * self.attr.recsize)
        for i, field in enumerate(data):
            encode = self.DTYPE[self.record[i]].encode
            self.f.write(encode(field, self.size[i]))

    def __str__(self):
        return (f'{type(self).__name__}\n'
                f'     fname: {self.attr.fname}\n'
                f'   records: {len(self):_d}\n'
                f'      size: {_humanb(self.attr.totalsize)}\n'
                f'   recsize: {self.attr.recsize} Byte  {tuple(self.size)}\n')
