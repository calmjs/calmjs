# -*- coding: utf-8 -*-
"""
Module for dealing with npm framework.

Provides some helper functions that deal with package.json, and also the
setuptools integration of certain npm features.
"""

from __future__ import absolute_import

import json
from functools import partial
from os.path import exists
from os.path import join
from logging import getLogger

from calmjs.cli import PackageManagerDriver
from calmjs.command import PackageManagerCommand
from calmjs.dist import write_json_file
from calmjs.runtime import PackageManagerRuntime

PACKAGE_FIELD = 'package_json'
PACKAGE_JSON = package_json = 'package.json'
NPM = 'npm'
write_package_json = partial(write_json_file, PACKAGE_FIELD)
logger = getLogger(__name__)


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


def locate_package_entry_file(working_dir, package_name):
    """
    Locate a single npm package to return its browser or main entry.
    """

    basedir = join(working_dir, 'node_modules', package_name)
    package_json = join(basedir, 'package.json')
    if not exists(package_json):
        logger.debug(
            "could not locate package.json for the npm package '%s' in the "
            "current working directory '%s'; the package may have been "
            "not installed, the build process may fail",
            package_name, working_dir,
        )
        return

    with open(package_json) as fd:
        package_info = json.load(fd)

    if ('browser' in package_info or 'main' in package_info):
        # assume the target file exists because configuration files
        # never lie /s
        return join(
            basedir,
            *(package_info.get('browser') or package_info['main']).split('/')
        )

    index_js = join(basedir, 'index.js')
    if exists(index_js):
        return index_js

    logger.debug(
        "package.json for the npm package '%s' does not contain a main "
        "entry point", package_name,
    )


npm._initialize_user_options()

if __name__ == '__main__':  # pragma: no cover
    npm.runtime()
