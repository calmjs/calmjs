# -*- coding: utf-8 -*-
"""
Module for dealing with npm framework.

Provides some helper functions that deal with package.json, and also the
setuptools integration of certain npm features.
"""

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
        super(Driver, self).__init__(**kw)


class npm(PackageManagerCommand):
    """
    The npm specific setuptools command.
    """

    # modules globals will be populated with friendly exported names.
    cli_driver = Driver.create(globals())
    runtime = PackageManagerRuntime(cli_driver)
    description = "npm compatibility helper"

npm._initialize_user_options()
