# -*- coding: utf-8 -*-
import unittest
import json
import os
from os.path import join
from os.path import exists

from distutils.errors import DistutilsOptionError
from setuptools.dist import Distribution
import pkg_resources

from calmjs import command
from calmjs import cli
from calmjs import dist
from calmjs import npm
from calmjs.testing.utils import make_dummy_dist
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import stub_mod_call


def make_flatten_package_json(working_set):

    def flatten_package_json(pkg_name, filename=npm.PACKAGE_JSON):
        return dist.flatten_package_json(
            pkg_name, filename=filename, working_set=working_set)

    return flatten_package_json


class DistCommandTestCase(unittest.TestCase):
    """
    Test case for the commands within.
    """

    def setUp(self):
        self.cwd = os.getcwd()

        app = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.11.0'},
            })),
        ), 'foo', '1.9.0')

        working_set = pkg_resources.WorkingSet()
        working_set.add(app, self._calmjs_testing_tmpdir)

        # Stub out the flatten_package_json calls with one that uses our
        # custom working_set here.
        new_flatten_package_json = make_flatten_package_json(working_set)
        command.flatten_package_json = new_flatten_package_json
        cli.flatten_package_json = new_flatten_package_json

    def tearDown(self):
        os.chdir(self.cwd)
        command.flatten_package_json = dist.flatten_package_json
        cli.flatten_package_json = dist.flatten_package_json

    def test_no_args(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm'],
            name='foo',
        ))
        dist.parse_command_line()
        with self.assertRaises(DistutilsOptionError):
            dist.run_commands()

    def test_init(self):
        tmpdir = mkdtemp(self)

        with open(os.path.join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {}, 'devDependencies': {}}, fd)

        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--init'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # gets overwritten anyway.
        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
        })

    def test_install_no_init(self):
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--install'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # The cli will still automatically write to that.
        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
        })
        self.assertEqual(self.call_args, ((['npm', 'install'],), {}))

    def test_install_no_init_has_package_json(self):
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)

        with open(os.path.join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({
                'dependencies': {'jquery': '~3.0.0'},
                'devDependencies': {}
            }, fd)

        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--install'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # Existing package.json will not be overwritten.
        self.assertEqual(result, {
            'dependencies': {'jquery': '~3.0.0'},
            'devDependencies': {},
        })

    def test_install_false(self):
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--install', '--dry-run'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        self.assertFalse(exists(join(tmpdir, 'package.json')))
        self.assertIsNone(self.call_args)
