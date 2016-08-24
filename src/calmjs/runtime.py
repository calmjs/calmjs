# -*- coding: utf-8 -*-
import logging
import re
import sys
from argparse import Action
from argparse import ArgumentParser

from pkg_resources import working_set as default_working_set

from calmjs.utils import pretty_logging

CALMJS_RUNTIME = 'calmjs.runtime'
logger = logging.getLogger(__name__)
DEST_ACTION = 'action'
DEST_RUNTIME = 'runtime'

levels = {
    -2: logging.CRITICAL,
    -1: logging.ERROR,
    0: logging.WARNING,
    1: logging.INFO,
    2: logging.DEBUG,
}

valid_command_name = re.compile('^[0-9a-zA-Z]*$')


class BootstrapRuntime(object):
    """
    calmjs bootstrap runtime.
    """

    def __init__(self):
        self.verbosity = 0
        self.argparser = ArgumentParser(add_help=False)
        self.init_argparser(self.argparser)

    def init_argparser(self, argparser):
        argparser.add_argument(
            '-v', '--verbose', action='count', default=0,
            help="be more verbose")

        argparser.add_argument(
            '-q', '--quiet', action='count', default=0,
            help="be more quiet")

    def prepare_keywords(self, kwargs):
        v = min(max(
            self.verbosity + kwargs.pop('verbose') - kwargs.pop('quiet'),
            -2), 2)
        self.log_level = levels.get(v)

    def __call__(self, args):
        kwargs = vars(self.argparser.parse_known_args(args)[0])
        self.prepare_keywords(kwargs)


class Runtime(BootstrapRuntime):
    """
    calmjs runtime collection
    """

    def __init__(
            self, action_key=DEST_RUNTIME, working_set=default_working_set):
        """
        Arguments:

        action_key
            The destination key where the command will be stored.  Under
            this key the target driver runtime will be stored, and it
            will be popped off first before passing rest of kwargs to
            it.
        working_set
            The working_set to use for this instance.

            Default: pkg_resources.working_set
        """

        self.verbosity = 0
        self.log_level = logging.WARNING
        self.action_key = action_key
        self.working_set = working_set
        self.runtimes = {}
        self.entry_points = {}
        self.argparser = None
        self.init()

    def init(self):
        if self.argparser is None:
            self.argparser = ArgumentParser(description=self.__doc__)
            self.init_argparser(self.argparser)

    def init_argparser(self, argparser):
        """
        This should not be called with an external argparser as it will
        corrupt tracking data if forced.
        """

        if argparser is not self.argparser:
            raise RuntimeError(
                'instances of Runtime will not accept external instances of '
                'ArgumentParsers'
            )

        super(Runtime, self).init_argparser(argparser)

        commands = argparser.add_subparsers(
            dest=self.action_key, metavar='<command>')

        for entry_point in self.working_set.iter_entry_points(CALMJS_RUNTIME):
            try:
                # load the runtime instance
                inst = entry_point.load()
            except ImportError:
                logger.error(
                    "bad '%s' entry point '%s' from '%s': ImportError",
                    CALMJS_RUNTIME, entry_point, entry_point.dist,
                )
                continue

            if not isinstance(inst, DriverRuntime):
                logger.error(
                    "bad '%s' entry point '%s' from '%s': "
                    "target not a calmjs.runtime.DriverRuntime instance; "
                    "not registering ignored entry point",
                    CALMJS_RUNTIME, entry_point, entry_point.dist,
                )
                continue

            if not valid_command_name.match(entry_point.name):
                logger.error(
                    "bad '%s' entry point '%s' from '%s': "
                    "entry point name must be a latin alphanumeric string; "
                    "not registering ignored entry point",
                    CALMJS_RUNTIME, entry_point, entry_point.dist,
                )
                continue

            if entry_point.name in self.runtimes:
                registered = self.entry_points[entry_point.name]

                if self.runtimes[entry_point.name] is inst:
                    # this is fine, multiple packages declared the same
                    # thing with the same name.
                    logger.debug(
                        "duplicated registration of command '%s' via entry "
                        "point '%s' ignored; registered '%s', confict '%s'",
                        entry_point.name, entry_point, registered.dist,
                        entry_point.dist,
                    )
                    continue

                logger.error(
                    "a calmjs runtime command named '%s' already registered.",
                    entry_point.name
                )
                logger.info("conflicting entry points are:")
                logger.info(
                    "'%s' from '%s' (registered)", registered, registered.dist)
                logger.info(
                    "'%s' from '%s' (conflict)", entry_point, entry_point.dist)
                # Fall back name should work if the class/instances are
                # stable.
                name = '%s:%s' % (
                    entry_point.module_name, '.'.join(entry_point.attrs))

                if name in self.runtimes:
                    # Maybe this is the third time this module is
                    # registered.  Test for its identity.
                    if self.runtimes[name] is not inst:
                        # Okay someone is having a fun time here mucking
                        # with data structures internal to here, likely
                        # (read hopefully) due to testing or random
                        # monkey patching (or module level reload).
                        registered = self.entry_points[name]
                        logger.critical(
                            "'%s' is already registered but points to a "
                            "completely different instance; please try again "
                            "with verbose logging and note which packages are "
                            "reported as conflicted; alternatively this is a "
                            "forced situation where this Runtime instance has "
                            "been used or initialized improperly.",
                            name
                        )
                    else:
                        logger.debug('fallback entry point is already added.')
                    continue

                logger.error(
                    "falling back to using full instance path '%s' as command "
                    "name", name
                )
            else:
                name = entry_point.name

            subparser = commands.add_parser(
                name, help=inst.cli_driver.description)
            self.runtimes[name] = inst
            self.entry_points[name] = entry_point
            inst.init_argparser(subparser)

    def run(self, **kwargs):
        runtime = self.runtimes.get(kwargs.pop(self.action_key))
        if runtime:
            runtime.run(**kwargs)
        # nothing is going to happen otherwise?

    def __call__(self, args):
        kwargs = vars(self.argparser.parse_args(args))
        self.prepare_keywords(kwargs)
        with pretty_logging(
                logger='calmjs', level=self.log_level, stream=sys.stderr):
            self.run(**kwargs)


