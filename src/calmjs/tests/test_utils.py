# -*- coding: utf-8 -*-
import unittest
import os
from os.path import join
from os.path import pathsep
import sys

from calmjs.utils import which

from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import stub_os_environ


class WhichTestCase(unittest.TestCase):
    """
    Yeah, which?
    """

    def setUp(self):
        self._platform = sys.platform
        stub_os_environ(self)

    def tearDown(self):
        sys.platform = self._platform

    def test_nothing(self):
        os.environ['PATH'] = ''
        self.assertIsNone(which('ls'))

    def test_dupe_skip(self):
        os.environ['PATH'] = pathsep.join(
            (os.environ['PATH'], os.environ['PATH']))
        which('ls')
        which('cmd')

    # Well, we are not dependent on the result, but at the very least
    # test that the code is covered and won't randomly blow up.

    def test_found_posix(self):
        sys.platform = 'posix'
        tempdir = os.environ['PATH'] = mkdtemp(self)
        f = join(tempdir, 'binary')
        with open(f, 'w'):
            pass
        os.chmod(f, 0o777)
        self.assertEqual(which('binary'), f)
        os.environ['PATH'] = ''
        self.assertEqual(which('binary', path=tempdir), f)

    def test_found_nt(self):
        sys.platform = 'win32'
        tempdir = os.environ['PATH'] = mkdtemp(self)
        os.environ['PATHEXT'] = pathsep.join(('.com', '.exe', '.bat'))
        f = join(tempdir, 'binary.exe')
        with open(f, 'w'):
            pass
        os.chmod(f, 0o777)
        self.assertEqual(which('binary'), f)
        self.assertEqual(which('binary.exe'), f)
        self.assertIsNone(which('binary.com'))

        os.environ['PATH'] = ''
        self.assertEqual(which('binary', path=tempdir), f)
        self.assertEqual(which('binary.exe', path=tempdir), f)
        self.assertIsNone(which('binary.com', path=tempdir))
