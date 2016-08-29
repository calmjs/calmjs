# -*- coding: utf-8 -*-
import logging
import re
import sys
from argparse import Action
from argparse import ArgumentParser

from pkg_resources import working_set as default_working_set

from calmjs.utils import pretty_logging
from calmjs.utils import pdb_post_mortem

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

    argparser = None

    def __init__(self, prog=None, debug=0, log_level=0):
        self.prog = prog
        self.debug = debug
        self.log_level = log_level
        self.verbosity = 0
        self.init()

    def init(self):
        if self.argparser is None:
            self.argparser = ArgumentParser(
                prog=self.prog, description=self.__doc__, add_help=False)
            self.init_argparser(self.argparser)

    def init_argparser(self, argparser):
        argparser.add_argument(
            '-v', '--verbose', action='count', default=0,
            help="be more verbose")

        argparser.add_argument(
            '-q', '--quiet', action='count', default=0,
            help="be more quiet")

        argparser.add_argument(
            '-d', '--debug', action='count', default=0,
            help="enable debugging features")

    def prepare_keywords(self, kwargs):
        self.debug = kwargs.pop('debug')
        v = min(max(
            self.verbosity + kwargs.pop('verbose') - kwargs.pop('quiet'),
            -2), 2)
        self.log_level = levels.get(v)

    def __call__(self, args):
        parsed, extras = self.argparser.parse_known_args(args)
        kwargs = vars(parsed)
        self.prepare_keywords(kwargs)
        return extras


class BaseRuntime(BootstrapRuntime):
    """
    calmjs runtime collection
    """

    def __init__(
            self, logger='calmjs', action_key=DEST_RUNTIME,
            working_set=default_working_set, *a, **kw):
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

        self.logger = logger
        self.action_key = action_key
        self.working_set = working_set
        self.runtimes = {}
        self.entry_points = {}
        self.argparser = None
        self.subparsers = {}
        super(BaseRuntime, self).__init__(*a, **kw)

    def init(self):
        if self.argparser is None:
            self.argparser = ArgumentParser(
                prog=self.prog, description=self.__doc__)
            self.init_argparser(self.argparser)

    def run(self, **kwargs):
        """
        Subclasses should have their own running method.
        """


class Runtime(BaseRuntime):

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

        def to_module_attr(ep):
            return '%s:%s' % (ep.module_name, '.'.join(ep.attrs))

        def register(name, runtime, entry_point):
            subparser = commands.add_parser(
                name, help=inst.cli_driver.description)
            self.subparsers[name] = subparser
            self.runtimes[name] = runtime
            self.entry_points[name] = entry_point
            runtime.init_argparser(subparser)

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
                reg_ep = self.entry_points[entry_point.name]
                reg_rt = self.runtimes[entry_point.name]

                if reg_rt is inst:
                    # this is fine, multiple packages declared the same
                    # thing with the same name.
                    logger.debug(
                        "duplicated registration of command '%s' via entry "
                        "point '%s' ignored; registered '%s', confict '%s'",
                        entry_point.name, entry_point, reg_ep.dist,
                        entry_point.dist,
                    )
                    continue

                logger.error(
                    "a calmjs runtime command named '%s' already registered.",
                    entry_point.name
                )
                logger.info("conflicting entry points are:")
                logger.info(
                    "'%s' from '%s' (registered)", reg_ep, reg_ep.dist)
                logger.info(
                    "'%s' from '%s' (conflict)", entry_point, entry_point.dist)
                # Fall back name should work if the class/instances are
                # stable.
                name = to_module_attr(entry_point)

                if name in self.runtimes:
                    # Maybe this is the third time this module is
                    # registered.  Test for its identity.
                    if self.runtimes[name] is not inst:
                        # Okay someone is having a fun time here mucking
                        # with data structures internal to here, likely
                        # (read hopefully) due to testing or random
                        # monkey patching (or module level reload).
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
                        logger.debug(
                            "fallback command '%s' is already registered.",
                            name
                        )
                    continue

                logger.error(
                    "falling back to using full instance path '%s' as command "
                    "name, also registering alias for registered command", name
                )
                register(to_module_attr(reg_ep), reg_rt, reg_ep)
            else:
                name = entry_point.name

            register(name, inst, entry_point)

    def run(self, **kwargs):
        runtime = self.runtimes.get(kwargs.pop(self.action_key))
        if runtime:
            return runtime.run(**kwargs)
        # nothing is going to happen otherwise?

    def __call__(self, args):
        # MUST use the bootstrap runtime class to process all the common
        # flags as inconsistent handling of these between different
        # versions of Python make this extremely annoying.
        #
        # For a simple minimum demonstration, see:
        # https://gist.github.com/metatoaster/16bb6046d6363682b4c4497518436fc5

        # Also, remember that we need to strip off all the args that
        # the bootstrap knows, only process any leftovers.
        bootstrap = BootstrapRuntime()
        args = bootstrap(args)
        self.log_level = bootstrap.log_level
        self.debug = bootstrap.debug

        # NOT using parse_args directly because argparser is dumb when
        # it comes to bad keywords in a subparser - it doesn't invoke
        # its help text.  Nor does it keep track of what or where the
        # extra arguments actually came from.  So we are going to do
        # this manually so the users don't get confused.
        parsed, extras = self.argparser.parse_known_args(args)
        kwargs = vars(parsed)
        target = kwargs.get(self.action_key)

        if extras:
            # first step, figure out where exactly the problem is
            before = args[:args.index(target)] if target in args else args
            # Now, take everything before the target and see that it
            # got consumed
            bootstrap = BootstrapRuntime()
            check = bootstrap(before)

            # XXX msg generated has no gettext like the default one.
            if check:
                # So there exists some issues before the target, we can
                # fail by default.
                msg = 'unrecognized arguments: %s' % ' '.join(check)
                self.argparser.error(msg)
            if target:
                msg = 'unrecognized arguments: %s' % ' '.join(extras)
                self.subparsers[target].error(msg)

        with pretty_logging(
                logger=self.logger, level=self.log_level, stream=sys.stderr):
            try:
                return self.run(**kwargs)
            except KeyboardInterrupt:
                logger.critical('termination requested; aborted.')
            except Exception:
                if not self.debug:
                    logger.critical(
                        'terminating due to a critical error; please refer to '
                        'previous error log entries, alternatively retry with '
                        '--debug to get the traceback information to aid with '
                        'debugging.'
                    )
                else:
                    logger.critical(
                        'terminating due to exception', exc_info=1)
                    if self.debug > 1:
                        pdb_post_mortem(sys.exc_info()[2])
            return False


class DriverRuntime(BaseRuntime):
    """
    runtime for driver
    """

    def __init__(self, cli_driver, action_key=DEST_ACTION, *a, **kw):
        self.cli_driver = cli_driver
        super(DriverRuntime, self).__init__(action_key=action_key, *a, **kw)


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

        super(PackageManagerRuntime, self).init_argparser(argparser)

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
        return action(**kwargs)


def main(args=None):
    import warnings
    bootstrap = BootstrapRuntime()
    # None to distinguish args from unspecified or specified as [], but
    # ultimately the value must be a list.
    args = sys.argv[1:] if args is None else (args or [])
    extras = bootstrap(args)
    if not extras:
        args = args + ['-h']

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        with pretty_logging(
                logger='', level=bootstrap.log_level, stream=sys.stderr):
            # pass in the extra arguments that bootstrap cannot handle.
            runtime = Runtime()
        if runtime(args):
            sys.exit(0)
        else:
            sys.exit(1)
