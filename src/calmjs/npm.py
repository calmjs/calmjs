# -*- coding: utf-8 -*-
"""
Module for dealing with npm framework.

Provides some helper functions that deal with package.json, and also the
setuptools integration of certain npm features.
"""

from functools import partial

from calmjs.cli import Driver
from calmjs.dist import write_json_file
from calmjs.command import GenericPackageManagerCommand

PACKAGE_FIELD = 'package_json'
PACKAGE_JSON = 'package.json'
NPM = 'npm'

_inst = Driver(
    interactive=False, pkg_manager_bin=NPM, pkgdef_filename=PACKAGE_JSON)
get_node_version = _inst.get_node_version
get_npm_version = _inst.get_pkg_manager_version
npm_init = _inst.pkg_manager_init
npm_install = _inst.pkg_manager_install
package_json = _inst.pkgdef_filename

write_package_json = partial(write_json_file, PACKAGE_FIELD)


class npm(GenericPackageManagerCommand):
    """
    The npm specific setuptools command.
    """

    cli_driver = _inst
    description = "npm compatibility helper"

npm._initialize_user_options()
