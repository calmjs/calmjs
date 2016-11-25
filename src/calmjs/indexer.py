# -*- coding: utf-8 -*-
"""
Various loaders.
"""

from __future__ import absolute_import

import fnmatch
import pkg_resources
import warnings

from logging import getLogger
from glob import iglob
from os.path import exists
from os.path import join
from os.path import relpath
from os.path import sep
from os import walk

logger = getLogger(__name__)

JS_EXT = '.js'

_utils = {
    'modpath': {},
    'globber': {},
    'modname': {},
    'mapper': {},
}


def resource_filename_mod_entry_point(module, entry_point):
    """
    If a given package declares a namespace and also provide submodules
    nested at that namespace level, and for whatever reason that module
    is needed, Python's import mechanism will not have a path associated
    with that module.  However, if given an entry_point, this path can
    be resolved through its distribution.  That said, the default
    resource_filename function does not accept an entry_point, and so we
    have to chain that back together manually.
    """

    if not entry_point:
        return pkg_resources.resource_filename(module.__name__, '')

    try:
        namespaces = entry_point.dist.get_metadata(
            'namespace_packages.txt').split()
    except (OSError, IOError, AttributeError):
        return pkg_resources.resource_filename(module.__name__, '')

    if module.__name__ not in namespaces:
        return pkg_resources.resource_filename(module.__name__, '')

    try:
        result = pkg_resources.resource_filename(
            entry_point.dist.as_requirement(), module.__name__)
        if exists(result):
            return result
        else:
            return pkg_resources.resource_filename(module.__name__, '')
    except Exception:
        # either not a properly registered requirement (somehow), not a
        # proper module, or that the namespace does not exist in the
        # provided module.
        logger.warning(
            "module '%s' resolved by entry_point '%s' resulted in unexpected "
            "error when trying to resolve resources; falling back to standard "
            "retrival", module, entry_point,
        )
        return pkg_resources.resource_filename(module.__name__, '')


def modgen(
        module, entry_point=None,
        modpath='last', globber='root', fext=JS_EXT,
        registry=_utils):
    """
    JavaScript styled module location listing generator.

    Arguments:

    module
        The Python module to start fetching from.

    Optional Arguments:

    modpath
        The name to the registered modpath function that will fetch the
        paths belonging to the module.  Defaults to 'last', which only
        extracts the latest path registered to the module.

    globber
        The name to the registered file globbing function.  Defaults to
        one that will only glob the local path.

    fext
        The filename extension to match.  Defaults to `.js`.

    registry
        The "registry" to extract the functions from

    Yields 3-tuples of

    - raw list of module name fragments
    - the source base path to the python module (equivalent to module)
    - the relative path to the actual module

    For each of the module basepath and source files the globber finds.
    """

    globber_f = globber if callable(globber) else registry['globber'][globber]
    modpath_f = modpath if callable(modpath) else registry['modpath'][modpath]

    logger.debug(
        'modgen generating file listing for module %s',
        module.__name__,
    )

    module_frags = module.__name__.split('.')
    try:
        module_base_paths = modpath_f(module, entry_point)
    except TypeError:
        # missing entry_point argument; legacy calling.
        module_base_paths = modpath_f(module)
        msg = (
            'provided modpath %r method will need to accept entry_point '
            'argument by calmjs-3.0.0' % modpath_f
        )
        warnings.warn(msg, DeprecationWarning)
        logger.warning(msg)

    for module_base_path in module_base_paths:
        logger.debug('searching for *%s files in %s', fext, module_base_path)
        for path in globber_f(module_base_path, '*' + fext):
            mod_path = (relpath(path, module_base_path))
            yield (
                module_frags + mod_path[:-len(fext)].split(sep),
                module_base_path,
                mod_path,
            )


def register(util_type, registry=_utils):
    """
    Crude, local registration decorator for a crude local registry of
    all utilities local to this module.
    """

    def marker(f):
        mark = util_type + '_'
        if not f.__name__.startswith(mark):
            raise TypeError(
                'not registering %s to %s' % (f.__name__, util_type))
        registry[util_type][f.__name__[len(mark):]] = f
        return f
    return marker


@register('modpath')
def modpath_all(module, entry_point=None):
    """
    Provides the raw __path__.  Incompatible with PEP 302-based import
    hooks and incompatible with zip_safe packages.

    Deprecated.  Will be removed by calmjs-2.0.
    """

    module_paths = getattr(module, '__path__', [])
    if not module_paths:
        logger.warning(
            "module '%s' does not appear to be a namespace module or does not "
            "export available paths onto the filesystem; JavaScript source "
            "files cannot be extracted from this module.", module.__name__
        )
    return module_paths


@register('modpath')
def modpath_last(module, entry_point=None):
    """
    Provides the raw __path__.  Incompatible with PEP 302-based import
    hooks and incompatible with zip_safe packages.

    Deprecated.  Will be removed by calmjs-2.0.
    """

    module_paths = modpath_all(module)
    if len(module_paths) > 1:
        logger.info(
            "module '%s' has multiple paths, default selecting '%s' as base.",
            module.__name__, module_paths[-1],
        )
    return module_paths[-1:]


@register('modpath')
def modpath_pkg_resources(module, entry_point=None):
    """
    Goes through pkg_resources for compliance with various PEPs.

    This one accepts a module as argument.
    """

    try:
        return [resource_filename_mod_entry_point(module, entry_point)]
    except ImportError:
        logger.warning("%r could not be located as a module", module)
    except Exception:
        logger.warning("%r does not appear to be a valid module", module)

    return []


@register('globber')
def globber_root(root, patt):
    return iglob(join(root, patt))


@register('globber')
def globber_recursive(root, patt):
    for root, dirnames, filenames in walk(root):
        for filename in fnmatch.filter(filenames, patt):
            yield join(root, filename)


@register('modname')
def modname_es6(fragments):
    """
    Generates ES6 styled module names from fragments.
    """

    return '/'.join(fragments)


@register('modname')
def modname_python(fragments):
    """
    Generates Python styled module names from fragments.
    """

    return '.'.join(fragments)


def mapper(module, entry_point=None,
           modpath='last', globber='root', modname='es6',
           fext=JS_EXT, registry=_utils):
    """
    General mapper

    Loads components from the micro registry.
    """

    modname_f = modname if callable(modname) else _utils['modname'][modname]

    return {
        modname_f(modname_fragments): join(base, subpath)
        for modname_fragments, base, subpath in modgen(
            module, entry_point=entry_point,
            modpath=modpath, globber=globber,
            fext=fext, registry=_utils)
    }


@register('mapper')
def mapper_es6(module, entry_point=None):
    """
    Default mapper

    Finds the latest path declared for the module at hand and extract
    a list of importable JS modules using the es6 module import format.
    """

    return mapper(
        module, entry_point=entry_point, modpath='pkg_resources',
        globber='root', modname='es6')


@register('mapper')
def mapper_python(module, entry_point=None):
    """
    Default mapper using python style globber

    Finds the latest path declared for the module at hand and extract
    a list of importable JS modules using the es6 module import format.
    """

    return mapper(
        module, entry_point=entry_point, modpath='pkg_resources',
        globber='root', modname='python')
