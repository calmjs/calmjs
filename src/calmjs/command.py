# -*- coding: utf-8 -*-
"""
Module providing npm distutil command that ultimately integrates with
setuptools
"""

from distutils.core import Command
from distutils.errors import DistutilsOptionError

from calmjs.npm import PACKAGE_JSON
from calmjs import cli


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
        ('overwrite', None,
         "overwrite configuration files (such as package.json)"),
        ('merge', None,
         "merge configuration files if possible (such as package.json)"),
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
        # TODO figure out best practices to get the logs from the cli
        # module/class outputting via here.
        # log.info(
        #     "Generating a flattened '%s' for '%s'",
        #     cli.package_json, pkg_name)
        cli.npm_init(pkg_name, overwrite=self.overwrite, merge=self.merge)

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