class DriverRuntime(Runtime):
    """
    runtime for driver
    """

    def __init__(self, cli_driver, action_key=DEST_ACTION, *a, **kw):
        self.cli_driver = cli_driver
        super(DriverRuntime, self).__init__(action_key=action_key, *a, **kw)

    def init_argparser(self, argparser=None):
        """
        DriverRuntime should have their own init_argparer method.
        """

    def run(self, **kwargs):
        """
        DriverRuntime should have their own running method.
        """

    def prepare_keywords(self, kwargs):
        """
        DriverRuntime subclasses should have their own handling.
        """


class PackageManagerAction(Action):
    """
    Package manager specific action
    """

    def __init__(self, option_strings, dest, *a, **kw):
        super(PackageManagerAction, self).__init__(
            option_strings=option_strings, dest=dest, nargs=0, *a, **kw)

    def __call__(self, parser, namespace, values, option_string=None):
        priority, f = getattr(namespace, self.dest) or (0, None)
        new_priority, f = self.const
        if new_priority > priority:
            setattr(namespace, self.dest, self.const)
        if new_priority == 1:
            # Yes this is _really_ magical, however this is the way to
            # set attributes the cli later needs through the argparser.
            setattr(namespace, 'stream', sys.stdout)


class PackageManagerRuntime(DriverRuntime):
    """
    A calmjs runtime

    e.g

    $ calmjs npm --init example.package
    $ calmjs npm --install example.package
    """

    _pkg_manager_options = (
        ('view', None,
         "generate '%(pkgdef_filename)s' for the Python package and "
         "write to stdout for viewing [default]"),
        ('init', None,
         "generate and write '%(pkgdef_filename)s' to the "
         "current directory for this Python package"),
        # This required implicit step is done, otherwise there are no
        # difference to running ``npm init`` directly from the shell.
        ('install', None,
         "run '%(pkg_manager_bin)s install' with generated "
         "'%(pkgdef_filename)s'; implies init; will abort if init fails "
         "to write the generated file"),
        # As far as I know typically setuptools setup.py are not
        # interactive, so we keep it that way unless user explicitly
        # want this.  Consequence is that the generic tool will do the
        # same.
        ('interactive', 'i',
         "enable interactive prompt; if an action requires an explicit "
         "response but none were specified through flags "
         "(i.e. overwrite), prompt for response; disabled by default"),
        ('merge', 'm',
         "merge generated '%(pkgdef_filename)s' with the one in current "
         "directory; if interactive mode is not enabled, implies "
         "overwrite, else the difference will be displayed"),
        ('overwrite', 'w',
         "automatically overwrite any file changes to current directory "
         "without prompting"),
    )

    def make_cli_options(self):
        return [
            (full, s, desc % {
                'pkgdef_filename': self.cli_driver.pkgdef_filename,
                'pkg_manager_bin': self.cli_driver.pkg_manager_bin,
            }) for full, s, desc in self._pkg_manager_options
        ]

    def init(self):
        self.default_action = None
        self.pkg_manager_options = self.make_cli_options()
        # this will also initialize a local argparser that allow this
        # to function as a standalone callable, if required.
        super(PackageManagerRuntime, self).init()

    def init_argparser(self, argparser):
        """
        Other runtimes (or users of ArgumentParser) can pass their
        subparser into here to collect the arguments here for a
        subcommand.
        """

        # Ideally, we could use more subparsers for each action (i.e.
        # init and install).  However, this is complicated by the fact
        # that setuptools has its own calling conventions through the
        # setup.py file, and to present a consistent cli to end-users
        # from both calmjs entry point and setuptools using effectively
        # the same codebase will require a bit of creative handling.

        # provide this for the setuptools command class.
        actions = argparser.add_argument_group('action arguments')
        count = 0

        for full, short, desc in self.pkg_manager_options:
            args = [
                dash + key
                for dash, key in zip(('-', '--'), (short, full))
                if key
            ]
            if not short:
                f = getattr(self.cli_driver, '%s_%s' % (
                    self.cli_driver.binary, full), None)
                if callable(f):
                    count += 1
                    actions.add_argument(
                        *args, help=desc, action=PackageManagerAction,
                        dest=self.action_key, const=(count, f)
                    )
                    if self.default_action is None:
                        self.default_action = f
                    continue  # pragma: no cover
            argparser.add_argument(*args, help=desc, action='store_true')

        argparser.add_argument(
            'package_names', help='names of the python package to use',
            metavar='package_names', nargs='+',
        )

    def run(self, **kwargs):
        # Run the underlying package manager.  As the arguments in this
        # subparser is constructed in a way that maps directly with the
        # underlying actions, it can be invoked directly.
        raw = kwargs.pop(self.action_key)
        if raw:
            count, action = raw
        else:
            action = self.default_action
            kwargs['stream'] = sys.stdout
        action(**kwargs)


def main(args=None):
    bootstrap = BootstrapRuntime()
    bootstrap(args or sys.argv[1:])
    with pretty_logging(
            logger=logger, level=bootstrap.log_level, stream=sys.stderr):
        runtime = Runtime()
    runtime(args or sys.argv[1:])
