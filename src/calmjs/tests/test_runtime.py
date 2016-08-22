# -*- coding: utf-8 -*-
import unittest
import sys

from calmjs.cli import PackageManagerDriver
from calmjs import runtime

from calmjs.testing.mocks import WorkingSet
from calmjs.testing.utils import stub_stdouts


class PackageManagerDriverTestCase(unittest.TestCase):
    """
    Test cases for the package manager driver and argparse usage.
    """

    def test_command_creation(self):
        driver = PackageManagerDriver(pkg_manager_bin='mgr')
        cmd = runtime.PackageManagerRuntime(driver)
        text = cmd.argparser.format_help()
        self.assertIn(
            "action: run 'mgr install' with generated 'default.json';",
            text,
        )

    def test_duplicate_init_no_error(self):
        driver = PackageManagerDriver(pkg_manager_bin='mgr')
        cmd = runtime.PackageManagerRuntime(driver)
        cmd.init()

    def test_root_runtime_errors_ignored(self):
        stub_stdouts(self)
        working_set = WorkingSet([
            'foo = calmjs.nosuchmodule:no.where',
            'bar = calmjs.npm:npm',
            'npm = calmjs.npm:npm.runtime',
        ])
        rt = runtime.Runtime(working_set=working_set)
        with self.assertRaises(SystemExit):
            rt(['-h'])
        self.assertNotIn('foo', sys.stdout.getvalue())
        self.assertIn('npm', sys.stdout.getvalue())


class IntegrationTestCase(unittest.TestCase):

    def test_calmjs_entry_integration(self):
        stub_stdouts(self)
        with self.assertRaises(SystemExit):
            runtime.main(['-h'])
        self.assertIn('npm', sys.stdout.getvalue())
