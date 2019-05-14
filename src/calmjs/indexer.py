# -*- coding: utf-8 -*-
"""
Various loaders.
"""

from __future__ import absolute_import

import fnmatch
import pkg_resources

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


def resource_filename_mod_dist(module_name, dist):
    """
    Given a module name and a distribution, attempt to resolve the
    actual path to the module.
    """

    try:
        return pkg_resources.resource_filename(
            dist.as_requirement(), join(*module_name.split('.')))
    except pkg_resources.DistributionNotFound:
        logger.warning(
            "distribution '%s' not found, falling back to resolution using "
            "module_name '%s'", dist, module_name,
        )
        return pkg_resources.resource_filename(module_name, '')


# An attempt was made to use the provided distribution argument directly
# implemented as following:
#
# def resource_filename_mod_dist(module_name, dist):
#     """
#     Given a module name and a distribution, with the assumption that the
#     distribution is part of the default working set, resolve the actual
#     path to the module.
#     """
#
#     return dist.get_resource_filename(
#         pkg_resources.working_set, join(*module_name.split('.')))
#

# However, we cannot necessary access the underlying resource manager as
# that is "hidden" as an implementation detail, and that this duplicates
# code provided by that class.  Also due to the inconsistency with how
# values are handled, namely that the provided manager is generally
# irrelvant unless the provided distribution belongs to/references a
# zipped-egg, which IProvider.get_resource_filename implementation will
# actually make use of the manager to acquire relevant information.
#
# That said, just for clarity (and not waste some hours that was spent
# investigating whether we can bypass certain things to save some time
# on other test setup), it was discovered that the resolution of the
# path is done during the construction of the working_set, such that it
# ultimately will result in a path if the dist.as_requirement is not
# called and that the get_resource_filename is invoked directly.  The
# points of interests in the pkg_resources module:
# - find_on_path (resolves below via dist_factory)
# - distributions_from_metadata (which uses PathMetadata)
# The relevant path for the Distribution is ultimately found in
# `Distribution._provider.module_path`.


def resource_filename_mod_entry_point(module_name, entry_point):
    """
    If a given package declares a namespace and also provide submodules
    nested at that namespace level, and for whatever reason that module
    is needed, Python's import mechanism will not have a path associated
    with that module.  However, if given an entry_point, this path can
    be resolved through its distribution.  That said, the default
    resource_filename function does not accept an entry_point, and so we
    have to chain that back together manually.
    """

    if entry_point.dist is None:
        # distribution missing is typically caused by mocked entry
        # points from tests; silently falling back to basic lookup
        result = pkg_resources.resource_filename(module_name, '')
    else:
        result = resource_filename_mod_dist(module_name, entry_point.dist)

    if not result:
        logger.warning(
            "fail to resolve the resource path for module '%s' and "
            "entry_point '%s'", module_name, entry_point
        )
        return None
    if not exists(result):
        logger.warning(
            "resource path resolved to be '%s' for module '%s' and "
            "entry_point '%s', but it does not exist",
            result, module_name, entry_point,
        )
        return None
    return result


def modgen(
        module, entry_point,
        modpath='pkg_resources', globber='root', fext=JS_EXT,
        registry=_utils):
    """
    JavaScript styled module location listing generator.

    Arguments:

    module
        The Python module to start fetching from.

    entry_point
        This is the original entry point that has a distribution
        reference such that the resource_filename API call may be used
        to locate the actual resources.

    Optional Arguments:

    modpath
        The name to the registered modpath function that will fetch the
        paths belonging to the module.  Defaults to 'pkg_resources'.

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
    module_base_paths = modpath_f(module, entry_point)

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
def modpath_all(module, entry_point):
    """
    Provides the raw __path__.  Incompatible with PEP 302-based import
    hooks and incompatible with zip_safe packages.

    Deprecated.  Will be removed by calmjs-4.0.
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
def modpath_last(module, entry_point):
    """
    Provides the raw __path__.  Incompatible with PEP 302-based import
    hooks and incompatible with zip_safe packages.

    Deprecated.  Will be removed by calmjs-4.0.
    """

    module_paths = modpath_all(module, entry_point)
    if len(module_paths) > 1:
        logger.info(
            "module '%s' has multiple paths, default selecting '%s' as base.",
            module.__name__, module_paths[-1],
        )
    return module_paths[-1:]


@register('modpath')
def modpath_pkg_resources(module, entry_point):
    """
    Goes through pkg_resources for compliance with various PEPs.

    This one accepts a module as argument.
    """

    result = []
    try:
        path = resource_filename_mod_entry_point(module.__name__, entry_point)
    except ImportError:
        logger.warning("module '%s' could not be imported", module.__name__)
    except Exception:
        logger.warning("%r does not appear to be a valid module", module)
    else:
        if path:
            result.append(path)
    return result


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


def mapper(module, entry_point,
           modpath='pkg_resources', globber='root', modname='es6',
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
def mapper_es6(module, entry_point, globber='root', fext=JS_EXT):
    """
    Default mapper

    Finds the latest path declared for the module at hand and extract
    a list of importable JS modules using the es6 module import format.
    """

    return mapper(
        module, entry_point=entry_point, modpath='pkg_resources',
        globber=globber, modname='es6', fext=fext)


@register('mapper')
def mapper_python(module, entry_point, globber='root', fext=JS_EXT):
    """
    Default mapper using python style globber

    Finds the latest path declared for the module at hand and extract
    a list of importable JS modules using the es6 module import format.
    """

    return mapper(
        module, entry_point=entry_point, modpath='pkg_resources',
        globber=globber, modname='python', fext=fext)
