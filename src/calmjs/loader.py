# -*- coding: utf-8 -*-
"""
Various loaders.
"""

import fnmatch

from logging import getLogger
from itertools import chain
from glob import iglob
from os.path import join
from os.path import relpath
from os.path import sep
from os import walk

logger = getLogger(__name__)

JS_EXT = '.js'

_marker = object()


def module_mapper(f):
    f._marker = _marker
    return f


def modpath_all(module):
    module_paths = getattr(module, '__path__', [])
    if not module_paths:
        logger.warning(
            '%s does not appear to be a namespace module or does not export '
            'available paths onto the filesystem; JavaScript source files '
            'cannot be extracted from this module.',
            module.__name__
        )
    return module_paths


def modpath_single(module):
    module_paths = modpath_all(module)
    if len(module_paths) > 1:
        logger.info(
            'module `%s` has multiple paths, default selecting `%s` as base.',
            module.__name__, module_paths[-1],
        )
    return module_paths[-1:]


def glob_current(root, patt):
    return iglob(join(root, patt))


def glob_recursive(root, patt):
    for root, dirnames, filenames in walk(root):
        for filename in fnmatch.filter(filenames, patt):
            yield join(root, filename)


def _modgen(module, modpath=modpath_single, globber=glob_current, fext=JS_EXT):
    """
    JavaScript styled module location listing generator.

    Arguments:

    module
        The Python module to start fetching from.

    Optional Arguments:

    modpath
        The function that will fetch where the module lives.  Defaults
        to the one that extracts a single, latest path.

    globber
        The file globbing function.  Defaults to one that will only glob
        the local path.

    fext
        The filename extension to extract files from.

    Returns a 3-tuple of

    - raw list of module names
    - the source base path to the python module (equivalent to module)
    - the relative path to the actual module
    """

    logger.debug(
        'modgen generating file listing for module %s',
        module.__name__,
    )

    module_frags = module.__name__.split('.')
    module_base_paths = modpath(module)

    for module_base_path in module_base_paths:
        logger.debug('searching for *%s files in %s', fext, module_base_path)
        for path in globber(module_base_path, '*' + fext):
            mod_path = (relpath(path, module_base_path))
            yield (
                module_frags + mod_path[:-len(fext)].split(sep),
                module_base_path,
                mod_path,
            )


@module_mapper
def default(module):
    """
    Default mapper

    Finds the latest path declared for the module at hand and extract
    a list of importable JS modules using the es6 module import format.
    """

    return {
        '/'.join(modname): '/'.join((base, subpath))
        for modname, base, subpath in _modgen(module)
    }


@module_mapper
def default_py(module):
    """
    Default mapper using python style globber

    Finds the latest path declared for the module at hand and extract
    a list of importable JS modules using the es6 module import format.
    """

    return {
        '.'.join(modname): '/'.join((base, subpath))
        for modname, base, subpath in _modgen(module)
    }
