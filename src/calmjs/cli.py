# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
import json
import re
import sys
from os.path import exists

from subprocess import check_output
from subprocess import call

from calmjs.npm import PACKAGE_JSON
from calmjs.dist import flatten_package_json

__all__ = [
    'Driver', 'get_node_version', 'get_npm_version', 'npm_init', 'npm_install',
]

logger = logging.getLogger(__name__)

version_expr = re.compile('((?:\d+)(?:\.\d+)*)')

NODE_PATH = 'NODE_PATH'
NODE = 'node'
NPM = 'npm'
DEP_KEYS = ('dependencies', 'devDependencies')


if sys.version_info < (3,):  # pragma: no cover
    str = unicode  # noqa: F821

lower = str.lower


def _get_bin_version(bin_path, version_flag='-v', _from=None, _to=None):
    try:
        version_str = version_expr.search(
            check_output([bin_path, version_flag]).decode('ascii')
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


def null_validator(value):
    return value


def make_choice_validator(choices, default=NotImplemented, normalizer=None):
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
        # lowercase all the keys for easier comparison
        if normalizer:
            _choices = [(normalizer(key), value) for key, value in choices]
        return _choices

    choices = normalize_all(choices)

    def choice_validator(value):
        if normalizer:
            value = normalizer(value)
        if not value and default is not NotImplemented:
            return default
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
           choices=None, default_value=NotImplemented, normalizer=str.lower,
           _stdin=sys.stdin, _stdout=sys.stdout):
    """
    Provide a command line prompt.

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

    _stdout.write(question)
    _stdout.write(' ')

    choice_keys = []

    if validator is None:
        if choices:
            validator = make_choice_validator(
                choices, default_value, normalizer)
            choice_keys = [choice for choice, mapped in choices]
        else:
            validator = null_validator

    answer = NotImplemented
    while answer is NotImplemented:
        if choice_keys:
            _stdout.write('(')
            _stdout.write('/'.join(choice_keys))
            _stdout.write(') ')
        _stdout.flush()
        try:
            answer = validator(_stdin.readline().strip())
        except ValueError as e:
            _stdout.write('%s' % e)
            _stdout.write(' ')
        except KeyboardInterrupt:
            _stdout.write('Aborted.\n')
            answer = None

    return answer


class Driver(object):

    indent = 4

    def __init__(self, node_bin=NODE, pkg_manager_bin=NPM,
                 node_path=None, pkgdef_filename=PACKAGE_JSON,
                 ):
        """
        Optional Arguments:

        node_bin
            Path to node binary.  Defaults to ``node``.
        pkg_manager_bin
            Path to package manager binary.  Defaults to ``npm``.
        node_path
            Overrides NODE_PATH environment variable.
        pkgdef_filename
            The file name of the package.json file - defaults to
            ``package.json``.
        """

        self.node_path = node_path
        self.node_bin = node_bin
        self.pkg_manager_bin = pkg_manager_bin
        self.pkgdef_filename = pkgdef_filename

    def get_node_version(self):
        return _get_bin_version(self.node_bin, _from=1)

    def get_pkg_manager_version(self):
        return _get_bin_version(self.pkg_manager_bin)

    def pkg_manager_init(
            self, package_name=None,
            overwrite=False, merge=False):
        """
        If this class is initiated using standard procedures, this will
        emulate the functionality of ``npm init`` for the generation of
        a working ``package.json``, but without asking users for input
        but instead uses information available through the distribution
        packages within ``setuptools``.

        Arguments:

        package_name
            The python package to source the package.json from.

        overwrite
            Boolean flag; if set, overwrite package.json with the newly
            generated ``package.json``.

        merge
            Boolean flag; if set, implies overwrite.  However this will
            keep details defined in existing ``package.json`` and only
            merge dependencies/devDependencies defined by the specified
            Python package.

        Returns True if successful; can be achieved by writing a new
        file or that the existing one matches with the expected version.
        Returns False otherwise.
        """

        # this will be modified in place
        original_json = {}
        # package_json is the one that will get written out, if needed.
        package_json = flatten_package_json(
            package_name, filename=self.pkgdef_filename)

        existed = exists(self.pkgdef_filename)

        if existed:
            try:
                with open(self.pkgdef_filename, 'r') as fd:
                    original_json = json.load(fd)
            except ValueError:
                logger.warning(
                    "Ignoring existing malformed 'package.json'.")
            except (IOError, OSError):
                logger.error(
                    "Reading of existing 'package.json' failed; "
                    "please confirm that it is a file and/or permissions to "
                    "read and write is permitted before retrying."
                )
                # Cowardly giving up.
                raise

            if merge:
                # Merge the generated on top of the original.
                overwrite = True  # implied, as documented.
                updates = generate_merge_dict(
                    DEP_KEYS, original_json, package_json,
                )
                final = {}
                final.update(original_json)
                final.update(package_json)
                final.update(updates)
                package_json = final

            if original_json == package_json:
                # Well, if original existing one is identical with the
                # generated version, we got it, and we are done here.
                return True

            if not overwrite:
                return False

        if package_json:
            # Only write one if we actually got data.
            with open(self.pkgdef_filename, 'w') as fd:
                json.dump(package_json, fd, indent=self.indent)

    def pkg_manager_install(self, package_name=None):
        """
        If this class is initiated using standard procedures, this will
        install node_modules into the current working directory for the
        specific package.  With an already available ``package.json``
        file, the init process will be skipped.
        """

        if package_name and not exists(self.pkgdef_filename):
            self.pkg_manager_init(package_name)

        kw = {}
        env = {}

        if self.node_path:
            env[NODE_PATH] = self.node_path

        if env:
            kw['env'] = env

        call([self.pkg_manager_bin, 'install'], **kw)


_inst = Driver()
get_node_version = _inst.get_node_version
# Defaults rely on npm.  The same Driver class should be usable with
# bower when constructed with the relevant reference to its binary.
get_npm_version = _inst.get_pkg_manager_version
npm_init = _inst.pkg_manager_init
npm_install = _inst.pkg_manager_install
package_json = _inst.pkgdef_filename
