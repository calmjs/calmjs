# -*- coding: utf-8 -*-
import unittest
import json
import os
from os.path import join
from os.path import exists

from calmjs import cli
from calmjs.testing.utils import fake_error
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import stub_mod_call
from calmjs.testing.utils import stub_mod_check_output


class CliDriverTestCase(unittest.TestCase):
    """
    Base cli driver class test case.
    """

    def setUp(self):
        # keep copy of original os.environ
        self.original_env = {}
        self.original_env.update(os.environ)
        # working directory
        self.cwd = os.getcwd()

    def tearDown(self):
        # restore original os.environ from copy
        os.environ.clear()
        os.environ.update(self.original_env)
        os.chdir(self.cwd)

    def test_get_bin_version_long(self):
        stub_mod_check_output(self, cli)
        self.check_output_answer = b'Some app v.1.2.3.4. All rights reserved'
        results = cli._get_bin_version('some_app')
        self.assertEqual(results, (1, 2, 3, 4))

    def test_get_bin_version_longer(self):
        stub_mod_check_output(self, cli)
        # tags are ignored for now.
        self.check_output_answer = b'version.11.200.345.4928-what'
        results = cli._get_bin_version('some_app')
        self.assertEqual(results, (11, 200, 345, 4928))

    def test_get_bin_version_short(self):
        stub_mod_check_output(self, cli)
        self.check_output_answer = b'1'
        results = cli._get_bin_version('some_app')
        self.assertEqual(results, (1,))

    def test_get_bin_version_unexpected(self):
        stub_mod_check_output(self, cli)
        self.check_output_answer = b'Nothing'
        results = cli._get_bin_version('some_app')
        self.assertIsNone(results)

    def test_get_bin_version_no_bin(self):
        stub_mod_check_output(self, cli, fake_error(OSError))
        results = cli._get_bin_version('some_app')
        self.assertIsNone(results)

    def test_node_no_path(self):
        os.environ['PATH'] = ''
        self.assertIsNone(cli.get_node_version())

    def test_node_version_mocked(self):
        stub_mod_check_output(self, cli)
        self.check_output_answer = b'v0.10.25'
        version = cli.get_node_version()
        self.assertEqual(version, (0, 10, 25))

    # live test, no stubbing
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
        stub_mod_call(self, cli)
        driver = cli.Driver(node_path='./node_mods')

        # ensure env is passed into the call.
        driver.pkg_manager_install()  # npm install
        self.assertEqual(self.call_args, ((['npm', 'install'],), {
            'env': {'NODE_PATH': './node_mods'},
        }))

    def test_set_binary(self):
        stub_mod_call(self, cli)
        driver = cli.Driver(pkg_manager_bin='bower')

        # this will call ``bower install`` instead.
        driver.pkg_manager_install()
        self.assertEqual(self.call_args, ((['bower', 'install'],), {}))

    @unittest.skipIf(cli.get_npm_version() is None, 'npm not found.')
    def test_npm_install_package_json(self):
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        # This is faked.
        cli.npm_install()
        # However we make sure that it's been fake called
        self.assertEqual(self.call_args, ((['npm', 'install'],), {}))
        self.assertFalse(exists(join(tmpdir, 'package.json')))

    @unittest.skipIf(cli.get_npm_version() is None, 'npm not found.')
    def test_npm_install_package_json_no_overwrite(self):
        stub_mod_call(self, cli)
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
