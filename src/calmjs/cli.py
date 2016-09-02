# -*- coding: utf-8 -*-
"""
This module intends to provide an interface between the underlying
command-line interface (cli) based tools, at the same time also provide
helpers and classes that also support and provide its own cli for calmjs
framework.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

import difflib
import logging
import json
import re
import sys
from locale import getpreferredencoding
from os import fstat
from os.path import exists
from stat import S_ISCHR

from subprocess import check_output
from subprocess import call

from calmjs.dist import convert_package_names
from calmjs.dist import find_packages_requirements_dists
from calmjs.dist import flatten_dist_egginfo_json
from calmjs.dist import pkg_names_to_dists
from calmjs.dist import DEFAULT_JSON
from calmjs.dist import DEP_KEYS

from calmjs.base import NODE
from calmjs.base import BaseDriver
from calmjs.base import _get_exec_binary

__all__ = [
    'NodeDriver',
    'PackageManagerDriver',
]

locale = getpreferredencoding()
logger = logging.getLogger(__name__)

version_expr = re.compile('((?:\d+)(?:\.\d+)*)')


if sys.version_info < (3,):  # pragma: no cover
    str = unicode  # noqa: F821

lower = str.lower


def _get_bin_version(bin_path, version_flag='-v', kw={}):
    try:
        prog = _get_exec_binary(bin_path, kw)
        version_str = version_expr.search(
            check_output([prog, version_flag], **kw).decode(locale)
        ).groups()[0]
        version = tuple(int(i) for i in version_str.split('.'))
    except OSError:
        logger.warning("failed to execute '%s'", bin_path)
        return None
    except:
        logger.exception(
            "encountered unexpected error while trying to find version of "
            "'%s':", bin_path
        )
        return None
    logger.info("found '%s' version '%s'", bin_path, version_str)
    return version


def generate_merge_dict(keys, *dicts):
    result = {}
    for key in keys:
        for d in dicts:
            if key not in d:
                continue
            result[key] = result.get(key, {})
            result[key].update(d[key])
    return result


def _check_interactive(*descriptors):
    for desc in descriptors:
        try:
            if not S_ISCHR(fstat(desc.fileno()).st_mode):
                return False
        except Exception:
            # Anything broken we are going to pretend this is not
            # interactive
            return False

    return True  # pragma: no cover


def check_interactive():
    return _check_interactive(sys.stdin, sys.stdout)


def null_validator(value):
    return value


def make_choice_validator(
        choices, default_key=None, normalizer=None):
    """
    Returns a callable that accepts the choices provided.

    Choices should be provided as a list of 2-tuples, where the first
    element is a string that should match user input (the key); the
    second being the value associated with the key.

    The callable by default will match, upon complete match the first
    value associated with the result will be returned.  Partial matches
    are supported.

    If a default is provided, that value will be returned if the user
    provided input is empty, i.e. the value that is mapped to the empty
    string.

    Finally, a normalizer function can be passed.  This normalizes all
    keys and validation value.
    """

    def normalize_all(_choices):
        # normalize all the keys for easier comparison
        if normalizer:
            _choices = [(normalizer(key), value) for key, value in choices]
        return _choices

    choices = normalize_all(choices)

    def choice_validator(value):
        if normalizer:
            value = normalizer(value)
        if not value and default_key:
            value = choices[default_key][0]
        results = []
        for choice, mapped in choices:
            if value == choice:
                return mapped
            if choice.startswith(value):
                results.append((choice, mapped))
        if len(results) == 1:
            return results[0][1]
        elif not results:
            raise ValueError('Invalid choice.')
        else:
            raise ValueError(
                'Choice ambiguous between (%s)' % ', '.join(
                    k for k, v in normalize_all(results))
            )

    return choice_validator


def prompt(question, validator=None,
           choices=None, default_key=NotImplemented,
           normalizer=str.lower,
           _stdin=None, _stdout=None):
    """
    Prompt user for question, maybe choices, and get answer.

    Arguments:

    question
        The question to prompt.  It will only be prompted once.
    validator
        Defaults to None.  Must be a callable that takes in a value.
        The callable should raise ValueError when the value leads to an
        error, otherwise return a converted value.
    choices
        If choices are provided instead, a validator will be constructed
        using make_choice_validator along with the next default_value
        argument.  Please refer to documentation for that function.
    default_value
        See above.
    normalizer
        Defaults to str.lower.  See above.
    """

    if _stdin is None:
        _stdin = sys.stdin

    if _stdout is None:
        _stdout = sys.stdout

    _stdout.write(question)
    _stdout.write(' ')

    choice_keys = []

    if validator is None:
        if choices:
            validator = make_choice_validator(
                choices, default_key, normalizer)
            choice_keys = [choice for choice, mapped in choices]
        else:
            validator = null_validator

    answer = NotImplemented
    while answer is NotImplemented:
        if choice_keys:
            _stdout.write('(')
            _stdout.write('/'.join(choice_keys))
            _stdout.write(') ')
            if default_key:
                _stdout.write('[')
                _stdout.write(choice_keys[default_key])
                _stdout.write('] ')
        _stdout.flush()
        try:
            answer = validator(
                _stdin.readline().strip().encode(locale).decode(locale))
        except ValueError as e:
            _stdout.write('%s\n' % e)
            _stdout.write(question.splitlines()[-1])
            _stdout.write(' ')
        except KeyboardInterrupt:
            _stdout.write('Aborted.\n')
            answer = None

    return answer


class NodeDriver(BaseDriver):
    """
    This is really a common base driver class that stores the common
    location of the node related values for the actual driver(s) to be
    implemented.
    """

    def __init__(self, node_bin=NODE, *a, **kw):
        """
        Optional Arguments:

        node_bin
            Path to node binary.  Defaults to ``node``.

        Other keyword arguments pass up to parent; please refer to its
        definitions.
        """

        super(NodeDriver, self).__init__(*a, **kw)
        self.binary = self.node_bin = node_bin

    def get_node_version(self):
        kw = self._gen_call_kws()
        return _get_bin_version(self.node_bin, kw=kw)

    def node(self, source, args=(), env={}):
        """
        Calls node with an inline source.

        Returns decoded output of stdout and stderr; decoding determine
        by locale.
        """

        return self._exec(self.node_bin, source, args=args, env=env)


class PackageManagerDriver(NodeDriver):
    """
    Generic package manager interaction driver class.

    This depends directly on the NodeDriver instead of the BaseDriver
    simply because quite often things might want to access the node
    binary.
    """

    def __init__(self, pkg_manager_bin, pkgdef_filename=DEFAULT_JSON,
                 prompt=prompt, interactive=None, install_cmd='install',
                 dep_keys=DEP_KEYS, pkg_name_field='name',
                 *a, **kw):
        """
        Optional Arguments:

        pkg_manager_bin
            Path to package manager binary.
        pkgdef_filename
            The file name of the package manager's definition file -
            defaults to ``package.json``.
        prompt
            The interactive prompt function.  See above.
        interactive
            Boolean value to determine interactive mode.  Unset by
            default, which triggers auto-detection and set if the
            running application has an interactive console.
        install_cmd
            The package manager's command line install command
            Defaults to ``install``.
        dep_keys
            The dependency keys, for which the dependency merging
            applies for.
        """

        super(PackageManagerDriver, self).__init__(*a, **kw)
        self.binary = pkg_manager_bin
        self.pkgdef_filename = pkgdef_filename
        self.prompt = prompt
        self.install_cmd = install_cmd
        self.dep_keys = dep_keys
        self.pkg_name_field = pkg_name_field

        self.interactive = interactive
        if self.interactive is None:
            self.interactive = check_interactive()

    @property
    def pkg_manager_bin(self):
        return self.binary

    @property
    def _aliases(self):
        # using explicit pkg_manager_bin because well, things can get
        # overwritten by subclasses
        names = [
            'pkg_manager_bin', 'get_pkg_manager_version', 'pkg_manager_init',
            'pkg_manager_install', 'pkg_manager_view', 'install_cmd',
        ]

        g = {}

        for name in names:
            g[name] = super(PackageManagerDriver, self).__getattribute__(name)

        return {
            'get_%(pkg_manager_bin)s_version' % g:
                g['get_pkg_manager_version'],
            '%(pkg_manager_bin)s_view' % g:
                g['pkg_manager_view'],
            '%(pkg_manager_bin)s_init' % g:
                g['pkg_manager_init'],
            '%(pkg_manager_bin)s_%(install_cmd)s' % g:
                g['pkg_manager_install'],
        }

    def __getattr__(self, name):
        lookup = super(PackageManagerDriver, self).__getattribute__('_aliases')
        if name not in lookup:
            # this should trigger default exception with right error msg
            return self.__getattribute__(name)
        return lookup[name]

    @classmethod
    def create_for_module_vars(cls, scope_vars):
        """
        This was originally designed to be invoked at the module level
        for packages that implement specific support, but this can be
        used to create an instance that has the Node.js backed
        executable be found via current directory's node_modules or
        NODE_PATH.
        """

        inst = cls()
        if not inst._set_env_path_with_node_modules():
            import warnings
            msg = (
                "Unable to locate the '%(binary)s' binary; default module "
                "level functions will not work. Please either provide "
                "%(PATH)s and/or update %(PATH)s environment variable "
                "with one that provides '%(binary)s'; or specify a "
                "working %(NODE_PATH)s environment variable with "
                "%(binary)s installed; or have install '%(binary)s' into "
                "the current working directory (%(cwd)s) either through "
                "npm or calmjs framework for this package. Restart or "
                "reload this module once that is done. Alternatively, "
                "create a manual Driver instance for '%(binary)s' with "
                "explicitly defined arguments." % {
                    'binary': inst.binary,
                    'PATH': 'PATH',
                    'NODE_PATH': inst.node_path,
                    'cwd': inst.join_cwd(),
                }
            )
            warnings.warn(msg, RuntimeWarning)
            # Yes there may be duplicates, but warnings are governed
            # differently.
            logger.warning(msg)
        scope_vars.update(inst._aliases)
        return inst

    def get_pkg_manager_version(self):
        kw = self._gen_call_kws()
        return _get_bin_version(self.pkg_manager_bin, kw=kw)

    def pkg_manager_view(
            self, package_names, stream=None, explicit=False, **kw):
        """
        Returns the manifest JSON for the Python package name.  Default
        npm implementation calls for package.json.

        If this class is initiated using standard procedures, this will
        mimic the functionality of ``npm view`` but mostly for showing
        the dependencies.  This is done as a default action.

        Arguments:

        package_names
            The names of the python packages with their requirements to
            source the package.json from.
        stream
            If specified, the generated package.json will be written to
            there.
        explicit
            If True, the package names specified are the explicit list
            to search for - no dependency resolution will then be done.

        Returns the manifest json as a dict.
        """

        # For looking up the pkg_name to dist converter for explicit
        to_dists = {
            False: find_packages_requirements_dists,
            True: pkg_names_to_dists,
        }

        # assuming string, and assume whitespaces are invalid.
        pkg_names, malformed = convert_package_names(package_names)
        if malformed:
            msg = 'malformed package name(s) specified: %s' % ', '.join(
                malformed)
            raise ValueError(msg)

        if len(pkg_names) == 1:
            logger.info(
                "generating a flattened '%s' for '%s'",
                self.pkgdef_filename, pkg_names[0],
            )
        else:
            logger.info(
                "generating a flattened '%s' for packages {%s}",
                self.pkgdef_filename, ', '.join(pkg_names),
            )

        # remember the filename is in the context of the distribution,
        # not the filesystem.
        dists = to_dists[explicit](pkg_names)
        pkgdef_json = flatten_dist_egginfo_json(
            dists, filename=self.pkgdef_filename,
            dep_keys=self.dep_keys,
        )

        if pkgdef_json.get(
                self.pkg_name_field, NotImplemented) is NotImplemented:
            # use the last item.
            pkgdef_json[self.pkg_name_field] = pkg_names[-1]

        if stream:
            self.dump(pkgdef_json, stream)
            stream.write('\n')

        return pkgdef_json

    def pkg_manager_init(
            self, package_names,
            interactive=None,
            overwrite=False, merge=False, **kw):
        """
        Note: default implementation calls for npm and package.json,
        please note that it may not be the case for this instance of
        Driver.

        If this class is initiated using standard procedures, this will
        emulate the functionality of ``npm init`` for the generation of
        a working ``package.json``, but without asking users for input
        but instead uses information available through the distribution
        packages within ``setuptools``.

        Arguments:

        package_names
            The names of the python packages with their requirements to
            source the package.json from.

        interactive
            Boolean flag; if set, prompts user on what to do when choice
            needs to be made.  Defaults to None, which falls back to the
            default setting for this command line instance.

        overwrite
            Boolean flag; if set, overwrite package.json with the newly
            generated ``package.json``; ignores interactive setting

        merge
            Boolean flag; if set, implies overwrite, but does not ignore
            interactive setting.  However this will keep details defined
            in existing ``package.json`` and only merge dependencies /
            devDependencies defined by the specified Python package.

        Returns True if successful; can be achieved by writing a new
        file or that the existing one matches with the expected version.
        Returns False otherwise.
        """

        if interactive is None:
            interactive = self.interactive
        # both autodetection AND manual specification must be true.
        interactive = interactive & check_interactive()

        # this will be modified in place
        original_json = {}

        pkgdef_json = self.pkg_manager_view(package_names, **kw)

        # Now we figure out the actual file we want to work with.
        pkgdef_path = self.join_cwd(self.pkgdef_filename)
        existed = exists(pkgdef_path)

        if existed:
            try:
                with open(pkgdef_path, 'r') as fd:
                    original_json = json.load(fd)
            except ValueError:
                logger.warning(
                    "ignoring existing malformed '%s'", pkgdef_path)
            except (IOError, OSError):
                logger.error(
                    "reading of existing '%s' failed; "
                    "please confirm that it is a file and/or permissions to "
                    "read and write is permitted before retrying.",
                    pkgdef_path
                )
                # Cowardly giving up.
                raise

            if merge:
                # Merge the generated on top of the original.
                updates = generate_merge_dict(
                    self.dep_keys, original_json, pkgdef_json,
                )
                final = {}
                final.update(original_json)
                final.update(pkgdef_json)
                final.update(updates)
                pkgdef_json = final

            if original_json == pkgdef_json:
                # Well, if original existing one is identical with the
                # generated version, we got it, and we are done here.
                # This also prevents the interactive prompt from firing.
                return True

            if not interactive:
                # here the implied settings due to non-interactive mode
                # are finally set
                if merge:
                    overwrite = True
            elif interactive:
                if not overwrite:
                    # generate compacted ndiff output.
                    diff = '\n'.join(l for l in (
                        line.rstrip() for line in difflib.ndiff(
                            self.dumps(original_json).splitlines(),
                            self.dumps(pkgdef_json).splitlines(),
                        ))
                        if l[:1] in '?+-' or l[-1:] in '{}' or l[-2:] == '},')
                    # set new overwrite value from user input.
                    overwrite = prompt(
                        "Generated '%(pkgdef_filename)s' differs with "
                        "'%(pkgdef_path)s'.\n\n"
                        "The following is a compacted list of changes "
                        "required:\n"
                        "%(diff)s\n\n"
                        "Overwrite '%(pkgdef_path)s'?" % {
                            'pkgdef_filename': self.pkgdef_filename,
                            'pkgdef_path': pkgdef_path,
                            'diff': diff,
                        },
                        choices=(
                            ('Yes', True),
                            ('No', False),
                        ),
                        default_key=1,
                    )

            if not overwrite:
                logger.warning("not overwriting existing '%s'", pkgdef_path)
                return False

        if pkgdef_json:
            # Only write one if we actually got data.
            with open(pkgdef_path, 'w') as fd:
                self.dump(pkgdef_json, fd)
            logger.info("wrote '%s'", pkgdef_path)

        return True

    def pkg_manager_install(self, package_names=None, args=(), env={}, **kw):
        """
        This will install all dependencies into the current working
        directory for the specific Python package from the selected
        JavaScript package manager; this requires that this package
        manager's package definition file to be properly generated
        first, otherwise the process will be aborted.

        If the argument 'args' is supplied as a tuple, those will be
        passed through to the package manager install command as its
        arguments.  This will be very specific to the underlying
        program; use with care as misuse can result in an environment
        that is not expected by the other parts of the framework.

        If the argument 'env' is supplied, they will be additional
        environment variables that are not already defined by the
        framework, which are 'NODE_PATH' and 'PATH'.  Values set for
        those will have highest precedence, then the ones passed in
        through env, then finally whatever was already defined before
        the execution of this program.

        All other arguments to this method will be passed forward to the
        pkg_manager_init method, if the package_name is supplied for the
        Python package.

        If no package_name was supplied then just continue with the
        process anyway, to still enable the shorthand calling.

        If the package manager could not be invoked, it will simply not
        be.

        Arguments:

        package_names
            The names of the Python package to generate the manifest
            for.
        args
            The arguments to pass into the command line install.
        """

        if package_names:
            result = self.pkg_manager_init(package_names, **kw)
            if not result:
                logger.warning(
                    "not continuing with '%s %s' as the generation of "
                    "'%s' failed", self.pkg_manager_bin, self.install_cmd,
                    self.pkgdef_filename
                )
                return
        else:
            logger.warning(
                "no package name supplied, but continuing with '%s %s'",
                self.pkg_manager_bin, self.install_cmd,
            )

        call_kw = self._gen_call_kws(**env)
        logger.debug(
            "invoking '%s %s'", self.pkg_manager_bin, self.install_cmd)
        if self.env_path:
            logger.debug(
                "invoked with env_path '%s'", self.env_path)
        if self.working_dir:
            logger.debug(
                "invoked from working directory '%s'", self.working_dir)
        try:
            cmd = [self._get_exec_binary(call_kw), self.install_cmd]
            cmd.extend(args)
            call(cmd, **call_kw)
        except (IOError, OSError):
            logger.error(
                "invocation of the '%s' binary failed; please ensure it and "
                "its dependencies are installed and available.", self.binary
            )
            # Still raise the exception as this is a lower level API.
            raise

    def run(self, args=(), env={}):
        """
        Calls the package manager with the arguments.

        Returns decoded output of stdout and stderr; decoding determine
        by locale.
        """

        # the following will call self._get_exec_binary
        return self._exec(self.binary, args=args, env=env)


_inst = NodeDriver()
get_node_version = _inst.get_node_version
node = _inst.node
