# -*- coding: utf-8 -*-
"""
Module for dealing with npm framework.

Provides some helper functions that deal with package.json, and also the
setuptools integration of certain npm features.
"""

from functools import partial
from subprocess import check_output

from calmjs.cli import Driver
from calmjs.cli import locale
from calmjs.dist import write_json_file
from calmjs.command import GenericPackageManagerCommand

PACKAGE_FIELD = 'package_json'
PACKAGE_JSON = 'package.json'
NPM = 'npm'

_inst = Driver(
    interactive=False, pkg_manager_bin=NPM, pkgdef_filename=PACKAGE_JSON)
get_node_version = _inst.get_node_version
get_npm_version = _inst.get_npm_version
npm_init = _inst.npm_init
npm_install = _inst.npm_install
package_json = _inst.pkgdef_filename

write_package_json = partial(write_json_file, PACKAGE_FIELD)


class npm(GenericPackageManagerCommand):
    """
    The npm specific setuptools command.
    """

    cli_driver = _inst
    description = "npm compatibility helper"

npm._initialize_user_options()


def npm_bin():
    """
    Returns output of 'npm bin' from the current working directory.
    """

    try:
        return check_output([NPM, 'bin']).decode(locale).strip()
    except OSError:
        return None
