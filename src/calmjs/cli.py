# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import difflib
import logging
import json
import os
import re
import sys
import warnings
from locale import getpreferredencoding
from os import fstat
from os import getcwd
from os.path import isdir
from os.path import exists
from os.path import join
from os.path import pathsep
from stat import S_ISCHR

from subprocess import Popen
from subprocess import PIPE
from subprocess import check_output
from subprocess import call

from calmjs.dist import flatten_package_json
from calmjs.dist import DEFAULT_JSON
from calmjs.dist import DEP_KEYS
from calmjs.utils import which

__all__ = [
    'BaseDriver',
    'NodeDriver',
    'PackageManagerDriver',
]

logger = logging.getLogger(__name__)
locale = getpreferredencoding()

version_expr = re.compile('((?:\d+)(?:\.\d+)*)')

NODE_PATH = 'NODE_PATH'
NODE = 'node'


if sys.version_info < (3,):  # pragma: no cover
    str = unicode  # noqa: F821

lower = str.lower


def _get_bin_version(bin_path, version_flag='-v', kw={}):
    try:
        version_str = version_expr.search(
            check_output([bin_path, version_flag], **kw).decode(locale)
        ).groups()[0]
        version = tuple(int(i) for i in version_str.split('.'))
    except OSError:
        logger.warning('Failed to execute %s', bin_path)
        return None
    except:
        logger.exception(
            'Encountered unexpected error while trying to find version of %s:',
            bin_path
        )
        return None
    logger.info('Found %s version %s', bin_path, version_str)
    return version


def _check_isdir_assign_key(d, key, value, error_msg=None):
    if isdir(value):
        d[key] = value
    else:
        extra_info = '' if not error_msg else '; ' + error_msg
        logger.error(
            "not manually setting '%s' to '%s' as it not a directory%s",
            key, value, extra_info
        )


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


