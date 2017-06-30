# -*- coding: utf-8 -*-
"""
Module for dealing with npm framework via yarn.

Provides some helper functions that deal with package.json, and also the
setuptools integration of certain yarn features.
"""

from __future__ import absolute_import

from calmjs.cli import get_bin_version
from calmjs.cli import PackageManagerDriver
from calmjs.command import PackageManagerCommand
from calmjs.runtime import PackageManagerRuntime

PACKAGE_FIELD = 'package_json'
PACKAGE_JSON = package_json = 'package.json'
YARN = 'yarn'


class Driver(PackageManagerDriver):

    def __init__(self, **kw):
        kw['pkg_manager_bin'] = YARN
        kw['pkgdef_filename'] = PACKAGE_JSON
        kw['description'] = "yarn compatibility helper"
        super(Driver, self).__init__(**kw)

    def get_pkg_manager_version(self):
        kw = self._gen_call_kws()
        return get_bin_version(
            self.pkg_manager_bin, version_flag='--version', kw=kw)


class yarn(PackageManagerCommand):
    """
    The yarn specific setuptools command.
    """

    # modules globals will be populated with friendly exported names.
    cli_driver = Driver.create_for_module_vars(globals())
    runtime = PackageManagerRuntime(
        cli_driver, package_name='calmjs',
        description='yarn support for the calmjs framework',
    )
    description = cli_driver.description


yarn._initialize_user_options()

if __name__ == '__main__':  # pragma: no cover
    yarn.runtime()
