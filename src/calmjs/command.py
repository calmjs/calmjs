# -*- coding: utf-8 -*-
"""
Module providing npm distutil command that ultimately integrates with
setuptools
"""

import logging

from distutils.core import Command
from distutils.errors import DistutilsOptionError
from distutils import log

from calmjs import cli


class DistutilsLogHandler(logging.Handler):
    """
    A handler that streams the logs to the distutils logger
    """

    def __init__(self, distutils_log=log):
        logging.Handler.__init__(self)
        self.log = distutils_log
        # Basic numeric table
        self.level_table = {
            logging.CRITICAL: distutils_log.FATAL,
            logging.ERROR: distutils_log.ERROR,
            logging.WARNING: distutils_log.WARN,
            logging.INFO: distutils_log.INFO,
            logging.DEBUG: distutils_log.DEBUG,
        }
        self.setFormatter(logging.Formatter('%(message)s'))

    def _to_distutils_level(self, level):
        return self.level_table.get(level, level // 10)

    def emit(self, record):
        level = self._to_distutils_level(record.levelno)
        try:
            msg = self.format(record)
            self.log.log(level, msg)
        except Exception:
            # LogRecord.__str__ shouldn't fail... probably.
            self.log.warn('Failed to convert %s' % record)


distutils_log_handler = DistutilsLogHandler()


# Class names for subclasses of Command is in lower case simply due to
# setuptools using this verbatim as the command name when showing user
# help.

class npm(Command):
    """
    Simple compatibility hook for npm.
    """

    description = "npm compatibility helper"
    indent = 4

    # We are really only interested logs from these modules.
    handle_logger_ids = ('calmjs.cli', 'calmjs.dist',)

    user_options = [
        ('init', None,
         "generate package.json and write to current dir"),
        ('overwrite', None,
         "overwrite configuration files (such as package.json)"),
        ('merge', None,
         "merge configuration files if possible (such as package.json)"),
        # this is implicit because otherwise no difference from running
        # ``npm init`` directly from the shell.
        ('install', None,
         "runs npm install with generated package.json; implies --init"),
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
        cli.npm_init(pkg_name, overwrite=self.overwrite, merge=self.merge)

    def do_install(self):
        pkg_name = self.distribution.get_name()
        cli.npm_install(pkg_name, overwrite=self.overwrite, merge=self.merge)

    def finalize_options(self):
        opts = [i for i in (getattr(self, k) for k in self._opt_keys()) if i]
        if not opts:
            name = self.get_command_name()
            raise DistutilsOptionError(
                'must specify an action flag; see %s --help' % name)

    def run(self):
        for logger_id in self.handle_logger_ids:
            logger = logging.getLogger(logger_id)
            logger.addHandler(distutils_log_handler)
            logger.setLevel(logging.DEBUG)

        self.run_command('egg_info')
        if self.dry_run:
            # Everything else will do a lot of naughty things so...
            return

        if self.init:
            self.do_init()
        elif self.install:
            self.do_install()
