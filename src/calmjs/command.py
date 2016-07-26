# -*- coding: utf-8 -*-
"""
Module providing npm distutil command that ultimately integrates with
setuptools
"""

from distutils.core import Command
from distutils.errors import DistutilsOptionError
from distutils import log

import json

from calmjs.npm import PACKAGE_JSON
from calmjs import cli
from calmjs.dist import flatten_package_json


# class names in lower case simply due to setuptools using this verbatim
# as the command name when showing user help.

class npm(Command):
    """
    Simple compatibility hook for npm.
    """

    description = "npm compatibility helper"
    package_json = PACKAGE_JSON
    indent = 4

    user_options = [
        ('init', None,
         "generate package.json and write to current dir"),
        ('install', None,
         "runs npm install with package.json in current directory"),
    ]
    # TODO implement support for other install args like specifying the
    # location of stuff.

    def _opt_keys(self):
        for opt in self.user_options:
            yield opt[0]

    def initialize_options(self):
        for key in self._opt_keys():
            setattr(self, key, False)

    def do_init(self):
        pkg_name = self.distribution.get_name()
        with open(PACKAGE_JSON, 'w') as fd:
            log.info(
                "Generating a flattened '%s' for '%s'",
                self.package_json, pkg_name)
            json.dump(
                flatten_package_json(
                    pkg_name, filename=self.package_json,
                ),
                fd, indent=self.indent)

    def finalize_options(self):
        opts = [i for i in (getattr(self, k) for k in self._opt_keys()) if i]
        if not opts:
            name = self.get_command_name()
            raise DistutilsOptionError(
                'must specify an action flag; see %s --help' % name)

    def run(self):
        self.run_command('egg_info')
        if self.dry_run:
            # Everything else will do a lot of naughty things so...
            return

        if self.init:
            self.do_init()

        if self.install:
            cli.npm_install(package_name=self.distribution.get_name())
