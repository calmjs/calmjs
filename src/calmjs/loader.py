# -*- coding: utf-8 -*-
"""
Various loaders.
"""

from logging import getLogger
from glob import glob
from os.path import join
from os.path import relpath
from os.path import sep

logger = getLogger(__name__)

JS_EXT = '.js'

_marker = object()


def module_mapper(f):
    f._marker = _marker
    return f


def _get_module_path(module):
    module_paths = getattr(module, '__path__', [])
    if not module_paths:
        logger.warning(
            '%s not a namespace module, cannot map JavaScript source files',
            module.__name__
        )
        return None

    if len(module_paths) > 1:
        path = module_paths[-1]
        logger.warning(
            'module `%s` has multiple paths, default selecting `%s` as base.',
            module.__name__, path
        )
    else:
        path = module_paths[0]

    return path


def _es6mod_globber(module_name, module_base_path):
    """
    The globber that returns a map of JavaScript modules named using the
    es6 style of namespaces/modules (using '/' as separator).
    """

    module_frags = module_name.split('.')
    return {
        '/'.join(module_frags + relpath(
            path[:-len(JS_EXT)], module_base_path
        ).split(sep)): path
        for path in glob(join(module_base_path, '*' + JS_EXT))
    }


def _pymod_globber(module_name, module_base_path):
    """
    The globber that returns a map of JavaScript modules named using the
    Python style for namespaces/modules (using '.' as separator).
    """

    return {
        '.'.join([module_name] + relpath(
            path[:-len(JS_EXT)], module_base_path
        ).split(sep)): path
        for path in glob(join(module_base_path, '*' + JS_EXT))
    }


@module_mapper
def default(module):
    """
    Default mapper

    Finds the latest path declared for the module at hand and extract
    a list of importable JS modules using the es6 module import format.
    """

    path = _get_module_path(module)
    if path is None:
        return []
    return _es6mod_globber(module.__name__, path)


@module_mapper
def default_py(module):
    """
    Default mapper using python style globber

    Finds the latest path declared for the module at hand and extract
    a list of importable JS modules using the es6 module import format.
    """

    path = _get_module_path(module)
    if path is None:
        return []
    return _pymod_globber(module.__name__, path)
