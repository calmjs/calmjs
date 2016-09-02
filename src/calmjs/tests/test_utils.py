# -*- coding: utf-8 -*-
import unittest
import errno
import io
import logging
import os
from os.path import join
from os.path import pathsep
import sys

from calmjs.utils import which
from calmjs.utils import enable_pretty_logging
from calmjs.utils import pretty_logging
from calmjs.utils import raise_os_error

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

    # ensure the right error is raised for the running python version

    def test_raise_os_error_file_not_found(self):
        e = OSError if sys.version_info < (
            3, 0) else FileNotFoundError  # noqa: F821
        with self.assertRaises(e):
            raise_os_error(errno.ENOENT)

    def test_raise_os_error_not_dir(self):
        e = OSError if sys.version_info < (
            3, 0) else NotADirectoryError  # noqa: F821
        with self.assertRaises(e):
            raise_os_error(errno.ENOTDIR)


class LoggingTestCase(unittest.TestCase):
    """
    Pretty logging can be pretty.
    """

    def test_enable_pretty_logging(self):
        logger_id = 'calmjs.testing.dummy_logger'
        logger = logging.getLogger(logger_id)
        self.assertEqual(len(logger.handlers), 0)
        cleanup1 = enable_pretty_logging(logger=logger_id)
        self.assertEqual(len(logger.handlers), 1)
        cleanup2 = enable_pretty_logging(logger=logger)
        self.assertEqual(len(logger.handlers), 2)
        cleanup1()
        cleanup2()
        self.assertEqual(len(logger.handlers), 0)

    def test_logging_contextmanager(self):
        logger_id = 'calmjs.testing.dummy_logger'
        logger = logging.getLogger(logger_id)
        stream = io.StringIO()
        with pretty_logging(logger=logger_id, stream=stream) as fd:
            logger.info(u'hello')

        self.assertIs(fd, stream)
        self.assertIn(u'hello', stream.getvalue())
        self.assertEqual(len(logger.handlers), 0)
