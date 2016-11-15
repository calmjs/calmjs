# -*- coding: utf-8 -*-
"""
Module for dealing with npm framework.

Provides some helper functions that deal with package.json, and also the
setuptools integration of certain npm features.
"""

from __future__ import absolute_import

from functools import partial

from calmjs.cli import PackageManagerDriver
from calmjs.command import PackageManagerCommand
from calmjs.dist import write_json_file
from calmjs.runtime import PackageManagerRuntime

PACKAGE_FIELD = 'package_json'
PACKAGE_JSON = package_json = 'package.json'
NPM = 'npm'
write_package_json = partial(write_json_file, PACKAGE_FIELD)


class Driver(PackageManagerDriver):

    def __init__(self, **kw):
        kw['pkg_manager_bin'] = NPM
        kw['pkgdef_filename'] = PACKAGE_JSON
        kw['description'] = "npm compatibility helper"
        super(Driver, self).__init__(**kw)


class npm(PackageManagerCommand):
    """
    The npm specific setuptools command.
    """

    # modules globals will be populated with friendly exported names.
    cli_driver = Driver.create_for_module_vars(globals())
    runtime = PackageManagerRuntime(
        cli_driver, package_name='calmjs',
        description='npm support for the calmjs framework',
    )
    description = cli_driver.description


npm._initialize_user_options()

if __name__ == '__main__':  # pragma: no cover
    npm.runtime()
