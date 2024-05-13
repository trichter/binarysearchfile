# (C) 2024, Tom Eulenfeld, MIT license

from os.path import join
from tempfile import TemporaryDirectory
import unittest

from binarysearchfile import BinarySearchFile, BinarySequentialFile, DTypeDef


class BinarySearchFileTestCase(unittest.TestCase):
    def test_methods(self):
        data = [('test1', 3), ('test4', 6), ('test2', 1), ('test3', 10),
                ('test3', 5)]
        with TemporaryDirectory() as tmpdir:
            path = join(tmpdir, 'test.bsf')
            bsf = BinarySearchFile(path)
            bsf.write(data)
            self.assertEqual(bsf['test3'], ('test3', 5))
            self.assertEqual(bsf.search('test3', first=False), 3)
            self.assertEqual(len(bsf.getall('test3')), 2)
            self.assertEqual(len(bsf.read()), len(bsf))
            self.assertEqual(bsf.read(0), ('test1', 3))
            self.assertEqual(len(bsf.read((0, 2))), 2)
            bsf.update([('test99', 1)])
            self.assertEqual(len(bsf), 6)
            self.assertIn('size', str(bsf))
            # print(bsf['testX'])
            with self.assertRaises(ValueError):
                bsf['testX']

            self.assertTrue(BinarySearchFile.check_magic(path))
            self.assertFalse(
                BinarySearchFile.check_magic(join(tmpdir, 'none')))

            bsf = BinarySearchFile(path + 'x')
            self.assertIn('does not exist', str(bsf))

            with open(path, mode='r+b') as f:
                f.write(b'x')  # wrong magic byte
                f.seek(0, 2)
                f.write(b'bla')  # wrong size
            bsf = BinarySearchFile(path)
            with self.assertWarnsRegex(UserWarning, 'Wrong magic'):
                self.assertEqual(bsf['test3'], ('test3', 5))

    def test_inheritance(self):
        class MyBinarySearchFile(BinarySearchFile):
            magic = b'\xfe\xff\x01\x01'
            headerstart = b'MyBinarySearchFile'
            record = (10, 10)
        with TemporaryDirectory() as tmpdir:
            path = join(tmpdir, 'test.bsf')
            bsf = MyBinarySearchFile(path)
            bsf.write([(10, 10), (4, 10), (5, 5)])
            self.assertEqual(bsf.search(10), 2)
            self.assertIn('MyBinary', str(bsf))
            bsf = BinarySearchFile(path)
            self.assertEqual(bsf.search(10), 2)

    def test_inttypes(self):
        class MyBinarySearchFile(BinarySearchFile):
            record = (10, 11, 10)
        data = list(zip(range(256), list(range(-127, 128)) + [127], [0] * 256))
        with TemporaryDirectory() as tmpdir:
            path = join(tmpdir, 'test.bsf')
            bsf = MyBinarySearchFile(path)
            bsf.write(data)
            self.assertEqual(bsf.read(), data)
            self.assertEqual(bsf.attr.recsize, 2)
            self.assertEqual(bsf.size, [1, 1, 0])
        data = list(zip(range(257), list(range(-127, 129)) + [128], [0] * 257))
        with TemporaryDirectory() as tmpdir:
            path = join(tmpdir, 'test.bsf')
            bsf = MyBinarySearchFile(path)
            bsf.write(data)
            self.assertTrue(MyBinarySearchFile.check_magic(path))
            self.assertTrue(BinarySearchFile.check_magic(path))
            self.assertEqual(bsf.read(), data)
            self.assertEqual(bsf.attr.recsize, 4)
            self.assertEqual(bsf.size, [2, 2, 0])

    def test_newtypes(self):
        class MyBinarySearchFile(BinarySearchFile):
            DTYPE = BinarySearchFile.DTYPE.copy()
            DTYPE[100] = DTypeDef(
                'fixedlenint', 5,
                encode=lambda v, s: v.to_bytes(s),
                decode=lambda v: int.from_bytes(v)
            )
            record = [100]
        with TemporaryDirectory() as tmpdir:
            path = join(tmpdir, 'test.bsf')
            bsf = MyBinarySearchFile(path)
            bsf.write([(100,), (200,)])
            self.assertEqual(bsf.get(100), (100,))
            self.assertEqual(bsf.size[0], 5)

    def test_seqfile(self):
        with TemporaryDirectory() as tmpdir:
            path = join(tmpdir, 'test.bsf')
            with BinarySequentialFile(path) as b:
                b.write(('test', 10))
                self.assertEqual(b[0], ('test', 10))
            with BinarySequentialFile(path) as b:
                self.assertEqual(b[0], ('test', 10))
                b.write(('test2', 11))
                b[0] = ('test1', 12)
                data = [('test1', 12), ('test2', 11)]
                self.assertEqual(b.read(), data)
                self.assertIn('size', str(b))
                self.assertEqual(b[:], data)
                self.assertEqual(b[::-1], data[::-1])
                self.assertEqual(b[1:], data[1:])
                self.assertEqual(b[:-1], data[:-1])
                self.assertEqual(b[1::-1], data[1::-1])
            self.assertTrue(BinarySequentialFile.check_magic(path))


if __name__ == '__main__':
    unittest.main()
