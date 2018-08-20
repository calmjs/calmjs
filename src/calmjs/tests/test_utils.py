# -*- coding: utf-8 -*-
import unittest
import errno
import io
import logging
import os
from os.path import join
from os.path import pathsep
import sys

from calmjs.utils import json_dump
from calmjs.utils import json_dumps
from calmjs.utils import requirement_comma_list
from calmjs.utils import which
from calmjs.utils import enable_pretty_logging
from calmjs.utils import finalize_env
from calmjs.utils import fork_exec
from calmjs.utils import pretty_logging
from calmjs.utils import raise_os_error

from calmjs.testing.mocks import StringIO
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import stub_os_environ
from calmjs.testing.utils import remember_cwd


class JsonDumpTestCase(unittest.TestCase):

    def test_dump(self):
        stream = StringIO()
        json_dump({'a': 'b', 'c': 'd'}, stream)
        self.assertEqual(
            stream.getvalue(),
            '{\n    "a": "b",\n    "c": "d"\n}'
        )

    def test_dumps(self):
        self.assertEqual(
            json_dumps({'a': 'b', 'c': 'd'}),
            '{\n    "a": "b",\n    "c": "d"\n}'
        )


class RequirementCommaListTestCase(unittest.TestCase):

    def test_basic(self):
        self.assertEqual(
            ['some', 'simple', 'test.foo'],
            requirement_comma_list.split('some,simple,test.foo'),
        )

    def test_with_requirement_commas(self):
        self.assertEqual(
            ['some', 'simple[part1]', 'test.foo[part2,part3,part4]'],
            requirement_comma_list.split(
                'some,simple[part1],test.foo[part2,part3,part4]'),
        )


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
        self.assertEqual(which(f), f)
        os.environ['PATH'] = ''
        self.assertEqual(which('binary', path=tempdir), f)
        self.assertEqual(which(f, path=tempdir), f)

    def test_found_posix_relpath(self):
        remember_cwd(self)
        sys.platform = 'posix'
        os.chdir(mkdtemp(self))
        os.mkdir('bin')
        bin_dir = os.environ['PATH'] = join(os.path.curdir, 'bin')
        f = join(bin_dir, 'binary')
        with open(f, 'w'):
            pass
        os.chmod(f, 0o777)
        self.assertEqual(which(f), f)

    def test_found_win32(self):
        sys.platform = 'win32'
        tempdir = os.environ['PATH'] = mkdtemp(self)
        os.environ['PATHEXT'] = pathsep.join(('.com', '.exe', '.bat'))
        f = join(tempdir, 'binary.exe')
        with open(f, 'w'):
            pass
        os.chmod(f, 0o777)
        self.assertEqual(which('binary'), f)
        self.assertEqual(which('binary.exe'), f)
        self.assertEqual(which(f), f)
        self.assertIsNone(which('binary.com'))

        os.environ['PATH'] = ''
        self.assertEqual(which('binary', path=tempdir), f)
        self.assertEqual(which('binary.exe', path=tempdir), f)
        self.assertEqual(which(f, path=tempdir), f)
        self.assertIsNone(which('binary.com', path=tempdir))

    def test_finalize_env_others(self):
        sys.platform = 'others'
        self.assertEqual(sorted(finalize_env({}).keys()), ['PATH'])

    def test_finalize_env_win32(self):
        sys.platform = 'win32'

        # when os.environ is empty or missing the required keys, the
        # values will be empty strings.
        os.environ = {}
        self.assertEqual(finalize_env({}), {
            'APPDATA': '', 'PATH': '', 'PATHEXT': '', 'SYSTEMROOT': ''})

        # should be identical with the keys copied
        os.environ['APPDATA'] = 'C:\\Users\\Guest\\AppData\\Roaming'
        os.environ['PATH'] = 'C:\\Windows'
        os.environ['PATHEXT'] = pathsep.join(('.com', '.exe', '.bat'))
        os.environ['SYSTEMROOT'] = 'C:\\Windows'
        self.assertEqual(finalize_env({}), os.environ)

    # This test is done with conjunction with finalize_env to mimic how
    # this is typically used within the rest of the library.

    def test_fork_exec_bytes(self):
        stdout, stderr = fork_exec(
            [sys.executable, '-c', 'import sys;print(sys.stdin.read())'],
            stdin=b'hello',
            env=finalize_env({}),
        )
        self.assertEqual(stdout.strip(), b'hello')

    def test_fork_exec_str(self):
        stdout, stderr = fork_exec(
            [sys.executable, '-c', 'import sys;print(sys.stdin.read())'],
            stdin=u'hello',
            env=finalize_env({}),
        )
        self.assertEqual(stdout.strip(), u'hello')

    # ensure the right error is raised for the running python version

    def test_raise_os_error_file_not_found(self):
        e = OSError if sys.version_info < (
            3, 3) else FileNotFoundError  # noqa: F821
        with self.assertRaises(e):
            raise_os_error(errno.ENOENT)

    def test_raise_os_error_not_dir(self):
        e = OSError if sys.version_info < (
            3, 3) else NotADirectoryError  # noqa: F821
        with self.assertRaises(e) as exc:
            raise_os_error(errno.ENOTDIR)

        self.assertIn('Not a directory', str(exc.exception))

    def test_raise_os_error_not_dir_with_path(self):
        e = OSError if sys.version_info < (
            3, 3) else NotADirectoryError  # noqa: F821
        with self.assertRaises(e) as exc:
            raise_os_error(errno.ENOTDIR, 'some_path')

        self.assertIn("Not a directory: 'some_path'", str(exc.exception))


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
