# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import difflib
import logging
import json
import re
import sys
from locale import getpreferredencoding
from os import fstat
from os import getcwd
from os.path import exists
from stat import S_ISCHR

from subprocess import check_output
from subprocess import call

from calmjs.dist import flatten_package_json
from calmjs.dist import DEFAULT_JSON

__all__ = [
    'Driver',
]

logger = logging.getLogger(__name__)
locale = getpreferredencoding()

version_expr = re.compile('((?:\d+)(?:\.\d+)*)')

NODE_PATH = 'NODE_PATH'
NODE = 'node'
DEP_KEYS = ('dependencies', 'devDependencies')


if sys.version_info < (3,):  # pragma: no cover
    str = unicode  # noqa: F821

lower = str.lower


def _get_bin_version(bin_path, version_flag='-v', _from=None, _to=None, kw={}):
    try:
        version_str = version_expr.search(
            check_output([bin_path, version_flag], **kw).decode('ascii')
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


class NodeDriver(object):
    """
    This is really a common base driver class that stores the common
    location of the node related values for the actual driver(s) to be
    implemented.
    """

    indent = 4

    def __init__(self, node_bin=NODE, node_path=None):
        """
        Optional Arguments:

        node_bin
            Path to node binary.  Defaults to ``node``.
        node_path
            Overrides NODE_PATH environment variable.
        """

        self.node_path = node_path
        self.node_bin = node_bin

    def _gen_call_kws(self):
        kw = {}
        env = {}
        if self.node_path:
            env[NODE_PATH] = self.node_path
        if env:
            kw['env'] = env
        return kw

    def get_node_version(self):
        kw = self._gen_call_kws()
        return _get_bin_version(self.node_bin, _from=1, kw=kw)


class Driver(NodeDriver):
    """
    Generic package manager interaction driver class.
    """

    def __init__(self, pkg_manager_bin, pkgdef_filename=DEFAULT_JSON,
                 prompt=prompt, interactive=None, *a, **kw):
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
        """

        super(Driver, self).__init__(*a, **kw)
        self.pkg_manager_bin = pkg_manager_bin
        self.pkgdef_filename = pkgdef_filename
        self.prompt = prompt

        self.interactive = interactive
        if self.interactive is None:
            self.interactive = check_interactive()

    def get_pkg_manager_version(self):
        return _get_bin_version(self.pkg_manager_bin)

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

        logger.info(
            "generating a flattened '%s' for '%s' into current working "
            "directory (%s)",
            self.pkgdef_filename, package_name, getcwd())

        if interactive is None:
            interactive = self.interactive
        # both autodetection AND manual specification must be true.
        interactive = interactive & check_interactive()

        # this will be modified in place
        original_json = {}
        # package_json is the one that will get written out, if needed.
        package_json = flatten_package_json(
            package_name, filename=self.pkgdef_filename)

        existed = exists(self.pkgdef_filename)

        # I really don't like all these if statements that follow,
        # however this is still relatively easy to reason over.  Should
        # consider this more of a shell and have the heavy lifting be
        # arranged in a more functional approach.

        if existed:
            try:
                with open(self.pkgdef_filename, 'r') as fd:
                    original_json = json.load(fd)
            except ValueError:
                logger.warning(
                    "Ignoring existing malformed '%s'.", self.pkgdef_filename)
            except (IOError, OSError):
                logger.error(
                    "Reading of existing '%s' failed; "
                    "please confirm that it is a file and/or permissions to "
                    "read and write is permitted before retrying.",
                    self.pkgdef_filename,
                )
                # Cowardly giving up.
                raise

            if merge:
                # Merge the generated on top of the original.
                updates = generate_merge_dict(
                    DEP_KEYS, original_json, package_json,
                )
                final = {}
                final.update(original_json)
                final.update(package_json)
                final.update(updates)
                package_json = final

            if package_json.get('name', NotImplemented) is NotImplemented:
                package_json['name'] = package_name

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
                            json.dumps(
                                original_json, indent=self.indent,
                                sort_keys=True,
                            ).splitlines(),
                            json.dumps(
                                package_json, indent=self.indent,
                                sort_keys=True,
                            ).splitlines(),
                        ))
                        if l[:1] in '?+-' or l[-1:] in '{}' or l[-2:] == '},')
                    # set new overwrite value from user input.
                    overwrite = prompt(
                        "Generated '%(pkgdef_filename)s' differs from one in "
                        "current working directory.\n\n"
                        "The following is a compacted list of changes "
                        "required:\n"
                        "%(diff)s\n\n"
                        "Overwrite '%(pkgdef_filename)s' in "
                        "current working directory?" % {
                            'pkgdef_filename': self.pkgdef_filename,
                            'diff': diff,
                        },
                        choices=(
                            ('Yes', True),
                            ('No', False),
                        ),
                        default_key=1,
                    )

            if not overwrite:
                logger.warning(
                    "'%s' exists in current working directory; "
                    "not overwriting", self.pkgdef_filename
                )
                return False

        if package_json:
            # Only write one if we actually got data.
            with open(self.pkgdef_filename, 'w') as fd:
                json.dump(package_json, fd, indent=self.indent, sort_keys=True)
            logger.info(
                "wrote '%s' to current working directory",
                self.pkgdef_filename
            )

        return True

    def pkg_manager_install(self, package_name=None, *a, **kw):
        """
        This will install all dependencies into the current working
        directory for the specific Python package from the selected
        JavaScript package manager; this requires that this package
        manager's package definition file to be properly generated
        first, otherwise the process will be aborted.  All other
        arguments to this method will be passed forward to the
        pkg_manager_init method.

        If no package_name was supplied then just continue with the
        process anyway, to still enable the shorthand calling.
        """

        # TODO not hardcode 'install'

        if package_name:
            result = self.pkg_manager_init(package_name, *a, **kw)
            if not result:
                logger.warn(
                    "not continuing with '%s install' as the generation of "
                    "'%s' failed", self.pkg_manager_bin, self.pkgdef_filename
                )
                return
        else:
            logger.warn(
                "no package name supplied, but continuing with '%s install'",
                self.pkg_manager_bin
            )

        kw = self._gen_call_kws()
        call([self.pkg_manager_bin, 'install'], **kw)


_inst = NodeDriver()
get_node_version = _inst.get_node_version
