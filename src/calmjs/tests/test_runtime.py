# -*- coding: utf-8 -*-
import unittest
import json
import os
import sys
from os.path import join

import pkg_resources

from calmjs import cli
from calmjs import runtime

from calmjs.testing import mocks
from calmjs.testing.utils import make_dummy_dist
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import remember_cwd
from calmjs.testing.utils import stub_dist_flatten_egginfo_json
from calmjs.testing.utils import stub_mod_call
from calmjs.testing.utils import stub_mod_check_interactive
from calmjs.testing.utils import stub_stdouts


class PackageManagerDriverTestCase(unittest.TestCase):
    """
    Test cases for the package manager driver and argparse usage.
    """

    def test_command_creation(self):
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        cmd = runtime.PackageManagerRuntime(driver)
        text = cmd.argparser.format_help()
        self.assertIn(
            "run 'mgr install' with generated 'default.json';", text,
        )

    def test_duplicate_init_no_error(self):
        driver = cli.PackageManagerDriver(pkg_manager_bin='mgr')
        cmd = runtime.PackageManagerRuntime(driver)
        cmd.init()

    def test_root_runtime_errors_ignored(self):
        stub_stdouts(self)
        working_set = mocks.WorkingSet({'calmjs.runtime': [
            'foo = calmjs.nosuchmodule:no.where',
            'bar = calmjs.npm:npm',
            'npm = calmjs.npm:npm.runtime',
        ]})
        rt = runtime.Runtime(working_set=working_set)
        with self.assertRaises(SystemExit):
            rt(['-h'])
        self.assertNotIn('foo', sys.stdout.getvalue())
        self.assertIn('npm', sys.stdout.getvalue())


class IntegrationTestCase(unittest.TestCase):

    def test_calmjs_main_console_entry_point(self):
        stub_stdouts(self)
        with self.assertRaises(SystemExit):
            runtime.main(['-h'])
        # ensure our base action module/class is registered.
        self.assertIn('npm', sys.stdout.getvalue())

    def setup_runtime(self):
        make_dummy_dist(self, (
            ('package.json', json.dumps({
                'name': 'site',
                'dependencies': {
                    'jquery': '~3.1.0',
                },
            })),
        ), 'example.package1', '1.0')

        make_dummy_dist(self, (
            ('package.json', json.dumps({
                'name': 'site',
                'dependencies': {
                    'underscore': '~1.8.3',
                },
            })),
        ), 'example.package2', '2.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        # Stub out the underlying data needed for the cli for the tests
        # to test against our custom data for reproducibility.
        stub_dist_flatten_egginfo_json(self, [cli], working_set)
        stub_mod_check_interactive(self, [cli], True)

        # Of course, apply a mock working set for the runtime instance
        # so it can use the npm runtime, however we will use a different
        # keyword.  Note that the runtime is invoked using foo.
        working_set = mocks.WorkingSet({
            'calmjs.runtime': [
                'foo = calmjs.npm:npm.runtime',
            ],
        })
        return runtime.Runtime(working_set=working_set)

    def test_npm_init_integration(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)

        rt = self.setup_runtime()
        rt(['foo', '--init', 'example.package1'])

        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result['dependencies']['jquery'], '~3.1.0')

    def test_npm_install_integration(self):
        remember_cwd(self)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        stub_mod_call(self, cli)
        rt = self.setup_runtime()
        rt(['foo', '--install', 'example.package1', 'example.package2'])

        with open(join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        self.assertEqual(result['dependencies']['jquery'], '~3.1.0')
        self.assertEqual(result['dependencies']['underscore'], '~1.8.3')
        # not foo install, but npm install since entry point specified
        # the actual runtime instance.
        self.assertEqual(self.call_args, ((['npm', 'install'],), {}))
