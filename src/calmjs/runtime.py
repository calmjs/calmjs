# -*- coding: utf-8 -*-
from argparse import ArgumentParser

# TODO, provide runtime/entrypoint into the cli

pkg_manager_options = (
    ('init', None,
     "action: generate and write '%(pkgdef_filename)s' to the "
     "current directory for this Python package"),
    # this required implicit step is done, otherwise there are no
    # difference to running ``npm init`` directly from the shell.
    ('install', None,
     "action: run '%(pkg_manager_bin)s install' with generated "
     "'%(pkgdef_filename)s'; implies init; will abort if init fails "
     "to write the generated file"),
    # as far as I know typically setuptools setup.py are not
    # interactive, so we keep it that way unless user explicitly
    # want this.
    ('interactive', 'i',
     "enable interactive prompt; if an action requires an explicit "
     "response but none were specified through flags "
     "(i.e. overwrite), prompt for response; disabled by default"),
    ('merge', 'm',
     "merge generated 'package.json' with the one in current "
     "directory; if interactive mode is not enabled, implies "
     "overwrite, else the difference will be displayed"),
    ('overwrite', 'w',
     "automatically overwrite any file changes to current directory "
     "without prompting"),
)


def make_cli_options(cli_driver):
    return [
        (full, s, desc % {
            'pkgdef_filename': cli_driver.pkgdef_filename,
            'pkg_manager_bin': cli_driver.pkg_manager_bin,
        }) for full, s, desc in pkg_manager_options
    ]


class DriverRuntime(object):
    """
    A calmjs driver runtime
    """

    def __init__(self, cli_driver, argparser=None):
        self.cli_driver = cli_driver

        if argparser is None:
            argparser = ArgumentParser()
        self.argparser = argparser
        self.init()

    def init(self):
        self.init_argparser()

    def init_argparser(self, argparser):
        """
        Initialize the argparser
        """


class PackageManagerRuntime(DriverRuntime):
    """
    A calmjs runtime

    e.g

    $ calmjs npm --init example.package
    $ calmjs npm --install example.package
    """

    def init_argparser(self):
        # provide this for the setuptools command class.
        self.pkg_manager_options = make_cli_options(self.cli_driver)
        argparser = self.argparser
        actions = argparser.add_argument_group('actions arguments')

        for full, short, desc in self.pkg_manager_options:
            args = [
                dash + key
                for dash, key in zip(('-', '--'), (short, full))
                if key
            ]
            if short:
                argparser.add_argument(*args, help=desc, action='store_true')
            else:
                actions.add_argument(*args, help=desc, action='store_true')

        argparser.add_argument(
            'package_name', help='Name of the python package to use')