class BaseDriver(object):
    """
    The nodejs interfacing base driver class.

    Classes under the calmjs framework that make use of nodejs or nodejs
    binaries should make this as the base class to make accessing the
    nodejs environment in a manner consistent with the framework, where
    various defined attributes and helper methods that makes use of
    those will make interfacing with the nodejs environment be under a
    consistently managed scheme.

    Helper methods such as _exec will ensure the binary is executed
    with the right arguments (via _gen_call_kws).  The dump/dumps method
    invokes the underlying functions of the same name from the json
    module with the attributes defined to ensure human readability by
    default.  Finally, join_cwd joins a target path with the working
    directory defined for instances of this, so that target path can be
    accessed in a more explicit way.
    """

    def __init__(self, node_path=None, env_path=None, working_dir=None,
                 indent=4, separators=(',', ': ')):
        """
        Optional Arguments (defaults to None when not stated):

        node_path
            Overrides NODE_PATH environment variable for calling out.
        env_path
            Extra directory that will be assigned to the environment's
            PATH variable, so that that will be used first to look up a
            binary for exec calls.
        working_dir
            The working directory where the driver will operate at.
        indent
            JSON indentation level.  Defaults to 4.
        separators
            Set as a workaround to remove trailing spaces.  Should be
            left as is (',', ': ').
        """

        self.node_path = node_path
        self.env_path = env_path
        self.working_dir = working_dir
        self.indent = indent
        self.separators = separators
        self.binary = None

    def which(self):
        """
        Figure out which binary this will execute.
        """

        if self.binary is None:
            return None

        if self.env_path:
            return which(self.binary, path=self.env_path)
        else:
            return which(self.binary)

    def _set_env_path_with_node_modules(self, warn=False):
        """
        Attempt to locate and set the paths to the binary with the
        working directory defined for this instance.
        """

        if self.which() is not None:
            return

        node_path = os.environ.get(NODE_PATH, self.join_cwd('node_modules'))
        env_path = join(node_path, '.bin')
        if which(self.binary, path=env_path):
            # Only setting the path specific for the binary; side effect
            # will be whoever else borrowing the _exec in here might not
            # get the binary they want.  That's why it's private.
            self.env_path = env_path
        elif warn:
            warnings.warn(
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
                    'binary': self.binary,
                    'PATH': 'PATH',
                    'NODE_PATH': NODE_PATH,
                    'cwd': self.join_cwd(),
                },
                RuntimeWarning,
            )

    def _gen_call_kws(self, **env):
        kw = {}
        if self.node_path is not None:
            _check_isdir_assign_key(env, NODE_PATH, self.node_path)
        if self.env_path is not None:
            # Initial assignment with check
            _check_isdir_assign_key(env, 'PATH', self.env_path)
            # then append the rest of it
            env['PATH'] = pathsep.join([
                env.get('PATH', ''), os.environ.get('PATH', '')])
        if self.working_dir:
            _check_isdir_assign_key(
                kw, 'cwd', self.working_dir,
                error_msg="current working directory left as default")
        if env:
            kw['env'] = env
        return kw

    def _exec(self, binary, stdin='', args=(), env={}):
        """
        Executes the binary using stdin and args with environment
        variables.

        Returns a tuple of stdout, stderr.  Format determined by the
        input text (either str or bytes), and the encoding of str will
        be determined by the locale this module was imported in.
        """

        call_kw = self._gen_call_kws(**env)
        call_args = [binary]
        call_args.extend(args)
        as_bytes = isinstance(stdin, bytes)
        source = stdin if as_bytes else stdin.encode(locale)
        p = Popen(call_args, stdin=PIPE, stdout=PIPE, stderr=PIPE, **call_kw)
        stdout, stderr = p.communicate(source)
        if as_bytes:
            return stdout, stderr
        return (stdout.decode(locale), stderr.decode(locale))

    @property
    def cwd(self):
        return self.working_dir or getcwd()

    def dump(self, blob, stream):
        """
        Call json.dump with the attributes of this instance as
        arguments.
        """

        json.dump(
            blob, stream, indent=self.indent, sort_keys=True,
            separators=self.separators,
        )

    def dumps(self, blob):
        """
        Call json.dumps with the attributes of this instance as
        arguments.
        """

        return json.dumps(
            blob, indent=self.indent, sort_keys=True,
            separators=self.separators,
        )

    def join_cwd(self, path=None):
        """
        Join the path with the current working directory.  If it is
        specified for this instance of the object it will be used,
        otherwise rely on the global value.
        """

        if self.working_dir:
            logger.debug(
                "instance 'working_dir' set to '%s'", self.working_dir)
            cwd = self.working_dir
        else:
            cwd = getcwd()
            logger.debug(
                "instance 'working_dir' unset; default to process '%s'", cwd)

        if path:
            return join(cwd, path)
        return cwd


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
        self.binary = self.pkg_manager_bin = pkg_manager_bin
        self.pkgdef_filename = pkgdef_filename
        self.prompt = prompt
        self.install_cmd = install_cmd
        self.dep_keys = dep_keys
        self.pkg_name_field = pkg_name_field

        self.interactive = interactive
        if self.interactive is None:
            self.interactive = check_interactive()

    def __getattr__(self, name):
        lookup = {
            'get_' + self.pkg_manager_bin + '_version':
                self.get_pkg_manager_version,
            self.pkg_manager_bin + '_init': self.pkg_manager_init,
            self.pkg_manager_bin + '_' + self.install_cmd:
                self.pkg_manager_install,
        }
        if name not in lookup:
            # this should trigger default exception with right error msg
            return self.__getattribute__(name)
        return lookup[name]

    @classmethod
    def create(cls):
        """
        This was originally designed to be invoked at the module level
        for packages that implement specific support, but this can be
        used to create an instance that has the nodejs backed executable
        be found via current directory's node_modules or NODE_PATH.
        """

        inst = cls()
        inst._set_env_path_with_node_modules()
        return inst

    def get_pkg_manager_version(self):
        kw = self._gen_call_kws()
        return _get_bin_version(self.pkg_manager_bin, kw=kw)

    def pkg_manager_init(
            self, package_name=None,
            interactive=None,
            overwrite=False, merge=False):
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

        package_name
            The python package to source the package.json from.

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

        cwd = self.cwd

        logger.info(
            "generating a flattened '%s' for '%s' into '%s'",
            self.pkgdef_filename, package_name, cwd
        )

        if interactive is None:
            interactive = self.interactive
        # both autodetection AND manual specification must be true.
        interactive = interactive & check_interactive()

        # this will be modified in place
        original_json = {}
        # package_json is the one that will get written out, if needed.
        # remember the filename is in the context of the distribution,
        # not the filesystem.
        package_json = flatten_package_json(
            package_name, filename=self.pkgdef_filename,
            dep_keys=self.dep_keys,
        )

        if package_json.get(
                self.pkg_name_field, NotImplemented) is NotImplemented:
            package_json[self.pkg_name_field] = package_name

        # Now we figure out the actual fiel we want to work with.

        pkgdef_path = self.join_cwd(self.pkgdef_filename)
        existed = exists(pkgdef_path)

        # I really don't like all these if statements that follow,
        # however this is still relatively easy to reason over.  Should
        # consider this more of a shell and have the heavy lifting be
        # arranged in a more functional approach.

        if existed:
            try:
                with open(pkgdef_path, 'r') as fd:
                    original_json = json.load(fd)
            except ValueError:
                logger.warning(
                    "Ignoring existing malformed '%s'.", pkgdef_path)
            except (IOError, OSError):
                logger.error(
                    "Reading of existing '%s' failed; "
                    "please confirm that it is a file and/or permissions to "
                    "read and write is permitted before retrying.",
                    pkgdef_path
                )
                # Cowardly giving up.
                raise

            if merge:
                # Merge the generated on top of the original.
                updates = generate_merge_dict(
                    self.dep_keys, original_json, package_json,
                )
                final = {}
                final.update(original_json)
                final.update(package_json)
                final.update(updates)
                package_json = final

            if original_json == package_json:
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
                            self.dumps(package_json).splitlines(),
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
                logger.warning("Not overwriting existing '%s'", pkgdef_path)
                return False

        if package_json:
            # Only write one if we actually got data.
            with open(pkgdef_path, 'w') as fd:
                self.dump(package_json, fd)
            logger.info("wrote '%s'", pkgdef_path)

        return True

    def pkg_manager_install(self, package_name=None, args=(), env={},
                            *a, **kw):
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

        Arguments:

        package_name
            Then name of the Python package to generate the manifest
            for.
        args
            The arguments to pass into the command line install.
        """

        if package_name:
            result = self.pkg_manager_init(package_name, *a, **kw)
            if not result:
                logger.warn(
                    "not continuing with '%s %s' as the generation of "
                    "'%s' failed", self.pkg_manager_bin, self.install_cmd,
                    self.pkgdef_filename
                )
                return
        else:
            logger.warn(
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
        cmd = [self.pkg_manager_bin, self.install_cmd]
        cmd.extend(args)
        call(cmd, **call_kw)

    def run(self, args=(), env={}):
        """
        Calls the package manager with the arguments.

        Returns decoded output of stdout and stderr; decoding determine
        by locale.
        """

        return self._exec(self.pkg_manager_bin, args=args, env=env)


_inst = NodeDriver()
get_node_version = _inst.get_node_version
node = _inst.node
