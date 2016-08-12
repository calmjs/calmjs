# -*- coding: utf-8 -*-
"""
Module for dealing with npm framework.

Provides some helper functions that deal with package.json, and also the
setuptools integration of certain npm features.
"""

from functools import partial

from calmjs import cli
from calmjs.dist import write_json_file
from calmjs.command import GenericPackageManagerCommand

PACKAGE_FIELD = 'package_json'
PACKAGE_JSON = package_json = 'package.json'
NPM = 'npm'
write_package_json = partial(write_json_file, PACKAGE_FIELD)


class Driver(cli.PackageManagerDriver):

    def __init__(self, **kw):
        kw['pkg_manager_bin'] = NPM
        kw['pkgdef_filename'] = PACKAGE_JSON
        super(Driver, self).__init__(**kw)


class npm(GenericPackageManagerCommand):
    """
    The npm specific setuptools command.
    """

    # modules globals will be populated with friendly exported names.
    cli_driver = Driver.create(globals())
    description = "npm compatibility helper"

npm._initialize_user_options()
