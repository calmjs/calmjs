# -*- coding: utf-8 -*-
import unittest

from calmjs.cli import PackageManagerDriver
from calmjs.runtime import PackageManagerRuntime


class PackageManagerDriverTestCase(unittest.TestCase):
    """
    Test cases for the package manager driver and argparse usage.
    """

    # def setUp(self):
    #     stub_stdouts(self)

    def test_command_creation(self):
        driver = PackageManagerDriver(pkg_manager_bin='mgr')
        cmd = PackageManagerRuntime(driver)
        text = cmd.argparser.format_help()
        self.assertIn(
            "action: run 'mgr install' with generated 'default.json';",
            text,
        )
