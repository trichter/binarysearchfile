# binarysearchfile
[![build status](https://github.com/trichter/binarysearchfile/workflows/tests/badge.svg)](https://github.com/trichter/binarysearchfile/actions)
[![codecov](https://codecov.io/gh/trichter/binarysearchfile/branch/master/graph/badge.svg)](https://codecov.io/gh/trichter/binarysearchfile)
[![pypi version](https://img.shields.io/pypi/v/binarysearchfile.svg)](https://pypi.python.org/pypi/binarysearchfile)
[![python version](https://img.shields.io/pypi/pyversions/binarysearchfile.svg)](https://python.org)
[![DOI](https://zenodo.org/badge/DOI/)](https://doi.org/)

Binary search sorted binary file for fast random access

## Usage

Define and use your own binary search file:

```py
from binarysearchfile import BinarySearchFile

class MyBinarySearchFile(BinarySearchFile):
    magic = b'\xfe\xff\x01\x01'  # magic string, you can change 2nd and 4th byte
    headerstart = b'MyBinarySearchFile'  # name of the file format
    record = (10, 10)  # record structure

bsf = MyBinarySearchFile('mybinarysearchfile')
data = [(10, 42), (4, 10), (5, 5)]
bsf.write(data)  # write sorted data
print(len(bsf))  # number of records
print(bsf.search(10))  # get index
print(bsf.get(10))  # get record
print(bsf)

#Output:
#3
#2
#(10, 42)
#MyBinarySearchFile
#     fname: mybinarysearchfile
#   records: 3
#      size: 40.00 Byte
#   recsize: 2 Byte  (1, 1)
```

The above example defines records consisting of two integers.
The first element ("key") in the record can be binary-searched.
Currently, the following types can be used out of the box:

```
0: ascii
1: utf-8
10: int
11: signedint
```

The file can be read by the original class:

```
bsf = BinarySearchFile('mybinarysearchfile')
print(bsf.get(10))

#Output:
#(10, 42)

```

### Defining your own data types

Use the following approach to define additional custom types with the DTypeDef class.
Its init method takes `name`, `len`, `encode` and `decode` arguments.
`len`, the byte length of an object, is usually a function of the object, but may be an integer for a fixed length.
Register custom types only with keys greater than 99.

```
from binarysearchfile import BinarySearchFile, DTypeDef

class MyBinarySearchFile(BinarySearchFile):
    DTYPE = BinarySearchFile.DTYPE.copy()
    DTYPE[100] = DTypeDef(
        'fixedlenint', 5,
        encode=lambda v, s: v.to_bytes(s),
        decode=lambda v: int.from_bytes(v)
        )
    # definitions of other class properties follow
```

### Use binary sequential file

We provide a `BinarySequentialFile` class that uses the same file layout and can be used for sequential reading and writing.

```
from binarysearchfile import BinarySequentialFile
with BinarySequentialFile('mybinarysearchfile') as bseqf:
    print(bseqf[2])
#Output:
#(10, 42)
```
