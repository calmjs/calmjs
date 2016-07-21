# -*- coding: utf-8 -*-
import unittest
import json
import os
import tempfile
from os.path import join
from os.path import dirname
from shutil import rmtree

from calmjs import cli
from calmjs.testing.utils import mkdtemp


def fake_error(exception):
    def stub(*a, **kw):
        raise exception
    return stub


class CliTestCase(unittest.TestCase):
    """
    Base cli class test case.
    """

    def _fake_call(self, *a, **kw):
        self.call_args = (a, kw)

    def _fake_check_output(self, *a, **kw):
        self.check_output_args = (a, kw)
        return self.check_output_answer

    def setUp(self):
        # keep copy of original os.environ
        self.call_args = None
        self.check_output_args = None
        self.original_env = {}
        self.original_env.update(os.environ)

        # working directory
        self.cwd = os.getcwd()

        # Stub original module level functions
        self.original_call, cli.call = cli.call, self._fake_call
        # Save this original only
        self.original_check_output =  cli.check_output

        # other default values
        self.check_output_answer = None

    def tearDown(self):
        # restore original os.environ from copy
        os.environ.clear()
        os.environ.update(self.original_env)

        # Restore original module level functions
        cli.call = self.original_call
        cli.check_output = self.original_check_output

        os.chdir(self.cwd)

    def test_get_bin_version_long(self):
        cli.check_output = self._fake_check_output
        self.check_output_answer = b'Some app v.1.2.3.4. All rights reserved'
        results = cli._get_bin_version('some_app')
        self.assertEqual(results, (1, 2, 3, 4))

    def test_get_bin_version_longer(self):
        cli.check_output = self._fake_check_output
        # tags are ignored for now.
        self.check_output_answer = b'version.11.200.345.4928-what'
        results = cli._get_bin_version('some_app')
        self.assertEqual(results, (11, 200, 345, 4928))

    def test_get_bin_version_short(self):
        cli.check_output = self._fake_check_output
        self.check_output_answer = b'1'
        results = cli._get_bin_version('some_app')
        self.assertEqual(results, (1,))

    def test_get_bin_version_unexpected(self):
        cli.check_output = self._fake_check_output
        self.check_output_answer = b'Nothing'
        results = cli._get_bin_version('some_app')
        self.assertIsNone(results)

    def test_get_bin_version_no_bin(self):
        cli.check_output = fake_error(OSError)
        results = cli._get_bin_version('some_app')
        self.assertIsNone(results)

    def test_node_no_path(self):
        os.environ['PATH'] = ''
        self.assertIsNone(cli.get_node_version())

    def test_node_version_mocked(self):
        cli.check_output = self._fake_check_output
        self.check_output_answer = b'v0.10.25'
        version = cli.get_node_version()
        self.assertEqual(version, (0, 10, 25))

    @unittest.skipIf(cli.get_node_version() is None, 'nodejs not found.')
    def test_node_version_get(self):
        version = cli.get_node_version()
        self.assertIsNotNone(version)

    def test_npm_no_path(self):
        os.environ['PATH'] = ''
        self.assertIsNone(cli.get_npm_version())

    @unittest.skipIf(cli.get_npm_version() is None, 'npm not found.')
    def test_npm_version_get(self):
        version = cli.get_npm_version()
        self.assertIsNotNone(version)

    def test_set_node_path(self):
        custom_cli = cli.Cli(node_path='./node_mods')
        # environment locally here overridden.
        self.assertEqual(os.environ['NODE_PATH'], './node_mods')

    @unittest.skipIf(cli.get_npm_version() is None, 'npm not found.')
    def test_npm_install_package_json(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        # This is faked.
        cli.npm_install()
        # However we make sure that it's been fake called
        self.assertEqual(self.call_args, ((['npm', 'install'],), {}))
        # And that the JSON file was written to the temp dir as that was
        # set to be the current working directory by setup.

        with open(join(tmpdir, 'package.json')) as fd:
            config = json.load(fd)

        self.assertEqual(config, cli.make_package_json())

    @unittest.skipIf(cli.get_npm_version() is None, 'npm not found.')
    def test_npm_install_package_json_no_overwrite(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        # We are going to have a fake package.json
        with open(join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({}, fd)

        # This is faked.
        cli.npm_install()

        with open(join(tmpdir, 'package.json')) as fd:
            config = json.load(fd)
        # This should remain unchanged.
        self.assertEqual(config, {})
