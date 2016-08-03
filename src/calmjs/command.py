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
         "action: generate and write 'package.json' to current directory for "
         "this package"),
        # this required implicit step is done, otherwise there are no
        # difference to running ``npm init`` directly from the shell.
        ('install', None,
         "action: run npm install with generated 'package.json'; "
         "implies init; will abort if init fails to write the generated file"),
        # as far as I know typically setuptools setup.py are not
        # interactive, so we keep it that way unless user explicitly
        # want this.
        ('interactive', 'i',
         "enable interactive prompt; if an action requires an explicit "
         "response but none were specified through flags (i.e. overwrite), "
         "prompt for response; disabled by default"),
        ('merge', None,
         "merge generated 'package.json' with the one in current directory; "
         "if interactive mode is not enabled, implies overwrite, else the "
         "difference will be displayed"),
        ('overwrite', None,
         "automatically overwrite any file changes to current directory "
         "without prompting"),
    ]
    # TODO implement support for other install args like specifying the
    # location of stuff.

    # the actions that result in effects that we support
    actions = ('init', 'install')

    def _opt_keys(self):
        for opt in self.user_options:
            yield opt[0]

    def initialize_options(self):
        self.cli = cli.Driver(interactive=False)
        for key in self._opt_keys():
            setattr(self, key, False)

    def do_init(self):
        pkg_name = self.distribution.get_name()
        self.cli.pkg_manager_init(
            pkg_name,
            overwrite=self.overwrite, merge=self.merge,
            interactive=self.interactive,
        )

    def do_install(self):
        pkg_name = self.distribution.get_name()
        self.cli.pkg_manager_install(
            pkg_name,
            overwrite=self.overwrite, merge=self.merge,
            interactive=self.interactive,
        )

    def finalize_options(self):
        opts = [i for i in (getattr(self, k) for k in self.actions) if i]
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
