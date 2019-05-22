# -*- coding: utf-8 -*-
"""
This provides a "toolchain" for the calmjs framework.

The toolchain module provides two classes, a ``Spec`` which instances of
act as the orchestration object for the ``Toolchain`` instances, where
the states of a single workflow through it is tracked.  The other being
the ``Toolchain`` class, which `compiles`, `assembles` and `links` the
stuff as specified in the ``Spec`` into a standalone `module`, which can
be treated as an artifact file.  This whole thing jumpstarts that
process.

This whole thing started simply because the author thought it is a lot
easier to deal with JavaScript when one treats that as a compilation
target.  However given that the generic method works better, this module
encapsulates the generalized implementation of the previous version.

To better convey the understanding of how this came to place, the
following terms and variable name, prefix and suffixes have been defined
to carry the following meanings that is applicable throughout the entire
calmjs system:

modname
    A JavaScript path for a given module import system that it might
    have.  The Python analogue is the name of a given import module.
    Using the default mapper, one might map a Python module with the
    name ``calmjs.toolchain`` to ``calmjs/toolchain``.  While relative
    modpaths (i.e. identifiers beginning with './') are supported by
    most JavaScript/Node.js based import systems, its usage from within
    calmjs framework is discouraged.

sourcepath
    An absolute path on the local filesystem to the source file for a
    given modpath.  These two values (modpath and sourcepath) serves as
    the foundational mapping from a JavaScript module name to its
    corresponding source file.  Previously, this was simply named
    'source', so certain arguments remain named like so.

targetpath
    A relative path to a build directory (build_dir) serving as the
    write target for whatever proccessing done by the toolchain
    implementation to the file provided at the associated sourcepath.
    Note that by default this is NOT normalized to the currently running
    OS platform at generation time, due to varying and potentially
    complex internal/external integration usages.

    The relative path version (again, from build_dir) is typically
    recorded by instances of ``Spec`` objects that have undergone a
    ``Toolchain`` run.  Previously, this was simply named 'target'.

modpath
    Typically identical to modname, however the slight difference is
    that this is the transformed value that is to be better understood
    by the underlying tools.  Think of this as the post compiled value,
    or an alternative import location that is only applicable in the
    post-compiled context, specific to the toolchain class that it
    intends to encapsulate.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

import codecs
import errno
import logging
import re
import shutil
import sys
import warnings
from collections import namedtuple
from functools import partial
from inspect import currentframe
from traceback import format_stack
from os import mkdir
from os import makedirs
from os.path import basename
from os.path import join
from os.path import dirname
from os.path import exists
from os.path import isfile
from os.path import isdir
from os.path import normpath
from os.path import realpath
from tempfile import mkdtemp

from pkg_resources import Requirement
from pkg_resources import working_set as default_working_set

from calmjs.parse.io import read
from calmjs.parse.io import write
from calmjs.parse.parsers.es5 import parse
from calmjs.parse.unparsers.base import BaseUnparser
from calmjs.parse.unparsers.es5 import pretty_printer
from calmjs.parse.sourcemap import encode_sourcemap

from calmjs.base import BaseDriver
from calmjs.base import BaseRegistry
from calmjs.base import BaseLoaderPluginRegistry
from calmjs.base import PackageKeyMapping
from calmjs.registry import get as get_registry
from calmjs.exc import AdviceAbort
from calmjs.exc import AdviceCancel
from calmjs.exc import ValueSkip
from calmjs.exc import ToolchainAbort
from calmjs.exc import ToolchainCancel
from calmjs.utils import raise_os_error
from calmjs.utils import pdb_set_trace
from calmjs.vlqsm import SourceWriter

logger = logging.getLogger(__name__)

__all__ = [
    'AdviceRegistry', 'Spec', 'Toolchain', 'null_transpiler',

    'dict_setget', 'dict_setget_dict', 'dict_update_overwrite_check',

    'spec_update_loaderplugin_registry',
    'spec_update_sourcepath_filter_loaderplugins',

    'toolchain_spec_prepare_loaderplugins',

    'toolchain_spec_compile_entries', 'ToolchainSpecCompileEntry',

    'CALMJS_TOOLCHAIN_ADVICE',

    'SETUP', 'CLEANUP', 'SUCCESS',

    'AFTER_FINALIZE', 'BEFORE_FINALIZE', 'AFTER_LINK', 'BEFORE_LINK',
    'AFTER_ASSEMBLE', 'BEFORE_ASSEMBLE', 'AFTER_COMPILE', 'BEFORE_COMPILE',
    'AFTER_PREPARE', 'BEFORE_PREPARE', 'AFTER_TEST', 'BEFORE_TEST',

    'ADVICE_PACKAGES', 'ARTIFACT_PATHS', 'BUILD_DIR',
    'CALMJS_MODULE_REGISTRY_NAMES',
    'CALMJS_LOADERPLUGIN_REGISTRY_NAME',
    'CALMJS_LOADERPLUGIN_REGISTRY',
    'CALMJS_TEST_REGISTRY_NAMES',
    'CONFIG_JS_FILES', 'DEBUG',
    'EXPORT_MODULE_NAMES', 'EXPORT_PACKAGE_NAMES',
    'EXPORT_TARGET', 'EXPORT_TARGET_OVERWRITE',
    'SOURCE_MODULE_NAMES', 'SOURCE_PACKAGE_NAMES',
    'TEST_MODULE_NAMES', 'TEST_MODULE_PATHS_MAP', 'TEST_PACKAGE_NAMES',
    'TOOLCHAIN_BIN_PATH',
    'WORKING_DIR',
]

# these are the only non-key entities that should be in this module, as
# they currently reference auxilary registry classes that are currently
# residing in this module.
CALMJS_TOOLCHAIN_ADVICE = 'calmjs.toolchain.advice'
CALMJS_TOOLCHAIN_ADVICE_APPLY_SUFFIX = '.apply'

# define these as reserved advice names
SETUP = 'setup'
CLEANUP = 'cleanup'
SUCCESS = 'success'
AFTER_TEST = 'after_test'  # reserved however unused in this module
BEFORE_TEST = 'before_test'  # reserved however unused in this module
AFTER_FINALIZE = 'after_finalize'
BEFORE_FINALIZE = 'before_finalize'
AFTER_LINK = 'after_link'
BEFORE_LINK = 'before_link'
AFTER_ASSEMBLE = 'after_assemble'
BEFORE_ASSEMBLE = 'before_assemble'
AFTER_COMPILE = 'after_compile'
BEFORE_COMPILE = 'before_compile'
AFTER_PREPARE = 'after_prepare'
BEFORE_PREPARE = 'before_prepare'

# define these as reserved spec keys

# packages that have extra _optional_ advices supplied that have to be
# manually included.
ADVICE_PACKAGES = 'advice_packages'
# advice packages that have been applied to the spec via advice registry
# apply_toolchain_spec method.
ADVICE_PACKAGES_APPLIED_REQUIREMENTS = 'advice_packages_applied_requirements'
# listing of absolute locations on the file system where these bundled
# artifact files are.
ARTIFACT_PATHS = 'artifact_paths'
# build directory
BUILD_DIR = 'build_dir'
# the key for overriding the advice registry to be use
CALMJS_TOOLCHAIN_ADVICE_REGISTRY = 'calmjs_toolchain_advice_registry'
# source registries that have been used
CALMJS_MODULE_REGISTRY_NAMES = 'calmjs_module_registry_names'
CALMJS_TEST_REGISTRY_NAMES = 'calmjs_test_registry_names'
# loaderplugin registry related.
CALMJS_LOADERPLUGIN_REGISTRY_NAME = 'calmjs_loaderplugin_registry_name'
CALMJS_LOADERPLUGIN_REGISTRY = 'calmjs_loaderplugin_registry'
# configuration file for enabling execution of code in build directory
CONFIG_JS_FILES = 'config_js_files'
# for debug level
DEBUG = 'debug'
# the module names that have been exported out
EXPORT_MODULE_NAMES = 'export_module_names'
# the package names that have been exported out; not currently supported
# by any part of the library, but reserved nonetheless.
EXPORT_PACKAGE_NAMES = 'export_package_names'
# the container for the export target; either a file or directory; this
# should not be changed after the prepare step.
EXPORT_TARGET = 'export_target'
# specify that export target is safe to be overwritten.
EXPORT_TARGET_OVERWRITE = 'export_target_overwrite'
# for loaderplugin sourcepath dicts, where the maps are grouped by the
# name of the plugin; an intermediate step for processing of loader
# plugins
LOADERPLUGIN_SOURCEPATH_MAPS = 'loaderplugin_sourcepath_maps'
# if true, generate source map
GENERATE_SOURCE_MAP = 'generate_source_map'
# source module names; currently not supported by any part of the
# library, but reserved nonetheless
SOURCE_MODULE_NAMES = 'source_module_names'
# source Python package names that have been specified for source file
# extraction before the workflow, or the top level package(s); should
# not include automatically derived required packages.
SOURCE_PACKAGE_NAMES = 'source_package_names'
# for testing
# name of test modules
TEST_MODULE_NAMES = 'test_module_names'
# mapping of test module to their paths; i.e. sourcepath_map, but not
# labled as one to prevent naming conflicts (and they ARE to be
# standalone modules to be used directly by the toolchain and testing
# integration layer.
TEST_MODULE_PATHS_MAP = 'test_module_paths_map'
# name of test package
TEST_PACKAGE_NAMES = 'test_package_names'
# the binary that the toolchain encapsulates.
TOOLCHAIN_BIN_PATH = 'toolchain_bin_path'
# the working directory
WORKING_DIR = 'working_dir'


def cls_to_name(cls):
    return '%s:%s' % (cls.__module__, cls.__name__)


def _opener(*a):
    return codecs.open(*a, encoding='utf-8')


def partial_open(*a):
    return partial(codecs.open, *a, encoding='utf-8')


def _check_key_exists(spec, keys):
    for key in keys:
        if key not in spec:
            continue
        logger.error(
            "attempted to write '%s' to spec but key already exists; "
            "not overwriting, skipping", key
        )
        return True
    return False


def _deprecation_warning(msg):
    warnings.warn(msg, DeprecationWarning)
    logger.warning(msg)


def dict_setget(d, key, value):
    value = d[key] = d.get(key, value)
    return value


def dict_setget_dict(d, key):
    return dict_setget(d, key, {})


def dict_update_overwrite_check(base, fresh):
    """
    For updating a base dict with a fresh one, returning a list of
    3-tuples containing the key, previous value (base[key]) and the
    fresh value (fresh[key]) for all colliding changes (reassignment of
    identical values are omitted).
    """

    result = [
        (key, base[key], fresh[key])
        for key in set(base.keys()) & set(fresh.keys())
        if base[key] != fresh[key]
    ]
    base.update(fresh)
    return result


# Spec functions for interfacing with loaderplugins
#
# The following functions (named in the format spec_*_loaderplugin_*)
# are helpers for extracting and filtering the mappings for interfacing
# with the loaderplugin helpers through the registry system.  These
# helpers are here as they are part of the toolchain, not as part of the
# loaderplugin module due to that module being the part that couples
# tightly with npm.

def spec_update_loaderplugin_registry(spec, default=None):
    """
    Resolve a BasePluginLoaderRegistry instance from spec, and update
    spec[CALMJS_LOADERPLUGIN_REGISTRY] with that value before returning
    it.
    """

    registry = spec.get(CALMJS_LOADERPLUGIN_REGISTRY)
    if isinstance(registry, BaseLoaderPluginRegistry):
        logger.debug(
            "loaderplugin registry '%s' already assigned to spec",
            registry.registry_name)
        return registry
    elif not registry:
        # resolving registry
        registry = get_registry(spec.get(CALMJS_LOADERPLUGIN_REGISTRY_NAME))
        if isinstance(registry, BaseLoaderPluginRegistry):
            logger.info(
                "using loaderplugin registry '%s'", registry.registry_name)
            spec[CALMJS_LOADERPLUGIN_REGISTRY] = registry
            return registry

    # acquire the real default instance, if possible.
    if not isinstance(default, BaseLoaderPluginRegistry):
        default = get_registry(default)
        if not isinstance(default, BaseLoaderPluginRegistry):
            logger.info(
                "provided default is not a valid loaderplugin registry")
            default = None

    if default is None:
        default = BaseLoaderPluginRegistry('<default_loaderplugins>')

    # TODO determine the best way to optionally warn about this for
    # toolchains that require this.
    if registry:
        logger.info(
            "object referenced in spec is not a valid loaderplugin registry; "
            "using default loaderplugin registry '%s'", default.registry_name)
    else:
        logger.info(
            "no loaderplugin registry referenced in spec; "
            "using default loaderplugin registry '%s'", default.registry_name)
    spec[CALMJS_LOADERPLUGIN_REGISTRY] = registry = default

    return registry


def spec_update_sourcepath_filter_loaderplugins(
        spec, sourcepath_map, sourcepath_map_key,
        loaderplugin_sourcepath_map_key=LOADERPLUGIN_SOURCEPATH_MAPS):
    """
    Take an existing spec and a sourcepath mapping (that could be
    produced via calmjs.dist.*_module_registry_dependencies functions)
    and split out the keys that does not contain loaderplugin syntax and
    assign it to the spec under sourcepath_key.

    For the parts with loader plugin syntax (i.e. modnames (keys) that
    contain a '!' character), they are instead stored under a different
    mapping under its own mapping identified by the plugin_name.  The
    mapping under loaderplugin_sourcepath_map_key will contain all
    mappings of this type.

    The resolution for the handlers will be done through the loader
    plugin registry provided via spec[CALMJS_LOADERPLUGIN_REGISTRY] if
    available, otherwise the registry instance will be acquired through
    the main registry using spec[CALMJS_LOADERPLUGIN_REGISTRY_NAME].

    For the example sourcepath_map input:

    sourcepath = {
        'module': 'something',
        'plugin!inner': 'inner',
        'plugin!other': 'other',
        'plugin?query!question': 'question',
        'plugin!plugin2!target': 'target',
    }

    The following will be stored under the following keys in spec:

    spec[sourcepath_key] = {
        'module': 'something',
    }

    spec[loaderplugin_sourcepath_map_key] = {
        'plugin': {
            'plugin!inner': 'inner',
            'plugin!other': 'other',
            'plugin?query!question': 'question',
            'plugin!plugin2!target': 'target',
        },
    }

    The goal of this function is to aid in processing each of the plugin
    types by batch, one level at a time.  It is up to the handler itself
    to trigger further lookups as there are implementations of loader
    plugins that do not respect the chaining mechanism, thus a generic
    lookup done at once may not be suitable.

    Note that nested/chained loaderplugins are not immediately grouped
    as they must be individually handled given that the internal syntax
    are generally proprietary to the outer plugin.  The handling will be
    dealt with at the Toolchain.compile_loaderplugin_entry method
    through the associated handler call method.

    Toolchain implementations may either invoke this directly as part
    of the prepare step on the required sourcepaths values stored in the
    spec, or implement this at a higher level before invocating the
    toolchain instance with the spec.
    """

    default = dict_setget_dict(spec, sourcepath_map_key)
    registry = spec_update_loaderplugin_registry(spec)

    # it is more loaderplugin_sourcepath_maps
    plugins = dict_setget_dict(spec, loaderplugin_sourcepath_map_key)

    for modname, sourcepath in sourcepath_map.items():
        parts = modname.split('!', 1)
        if len(parts) == 1:
            # default
            default[modname] = sourcepath
            continue

        # don't actually do any processing yet.
        plugin_name = registry.to_plugin_name(modname)
        plugin = dict_setget_dict(plugins, plugin_name)
        plugin[modname] = sourcepath


def toolchain_spec_prepare_loaderplugins(
        toolchain, spec,
        loaderplugin_read_key,
        handler_sourcepath_key,
        loaderplugin_sourcepath_map_key=LOADERPLUGIN_SOURCEPATH_MAPS):
    """
    A standard helper function for combining the filtered (e.g. using
    ``spec_update_sourcepath_filter_loaderplugins``) loaderplugin
    sourcepath mappings back into one that is usable with the standard
    ``toolchain_spec_compile_entries`` function.

    Arguments:

    toolchain
        The toolchain
    spec
        The spec

    loaderplugin_read_key
        The read_key associated with the loaderplugin process as set up
        for the Toolchain that implemented this.  If the toolchain has
        this in its compile_entries:

            ToolchainSpecCompileEntry('loaderplugin', 'plugsrc', 'plugsink')

        The loaderplugin_read_key it must use will be 'plugsrc'.

    handler_sourcepath_key
        All found handlers will have their handler_sourcepath method be
        invoked, and the combined results will be a dict stored in the
        spec under that key.

    loaderplugin_sourcepath_map_key
        It must be the same key to the value produced by
        ``spec_update_sourcepath_filter_loaderplugins``
    """

    # ensure the registry is applied to the spec
    registry = spec_update_loaderplugin_registry(
        spec, default=toolchain.loaderplugin_registry)

    # this one is named like so for the compile entry method
    plugin_sourcepath = dict_setget_dict(
        spec, loaderplugin_read_key + '_sourcepath')
    # the key is supplied by the toolchain that might make use of this
    if handler_sourcepath_key:
        handler_sourcepath = dict_setget_dict(spec, handler_sourcepath_key)
    else:
        # provide a null value for this.
        handler_sourcepath = {}

    for key, value in spec.get(loaderplugin_sourcepath_map_key, {}).items():
        handler = registry.get(key)
        if handler:
            # assume handler will do the job.
            logger.debug("found handler for '%s' loader plugin", key)
            plugin_sourcepath.update(value)
            logger.debug(
                "plugin_sourcepath updated with %d keys", len(value))
            # TODO figure out how to address the case where the actual
            # JavaScript module for the handling wasn't found.
            handler_sourcepath.update(
                handler.generate_handler_sourcepath(toolchain, spec, value))
        else:
            logger.warning(
                "loaderplugin handler for '%s' not found in loaderplugin "
                "registry '%s'; as arguments associated with loader plugins "
                "are specific, processing is disabled for this group; the "
                "sources referenced by the following names will not be "
                "compiled into the build target: %s",
                key, registry.registry_name, sorted(value.keys()),
            )


def toolchain_spec_compile_entries(
        toolchain, spec, entries, process_name, overwrite_log=None):
    """
    The standardized Toolchain Spec Entries compile function

    This function accepts a toolchain instance, the spec to be operated
    with and the entries provided for the process name.  The standard
    flow is to deferr the actual processing to the toolchain method
    `compile_{process_name}_entry` for each entry in the entries list.

    The generic compile entries method for the compile process.

    Arguments:

    toolchain
        The toolchain to be used for the operation.
    spec
        The spec to be operated with.
    entries
        The entries for the source.
    process_name
        The name of the specific compile process of the provided
        toolchain.
    overwrite_log
        A callable that will accept a 4-tuple of suffix, key, original
        and new value, if monitoring of overwritten values are required.
        suffix is derived from the modpath_suffix or targetpath_suffix
        of the toolchain instance, key is the key on any of the keys on
        either of those mappings, original and new are the original and
        the replacement value.
    """

    processor = getattr(toolchain, 'compile_%s_entry' % process_name)
    modpath_logger = (
        partial(overwrite_log, toolchain.modpath_suffix)
        if callable(overwrite_log) else None)
    targetpath_logger = (
        partial(overwrite_log, toolchain.targetpath_suffix)
        if callable(overwrite_log) else None)
    return process_compile_entries(
        processor, spec, entries, modpath_logger, targetpath_logger)


def process_compile_entries(
        processor, spec, entries, modpath_logger=None, targetpath_logger=None):
    """
    The generalized raw spec entry process invocation loop.
    """

    # Contains a mapping of the module name to the compiled file's
    # relative path starting from the base build_dir.
    all_modpaths = {}
    all_targets = {}
    # List of exported module names, should be equal to all keys of
    # the compiled and bundled sources.
    all_export_module_names = []

    def update(base, fresh, logger):
        if callable(logger):
            for dupes in dict_update_overwrite_check(base, fresh):
                logger(*dupes)
        else:
            base.update(fresh)

    for entry in entries:
        modpaths, targetpaths, export_module_names = processor(spec, entry)
        update(all_modpaths, modpaths, modpath_logger)
        update(all_targets, targetpaths, targetpath_logger)
        all_export_module_names.extend(export_module_names)

    return all_modpaths, all_targets, all_export_module_names


ToolchainSpecCompileEntry = namedtuple('ToolchainSpecCompileEntry', [
    'process_name', 'read_key', 'store_key', 'logger', 'log_level'])
ToolchainSpecCompileEntry.__new__.__defaults__ = (None, None)


def debugger(spec, extras):
    if not spec.get(DEBUG):
        return
    for key in extras:
        if not key.startswith('debug_'):
            continue
        name = key.split('_', 1)[1]
        logger.debug("debugger advised at '%s'", name)
        spec.advise(name, pdb_set_trace)


def null_transpiler(spec, reader, writer):
    writer.write(reader.read())


class Spec(dict):
    """
    Instances of these will track the progress through a Toolchain
    instance.
    """

    def __init__(self, *a, **kw):
        self._deprecation_match_4_0 = [(re.compile(p), r) for p, r in (
            ('^((?!generate)(.*))_source_map$', '\\1_sourcepath'),
            ('_targets$', '_targetpaths'),
        )]

        clean_kw = {
            self.__process_deprecated_key(k): v for k, v in kw.items()}

        super(Spec, self).__init__(*a, **clean_kw)
        self._advices = {}
        self._frames = {}
        self._called = set()

    def __process_deprecated_key(self, key):
        for patt, repl in self._deprecation_match_4_0:
            if patt.search(key):
                break
        else:
            return key

        new_key = patt.sub(repl, key)
        _deprecation_warning(
            "Spec key '%s' has been remapped to '%s' in calmjs-3.0.0; this "
            "automatic remap will be removed by calmjs-4.0.0" % (key, new_key)
        )
        return new_key

    def get(self, key, default=NotImplemented):
        key = self.__process_deprecated_key(key)
        if default is NotImplemented:
            return dict.get(self, key)
        else:
            return dict.get(self, key, default)

    def __getitem__(self, key):
        return dict.__getitem__(
            self, self.__process_deprecated_key(key))

    def __setitem__(self, key, value):
        return dict.__setitem__(
            self, self.__process_deprecated_key(key), value)

    def __repr__(self):
        debug = self.get(DEBUG)
        if not isinstance(debug, int) or debug < 2:
            return object.__repr__(self)
        # for a repr, helpers by pprint module and even json doesn't
        # deal with circular references for this, so just use the trusty
        # parent class and be done with it (even though I wanted a
        # sorted output, this is fine for now as I don't want to spam
        # logs without debugging enabled).
        return dict.__repr__(self)

    def update_selected(self, other, selected):
        """
        Like update, however a list of selected keys must be provided.
        """

        self.update({k: other[k] for k in selected})

    def __advice_stack_frame_protection(self, frame):
        """
        Overriding of this is only permitted if and only if your name is
        Megumin and you have a pet/familiar named Chomusuke.
        """

        if frame is None:
            logger.debug(
                'currentframe() returned None; frame protection disabled')
            return

        f_back = frame.f_back
        while f_back:
            if f_back.f_code is self.handle.__code__:
                raise RuntimeError(
                    "indirect invocation of '%s' by 'handle' is forbidden" %
                    frame.f_code.co_name,
                )
            f_back = f_back.f_back

    def advise(self, name, f, *a, **kw):
        """
        Add an advice that will be handled later by the handle method.

        Arguments:

        name
            The name of the advice group
        f
            A callable method or function.

        The rest of the arguments will be passed as arguments and
        keyword arguments to f when it's invoked.
        """

        if name is None:
            return

        advice = (f, a, kw)
        debug = self.get(DEBUG)

        frame = currentframe()
        if frame is None:
            logger.debug('currentframe() failed to return frame')
        else:
            if name in self._called:
                self.__advice_stack_frame_protection(frame)
            if debug:
                logger.debug(
                    "advise '%s' invoked by %s:%d",
                    name,
                    frame.f_back.f_code.co_filename, frame.f_back.f_lineno,
                )
                if debug > 1:
                    # use the memory address of the tuple which should
                    # be stable
                    self._frames[id(advice)] = ''.join(
                        format_stack(frame.f_back))

        self._advices[name] = self._advices.get(name, [])
        self._advices[name].append(advice)

    def handle(self, name):
        """
        Call all advices at the provided name.

        This has an analogue in the join point in aspected oriented
        programming, but the analogy is a weak one as we don't have the
        proper metaobject protocol to support this.  Implementation that
        make use of this system should make it clear that they will call
        this method with name associated with its group before and after
        its execution, or that the method at hand that want this invoked
        be called by this other conductor method.

        For the Toolchain standard steps (prepare, compile, assemble,
        link and finalize), this handle method will only be called by
        invoking the toolchain as a callable.  Calling those methods
        piecemeal will not trigger the invocation, even though it
        probably should.  Modules, classes and methods that desire to
        call their own handler should instead follow the convention
        where the handle be called before and after with the appropriate
        names.  For instance:

            def test(self, spec):
                spec.handle(BEFORE_TEST)
                # do the things
                spec.handle(AFTER_TEST)

        This arrangement will need to be revisited when a proper system
        is written at the metaclass level.

        Arguments:

        name
            The name of the advices group.  All the callables
            registered to this group will be invoked, last-in-first-out.
        """

        if name in self._called:
            logger.warning(
                "advice group '%s' has been called for this spec %r",
                name, self,
            )
            # only now ensure checking
            self.__advice_stack_frame_protection(currentframe())
        else:
            self._called.add(name)

        # Get a complete clone, so indirect manipulation done to the
        # reference that others have access to will not have an effect
        # within the scope of this execution.  Please refer to the
        # test_toolchain, test_spec_advice_no_infinite_pop test case.
        advices = []
        advices.extend(self._advices.get(name, []))

        if advices and self.get('debug'):
            logger.debug(
                "handling %d advices in group '%s' ", len(advices), name)

        while advices:
            try:
                # advice processing is done lifo (last in first out)
                values = advices.pop()
                advice, a, kw = values
                if not ((callable(advice)) and
                        isinstance(a, tuple) and
                        isinstance(kw, dict)):
                    raise TypeError
            except ValueError:
                logger.info('Spec advice extraction error: got %s', values)
            except TypeError:
                logger.info('Spec advice malformed: got %s', values)
            else:
                try:
                    try:
                        advice(*a, **kw)
                    except Exception as e:
                        # get that back by the id.
                        frame = self._frames.get(id(values))
                        if frame:
                            logger.info('Spec advice exception: %r', e)
                            logger.info(
                                'Traceback for original advice:\n%s', frame)
                        # continue on for the normal exception
                        raise
                except AdviceCancel as e:
                    logger.info(
                        "advice %s in group '%s' signaled its cancellation "
                        "during its execution: %s", advice, name, e
                    )
                    if self.get(DEBUG):
                        logger.debug(
                            'showing traceback for cancellation', exc_info=1,
                        )
                except AdviceAbort as e:
                    # this is a signaled error with a planned abortion
                    logger.warning(
                        "advice %s in group '%s' encountered a known error "
                        "during its execution: %s; continuing with toolchain "
                        "execution", advice, name, e
                    )
                    if self.get(DEBUG):
                        logger.warning(
                            'showing traceback for error', exc_info=1,
                        )
                except ToolchainCancel:
                    # this is the safe cancel
                    raise
                except ToolchainAbort as e:
                    logger.critical(
                        "an advice in group '%s' triggered an abort: %s",
                        name, str(e)
                    )
                    raise
                except KeyboardInterrupt:
                    raise ToolchainCancel('interrupted')
                except Exception as e:
                    # a completely unplanned failure
                    logger.critical(
                        "advice %s in group '%s' terminated due to an "
                        "unexpected exception: %s", advice, name, e
                    )
                    if self.get(DEBUG):
                        logger.critical(
                            'showing traceback for error', exc_info=1,
                        )


class AdviceRegistry(BaseRegistry):
    """
    Registry for Spec.advise application functions.

    The declaration is specific to one given toolchain, and they are
    declared as EntryPoints by packages.  Once defined, the package may
    be refernced as an Advice Package and it may be specified by the
    spec key ADVICE_PACKAGES.

    For example, if 'example.package' declares the following::

        [calmjs.toolchain.advice]
        example.package.toolchain:Toolchain = example.package.spec:apply

    And if that toolchain was invoked with a Spec that has the following
    definition:

        Spec({ADVICE_PACKAGES: ['example.package[extra1,extra2]']})

    Then the target specified by that entry_point will then be invoked
    with the spec and the extras passed as an unordered list.

    For the implementation to function as expected, it requires the
    Toolchain to invoke process_toolchain_spec_package of instances of
    this registry.
    """

    def _init(self):
        for entry_point in self.raw_entry_points:
            key = entry_point.dist.project_name
            records = self.records[key] = self.records.get(key, {})
            records[entry_point.name] = entry_point

    def _to_requirement(self, value):
        try:
            return Requirement.parse(value)
        except ValueError as e:
            logger.error(
                "the specified value '%s' for advice setup is not valid for "
                "a package/requirement: %s", value, e,
            )
            raise

    def get_record(self, name):
        return self.records.get(name)

    def applied_requirements_map_from_spec(self, toolchain, spec):
        # it may be good to warn about requirements that have been
        # replaced by the standalone method.
        return {
            req.name: req
            for req in spec.get(ADVICE_PACKAGES_APPLIED_REQUIREMENTS, [])
        }

    def apply_toolchain_spec(self, toolchain, spec):
        """
        Apply the advice packages as defined by this registry to the
        provided toolchain and spec.

        This implementation will first apply whatever ADVICE_PACKAGES
        are provided by the spec, before applying whatever else that may
        be applied by this registry instance.  Before application of the
        advice packages, the ADVICE_PACKAGES_APPLIED_REQUIREMENTS key
        from the spec will also be checked first to prevent the
        application of advice with the same requirement name.

        As the ADVICE_PACKAGES feature was originally implemented as a
        part of the SETUP advice applied by the Runtime class, and the
        implementation allowed multiple copies of the same requirement
        be applied, this feature will be maintained as this method
        implements a fully contained version of that along with the
        version that applies the ones recorded by the registry.
        However, multiple execution of this method will not reapply
        the ones that have been recorded as applied.
        """

        # first step: apply all the advice packages as found in the
        # provided spec, as these are specified to be necessary which
        # may override whatever other requirements might be specified
        # in the accompanied apply registry.
        spec_advice_packages = spec.get(ADVICE_PACKAGES, [])
        # construct a mapping based on the list of applied requirements
        # that have been also recorded on this spec by the common apply
        # standalone method.
        applied_req_map = self.applied_requirements_map_from_spec(
            toolchain, spec)
        newly_applied_req_map = {}

        logger.debug(
            "invoking apply_toolchain_spec using instance of %s named '%s'",
            cls_to_name(type(self)), self.registry_name,
        )

        for value in spec_advice_packages:
            try:
                req = self._to_requirement(value)
            except ValueError:
                # error log entry already generated by the above method.
                continue

            if req.name in applied_req_map:
                logger.warning(
                    "advice package '%s' already applied as '%s'; skipping",
                    req, applied_req_map[req.name]
                )
                continue

            if req.name in newly_applied_req_map:
                logger.warning(
                    "advice package '%s' was previously applied as '%s'; "
                    "the recommended usage manner is to only specify any "
                    "given advice package once complete with all the required "
                    "extras, and that underlying implementation be structured "
                    "in a manner that support this one-shot invocation "
                    "format",
                    req, newly_applied_req_map[req.name]
                )

            logger.debug("applying advice package '%s'", value)
            self._process_toolchain_spec_requirement(toolchain, spec, req)
            # still going to warn
            newly_applied_req_map[req.name] = req

        # finally, find the accompanied apply registry for the package
        # definitions
        advice_apply_registry_key = (
            self.registry_name + CALMJS_TOOLCHAIN_ADVICE_APPLY_SUFFIX)
        advice_apply_registry = get_registry(advice_apply_registry_key)

        if not isinstance(advice_apply_registry, AdviceApplyRegistry):
            logger.warning(
                "registry key '%s' resulted in %r which is not a valid advice "
                "apply registry; no package level advice apply steps will be "
                "applied", advice_apply_registry_key, advice_apply_registry
            )
            return

        # combine the newly applied ones with existing ones.
        applied_req_map.update(newly_applied_req_map)

        for pkg_name in spec.get(SOURCE_PACKAGE_NAMES, []):
            requirements = advice_apply_registry.get_record(pkg_name)
            if not requirements:
                continue
            logger.info(
                "source package '%s' specified %d advice package(s) to be "
                "applied", pkg_name, len(requirements)
            )

            for req in requirements:
                if req.name in applied_req_map:
                    logger.debug(
                        "skipping specified advice package '%s' as '%s' was "
                        "already applied", req, applied_req_map[req.name]
                    )
                    continue
                logger.debug("apply advice package '%s'", req)
                self._process_toolchain_spec_requirement(toolchain, spec, req)
                applied_req_map[req.name] = req

    def process_toolchain_spec_package(self, toolchain, spec, value):
        # the original one-shot method.
        try:
            req = self._to_requirement(value)
        except ValueError:
            pass
        else:
            return self._process_toolchain_spec_requirement(
                toolchain, spec, req)

    def _process_toolchain_spec_requirement(self, toolchain, spec, req):
        if not isinstance(toolchain, Toolchain):
            logger.debug(
                'apply_toolchain_spec or process_toolchain_spec_package '
                'must be invoked with a toolchain instance, not %s', toolchain,
            )
            return

        pkg_name = req.project_name
        toolchain_cls = type(toolchain)
        toolchain_advices = self.get_record(pkg_name)

        if toolchain_advices is None and not default_working_set.find(req):
            logger.warning(
                "advice setup steps required from package/requirement "
                "'%s', however it is not found or not installed in this "
                "environment; build may continue; if there are errors or "
                "unexpected behavior that occur, it may be corrected by "
                "providing the missing requirement into this environment "
                "by installing the relevant package", req
            )
            return
        elif not toolchain_advices:
            logger.debug(
                "no advice setup steps registered for package/requirement "
                "'%s'", req)
            return

        logger.debug(
            "found advice setup steps registered for package/requirement "
            "'%s'; checking for compatibility with toolchain '%s'",
            req, cls_to_name(toolchain_cls)
        )

        entry_points = [
            toolchain_advices.get(cls_name) for cls_name in (
                cls_to_name(cls) for cls in toolchain_cls.__mro__
                if issubclass(cls, Toolchain)
            ) if cls_name in toolchain_advices
        ]

        if not entry_points:
            logger.debug("no compatible advice setup steps found")

        for entry_point in entry_points:
            try:
                f = entry_point.load()
            except ImportError:
                logger.error(
                    "ImportError: entry_point '%s' in group '%s' while "
                    "processing toolchain spec advice setup step "
                    "registered under advice package '%s'",
                    entry_point, self.registry_name, req
                )
                continue

            try:
                f(spec, sorted(req.extras))
            except Exception:
                logger.exception(
                    "failure encountered while setting up advices through "
                    "entry_point '%s' in group '%s' "
                    "registered under advice package '%s'",
                    entry_point, self.registry_name, req
                )
            else:
                logger.debug(
                    "entry_point '%s' registered by advice package '%s' "
                    "applied as an advice setup step by %s '%s'",
                    entry_point, req,
                    cls_to_name(type(self)), self.registry_name,
                )

        # will just simply be applied regardless.
        spec.setdefault(ADVICE_PACKAGES_APPLIED_REQUIREMENTS, [])
        spec[ADVICE_PACKAGES_APPLIED_REQUIREMENTS].append(req)


class AdviceApplyRegistry(BaseRegistry):
    """
    Registry to automatically set up the the list of ADVICE_PACKAGES for
    a given Toolchain execution.  If a package has entries declared in
    this registry, the default Toolchain will apply those declarations
    onto the list of ADVICE_PACKAGES whenever it appears as a member of
    SOURCE_PACKAGE_NAMES.  For example (continuing on from the example
    in AdviceRegistry), if 'example.demo' declares the following:

        [calmjs.toolchain.advice.apply]
        example.demo = example.package[extra3,extra4]

    Whenever 'example.demo' appears as an entry in SOURCE_PACKAGE_NAMES
    in a spec, the following additional flags will be applied to the
    spec.

        {ADVICE_PACKAGES: ['example.package[extra1,extra2]']}

    Naturally, this would not be carried across dependents - if
    dependents also need that exact advice setup applied, it needs to
    also declare the same entry in this registry.  Also, in order for
    the implementation to function as expected, the standard Toolchain
    must be used, and the relevant functionality should be invoked and
    not be overridden.

    Note that the key is ignored under the current implementation.
    """

    def _init(self):
        # since the record keys are package names
        self.records = PackageKeyMapping()
        for entry_point in self.raw_entry_points:
            self._init_entry_point(entry_point)

    def _init_entry_point(self, entry_point):
        if not entry_point.dist:
            logger.warning(
                'entry_points passed to %s for registration must provide a '
                'distribution with a project name; registration of %s skipped',
                cls_to_name(type(self)), entry_point,
            )
            return
        key = entry_point.dist.project_name
        self.records.setdefault(key, [])
        # have to cast the entry point into
        try:
            requirement = Requirement.parse(str(entry_point).split('=', 1)[1])
        except ValueError as e:
            logger.warning(
                "entry_point '%s' cannot be registered to %s due to the "
                "following error: %s",
                entry_point, cls_to_name(type(self)), e
            )
        else:
            self.records[key].append(requirement)

    def get_record(self, name):
        return self.records.get(name)


class Toolchain(BaseDriver):
    """
    For shared methods between all toolchains.

    The objective of this class is to provide a consistent interface
    from calmjs to the various cli Node.js tools, this class inherits
    from the BaseDriver class.  This means having the same foundation
    and also the ability to reuse a number of useful utility methods
    for talking to those scripts and binaries.

    This also involves some standardized processes within the calmjs
    framework, naming the definition of the following items that every
    subclass and implementation must support.

    BUILD_DIR
        The build directory.  This can be manually specified, or be a
        temporary directory automatically created and destroyed.
    CALMJS_MODULE_REGISTRY_NAMES
        For recording the list of calmjs modules it has used, so other
        parts of the framework can make use of this, such as inferring
        which test modules it should use.
    EXPORT_TARGET
        A path on the filesystem that this toolchain will ultimately
        generate its output to.
    EXPORT_TARGET_OVERWRITE
        Signifies that the export target can be safely overwritten.
    WORKING_DIR
        The working directory where the relative paths will be based
        from.
    """

    # subclasses may assign an identifier or instance of a compatible
    # loaderplugin registry for use with the encapsulated framework.
    loaderplugin_registry = None

    def __init__(self, *a, **kw):
        """
        Refer to parent for exact arguments.
        """

        super(Toolchain, self).__init__(*a, **kw)
        self.opener = _opener
        self.setup_filename_suffix()
        self.setup_transpiler()
        self.setup_prefix_suffix()
        self.setup_compile_entries()

    # Helpers

    def realpath(self, spec, key):
        """
        Resolve and update the path key in the spec with its realpath,
        based on the working directory.
        """

        if key not in spec:
            # do nothing for now
            return

        if not spec[key]:
            logger.warning(
                "cannot resolve realpath of '%s' as it is not defined", key)
            return

        check = realpath(join(spec.get(WORKING_DIR, ''), spec[key]))
        if check != spec[key]:
            spec[key] = check
            logger.warning(
                "realpath of '%s' resolved to '%s', spec is updated",
                key, check
            )
        return check

    # Setup related methods

    def setup_filename_suffix(self):
        """
        Set up the filename suffix for the sources and targets.
        """

        self.filename_suffix = '.js'

    def setup_transpiler(self):
        """
        Subclasses will need to implement this to setup the transpiler
        attribute, which the compile method will invoke.
        """

        self.parser = NotImplemented
        self.transpiler = NotImplemented

    def setup_prefix_suffix(self):
        """
        Set up the compile prefix, sourcepath and the targetpath suffix
        attributes, which are the prefix to the function name and the
        suffixes to retrieve the values from for creating the generator
        function.
        """

        self.compile_prefix = 'compile_'
        self.sourcepath_suffix = '_sourcepath'
        self.modpath_suffix = '_modpaths'
        self.targetpath_suffix = '_targetpaths'

    # TODO BBB backward compat fixes

    @property
    def sourcemap_suffix(self):
        _deprecation_warning(
            'sourcemap_suffix has been renamed to sourcepath_suffix; '
            'Toolchain attribute will be removed by calmjs-4.0.0',
        )
        return self.sourcepath_suffix

    @sourcemap_suffix.setter
    def sourcemap_suffix(self, value):
        _deprecation_warning(
            'sourcemap_suffix has been renamed to sourcepath_suffix; '
            'Toolchain attribute will be removed by calmjs-4.0.0',
        )
        self.sourcepath_suffix = value

    @property
    def target_suffix(self):
        _deprecation_warning(
            'target_suffix has been renamed to targetpath_suffix; '
            'Toolchain attribute will be removed by calmjs-4.0.0'
        )
        return self.targetpath_suffix

    @target_suffix.setter
    def target_suffix(self, value):
        _deprecation_warning(
            'target_suffix has been renamed to targetpath_suffix; '
            'Toolchain attribute will be removed by calmjs-4.0.0'
        )
        self.targetpath_suffix = value

    def setup_compile_entries(self):
        """
        The method that sets up the map that maps the compile methods
        stored in this class instance to the spec key that the generated
        maps should be stored at.
        """

        self.compile_entries = self.build_compile_entries()

    def build_compile_entries(self):
        """
        Build the entries that will be used to acquire the methods for
        the compile step.

        This is to be a list of 3-tuples.

        first element being the method name, which is a name that will
        be prefixed with the compile_prefix, default being `compile_`;
        alternatively a callable could be provided.  This method must
        return a 2-tuple.

        second element being the read key for the sourcepath dict, which
        is the name to be read from the spec and it will be suffixed
        with the sourcepath_suffix, default being `_sourcepath`.

        third element being the write key for first return value of the
        method, it will be suffixed with the modpath_suffix, defaults to
        `_modpaths`, and the targetpath_suffix, default to `_targetpaths`.

        The method referenced SHOULD NOT assign values to the spec, and
        it must produce and return a 2-tuple:

        first element should be the map from the module to the written
        targets, the key being the module name (modname) and the value
        being the relative path of the final file to the build_dir

        the second element must be a list of module names that it
        exported.
        """

        return (
            # compile_*, *_sourcepath, (*_modpaths, *_targetpaths)
            ToolchainSpecCompileEntry('transpile', 'transpile', 'transpiled'),
            ToolchainSpecCompileEntry('bundle', 'bundle', 'bundled'),
        )

    # Default built-in methods referenced by methods that will be
    # executed, as constructed by build_compile_entries.

    # Following are used for the transpile and bundle compile processes.

    def _validate_build_target(self, spec, target):
        """
        Essentially validate that the target is inside the build_dir.
        """

        if not realpath(target).startswith(spec[BUILD_DIR]):
            raise ValueError('build_target %s is outside build_dir' % target)

    # note that in the following methods, a shorthand notation is used
    # for some of the arguments: nearly all occurrences of source means
    # sourcepath, and target means targetpath.

    def _generate_transpile_target(self, spec, target):
        # ensure that the target is fully normalized.
        bd_target = join(spec[BUILD_DIR], normpath(target))
        self._validate_build_target(spec, bd_target)
        if not exists(dirname(bd_target)):
            logger.debug("creating dir '%s'", dirname(bd_target))
            makedirs(dirname(bd_target))

        return bd_target

    def transpile_modname_source_target(self, spec, modname, source, target):
        """
        The function that gets called by compile_transpile_entry for
        processing the provided JavaScript source file provided by some
        Python package through the transpiler instance.
        """

        if not isinstance(self.transpiler, BaseUnparser):
            _deprecation_warning(
                'transpiler callable assigned to %r must be an instance of '
                'calmjs.parse.unparsers.base.BaseUnparser by calmjs-4.0.0; '
                'if the original transpile behavior is to be retained, the '
                'subclass may instead override this method to call '
                '`simple_transpile_modname_source_target` directly, as '
                'this fallback behavior will be removed by calmjs-4.0.0' % (
                    self,
                )
            )
            return self.simple_transpile_modname_source_target(
                spec, modname, source, target)

        # do the new thing here.
        return self._transpile_modname_source_target(
            spec, modname, source, target)

    def _transpile_modname_source_target(self, spec, modname, source, target):
        bd_target = self._generate_transpile_target(spec, target)
        logger.info('Transpiling %s to %s', source, bd_target)
        reader = partial_open(source, 'r')
        writer_main = partial_open(bd_target, 'w')
        writer_map = (
            partial_open(bd_target + '.map', 'w')
            if spec.get(GENERATE_SOURCE_MAP) else
            None
        )
        write(self.transpiler, [
            read(self.parser, reader)], writer_main, writer_map)

    def simple_transpile_modname_source_target(
            self, spec, modname, source, target):
        """
        The original simple transpile method called by compile_transpile
        on each target.
        """

        opener = self.opener
        bd_target = self._generate_transpile_target(spec, target)
        logger.info('Transpiling %s to %s', source, bd_target)
        with opener(source, 'r') as reader, opener(bd_target, 'w') as _writer:
            writer = SourceWriter(_writer)
            self.transpiler(spec, reader, writer)
            if writer.mappings and spec.get(GENERATE_SOURCE_MAP):
                source_map_path = bd_target + '.map'
                with open(source_map_path, 'w') as sm_fd:
                    self.dump(encode_sourcemap(
                        filename=bd_target,
                        mappings=writer.mappings,
                        sources=[source],
                    ), sm_fd)

                # just use basename
                source_map_url = basename(source_map_path)
                _writer.write('\n//# sourceMappingURL=')
                _writer.write(source_map_url)
                _writer.write('\n')

    def compile_transpile_entry(self, spec, entry):
        """
        Handler for each entry for the transpile method of the compile
        process.  This invokes the transpiler that was set up to
        transpile the input files into the build directory.
        """

        modname, source, target, modpath = entry
        transpiled_modpath = {modname: modpath}
        transpiled_target = {modname: target}
        export_module_name = [modname]
        self.transpile_modname_source_target(spec, modname, source, target)
        return transpiled_modpath, transpiled_target, export_module_name

    def compile_bundle_entry(self, spec, entry):
        """
        Handler for each entry for the bundle method of the compile
        process.  This copies the source file or directory into the
        build directory.
        """

        modname, source, target, modpath = entry
        bundled_modpath = {modname: modpath}
        bundled_target = {modname: target}
        export_module_name = []
        if isfile(source):
            export_module_name.append(modname)
            copy_target = join(spec[BUILD_DIR], target)
            if not exists(dirname(copy_target)):
                makedirs(dirname(copy_target))
            shutil.copy(source, copy_target)
        elif isdir(source):
            copy_target = join(spec[BUILD_DIR], modname)
            shutil.copytree(source, copy_target)

        return bundled_modpath, bundled_target, export_module_name

    def compile_loaderplugin_entry(self, spec, entry):
        """
        Generic loader plugin entry handler.

        The default implementation assumes that everything up to the
        first '!' symbol resolves to some known loader plugin within
        the registry.

        The registry instance responsible for the resolution of the
        loader plugin handlers must be available in the spec under
        CALMJS_LOADERPLUGIN_REGISTRY
        """

        modname, source, target, modpath = entry
        handler = spec[CALMJS_LOADERPLUGIN_REGISTRY].get(modname)
        if handler:
            return handler(self, spec, modname, source, target, modpath)
        logger.warning(
            "no loaderplugin handler found for plugin entry '%s'", modname)
        return {}, {}, []

    # The naming methods, which are needed by certain toolchains that
    # need to generate specific names to maintain compatibility.  The
    # intended use case for this set of methods is to provide a rigidly
    # defined name handling ruleset for a given implementation of a
    # toolchain, but for toolchains that have its own custom naming
    # schemes per whatever value combination, further handling can be
    # done within each of the compile_* and/or compile_*_entry methods
    # that are enabled or registered for use for that particular
    # toolchain implementation.

    # Also note that 'source' and 'target' refer to 'sourcepath' and
    # 'targetpath' respectively in argument and method names.

    def modname_source_to_modname(self, spec, modname, source):
        """
        Method to get a modname.  Should really return the modname, but
        subclass has the option to override this.

        Called by generator method `_gen_modname_source_target_modpath`.
        """

        return modname

    def modname_source_to_source(self, spec, modname, source):
        """
        Method to get a source file name.  Should really return itself,
        but subclass has the option to override this.

        Called by generator method `_gen_modname_source_target_modpath`.
        """

        return source

    def modname_source_to_target(self, spec, modname, source):
        """
        Create a target file name from the input module name and its
        source file name.  The result should be a path relative to the
        build_dir, and this is derived directly from the modname with NO
        implicit convers of path separators (i.e. '/' or any other) into
        a system or OS specific form (e.g. '\\').  The rationale for
        this choice is that there exists Node.js/JavaScript tools that
        handle this internally and/or these paths and values are
        directly exposed on the web and thus these separators must be
        preserved.

        If the specific implementation requires this to be done,
        implementations may override by wrapping the result of this
        using os.path.normpath.  For the generation of transpile write
        targets, this will be done in _generate_transpile_target.

        Default is to append the module name with the filename_suffix
        assigned to this instance (setup by setup_filename_suffix), iff
        the provided source also end with this filename suffix.

        However, certain tools have issues dealing with loader plugin
        syntaxes showing up on the filesystem (and certain filesystems
        definitely do not like some of the characters), so the usage of
        the loaderplugin registry assigned to the spec may be used for
        lookup if available.

        Called by generator method `_gen_modname_source_target_modpath`.
        """

        loaderplugin_registry = spec.get(CALMJS_LOADERPLUGIN_REGISTRY)
        if '!' in modname and loaderplugin_registry:
            handler = loaderplugin_registry.get(modname)
            if handler:
                return handler.modname_source_to_target(
                    self, spec, modname, source)

        if (source.endswith(self.filename_suffix) and
                not modname.endswith(self.filename_suffix)):
            return modname + self.filename_suffix
        else:
            # assume that modname IS the filename
            return modname

    def modname_source_target_to_modpath(self, spec, modname, source, target):
        """
        Typical JavaScript tools will get confused if '.js' is added, so
        by default the same modname is returned as path rather than the
        target file for the module path to be written to the output file
        for linkage by tools.  Some other tools may desire the target to
        be returned instead, or construct some other string that is more
        suitable for the tool that will do the assemble and link step.

        The modname and source argument provided to aid pedantic tools,
        but really though this provides more consistency to method
        signatures.

        Called by generator method `_gen_modname_source_target_modpath`.
        """

        return modname

    def modname_source_target_modnamesource_to_modpath(
            self, spec, modname, source, target, modname_source):
        """
        Typical JavaScript tools will get confused if '.js' is added, so
        by default the same modname is returned as path rather than the
        target file for the module path to be written to the output file
        for linkage by tools.  Some other tools may desire the target to
        be returned instead, or construct some other string that is more
        suitable for the tool that will do the assemble and link step.

        The modname and source argument provided to aid pedantic tools,
        but really though this provides more consistency to method
        signatures.

        Same as `self.modname_source_target_to_modpath`, but includes
        the original raw key-value as a 2-tuple.

        Called by generator method `_gen_modname_source_target_modpath`.
        """

        return self.modname_source_target_to_modpath(
            spec, modname, source, target)

    # Generator methods

    def _gen_modname_source_target_modpath(self, spec, d):
        """
        Private generator that will consume those above functions.  This
        should NOT be overridden.

        Produces the following 4-tuple on iteration with the input dict;
        the definition is written at the module level documention for
        calmjs.toolchain, but in brief:

        modname
            The JavaScript module name.
        source
            Stands for sourcepath - path to some JavaScript source file.
        target
            Stands for targetpath - the target path relative to
            spec[BUILD_DIR] where the source file will be written to
            using the method that genearted this entry.
        modpath
            The module path that is compatible with tool referencing
            the target.  While this is typically identical with modname,
            some tools require certain modifications or markers in
            additional to what is presented (e.g. such as the addition
            of a '?' symbol to ensure absolute lookup).
        """

        for modname_source in d.items():
            try:
                modname = self.modname_source_to_modname(spec, *modname_source)
                source = self.modname_source_to_source(spec, *modname_source)
                target = self.modname_source_to_target(spec, *modname_source)
                modpath = self.modname_source_target_modnamesource_to_modpath(
                    spec, modname, source, target, modname_source)
            except ValueError as e:
                # figure out which of the above 3 functions failed by
                # acquiring the name from one frame down.
                f_name = sys.exc_info()[2].tb_next.tb_frame.f_code.co_name

                if isinstance(e, ValueSkip):
                    # a purposely benign failure.
                    log = partial(
                        logger.info,
                        "toolchain purposely skipping on '%s', "
                        "reason: %s, where modname='%s', source='%s'",
                    )
                else:
                    log = partial(
                        logger.warning,
                        "toolchain failed to acquire name with '%s', "
                        "reason: %s, where modname='%s', source='%s'; "
                        "skipping",
                    )

                log(f_name, e, *modname_source)
                continue
            yield modname, source, target, modpath

    # The core functions to be implemented for the toolchain.

    def prepare(self, spec):
        """
        Optional preparation step for handling the spec.

        Implementation can make use of this to do pre-compilation
        checking and/or other validation steps in order to result in a
        successful compilation run.
        """

    def compile(self, spec):
        """
        Generic step that compiles from a spec to build the specified
        things into the build directory `build_dir`, by gathering all
        the files and feed them through the transpilation process or by
        simple copying.
        """

        spec[EXPORT_MODULE_NAMES] = export_module_names = spec.get(
            EXPORT_MODULE_NAMES, [])
        if not isinstance(export_module_names, list):
            raise TypeError(
                "spec provided a '%s' but it is not of type list "
                "(got %r instead)" % (EXPORT_MODULE_NAMES, export_module_names)
            )

        def compile_entry(method, read_key, store_key):
            spec_read_key = read_key + self.sourcepath_suffix
            spec_modpath_key = store_key + self.modpath_suffix
            spec_target_key = store_key + self.targetpath_suffix

            if _check_key_exists(spec, [spec_modpath_key, spec_target_key]):
                logger.error(
                    "aborting compile step %r due to existing key", entry,
                )
                return

            sourcepath_dict = spec.get(spec_read_key, {})
            entries = self._gen_modname_source_target_modpath(
                spec, sourcepath_dict)
            (spec[spec_modpath_key], spec[spec_target_key],
                new_module_names) = method(spec, entries)
            logger.debug(
                "entry %r "
                "wrote %d entries to spec[%r], "
                "wrote %d entries to spec[%r], "
                "added %d export_module_names",
                entry,
                len(spec[spec_modpath_key]), spec_modpath_key,
                len(spec[spec_target_key]), spec_target_key,
                len(new_module_names),
            )
            export_module_names.extend(new_module_names)

        for entry in self.compile_entries:
            if isinstance(entry, ToolchainSpecCompileEntry):
                log = partial(
                    logging.getLogger(entry.logger).log,
                    entry.log_level,
                    (
                        entry.store_key + "%s['%s'] is being rewritten from "
                        "'%s' to '%s'; configuration may now be invalid"
                    ),
                ) if entry.logger else None
                compile_entry(partial(
                    toolchain_spec_compile_entries, self,
                    process_name=entry.process_name,
                    overwrite_log=log,
                ), entry.read_key, entry.store_key)
                continue

            m, read_key, store_key = entry
            if callable(m):
                method = m
            else:
                method = getattr(self, self.compile_prefix + m, None)
                if not callable(method):
                    logger.error(
                        "'%s' not a callable attribute for %r from "
                        "compile_entries entry %r; skipping", m, self, entry
                    )
                    continue

            compile_entry(method, read_key, store_key)

    def assemble(self, spec):
        """
        Assemble all the compiled files.

        This was intended to be the function that provides the
        aggregation of all compiled files in the build directory into a
        form that can then be linked.  Typically this is for the
        generation of an actual specification or instruction file that
        will be passed to the linker, which is some binary that is
        installed on the system.
        """

        raise NotImplementedError

    def link(self, spec):
        """
        Should pass in the manifest path to the final JS linker, which
        is typically the bundler.
        """

        raise NotImplementedError

    def finalize(self, spec):
        """
        Optional finalizing step, where further usage of the build_dir,
        scripts and/or results are needed.  This can be used to run some
        specific scripts through node's import system directly on the
        pre-linked assembled files, for instance.

        This step is optional.
        """

    def _calf(self, spec):
        """
        The main call, assuming the base spec is prepared.

        Also, no advices will be triggered.
        """

        self.prepare(spec)
        self.compile(spec)
        self.assemble(spec)
        self.link(spec)
        self.finalize(spec)

    def setup_apply_advice_packages(
            self, spec, default_advice_registry=CALMJS_TOOLCHAIN_ADVICE):
        """
        This method sets up the advices that have been specified in the
        ADVICE_PACKAGES key, and apply the advices to the spec.
        """

        advice_registry_key = spec.get(
            CALMJS_TOOLCHAIN_ADVICE_REGISTRY, default_advice_registry)
        advice_registry = get_registry(advice_registry_key)
        if not isinstance(advice_registry, AdviceRegistry):
            logger.warning(
                "registry key '%s' resulted in %r which is not a valid advice "
                "registry; all package advice steps will be skipped",
                advice_registry_key, advice_registry
            )
            return
        logger.debug(
            "setting up advices using %s '%s'",
            cls_to_name(type(advice_registry)), advice_registry_key
        )
        advice_registry.apply_toolchain_spec(self, spec)

    def calf(self, spec):
        """
        Typical safe usage is this, which sets everything that could be
        problematic up.

        Requires the filename which everything will be produced to.
        """

        if not isinstance(spec, Spec):
            raise TypeError('spec must be of type Spec')

        # The following ensure steps really should be formalised into
        # some form of setup.  This may be a version 4+ item to consider
        # for integration, where the current SETUP advice is changed to
        # BEFORE_SETUP and have the following ensure step be part of the
        # default setup.

        # ensure build directory is defined and sane.
        if not spec.get(BUILD_DIR):
            tempdir = realpath(mkdtemp())
            spec.advise(CLEANUP, shutil.rmtree, tempdir)
            build_dir = join(tempdir, 'build')
            mkdir(build_dir)
            spec[BUILD_DIR] = build_dir
        else:
            build_dir = self.realpath(spec, BUILD_DIR)
            if not isdir(build_dir):
                logger.error("build_dir '%s' is not a directory", build_dir)
                raise_os_error(errno.ENOTDIR, build_dir)

        # ensure export target is sane
        self.realpath(spec, EXPORT_TARGET)

        # ensure advices specific to packages are applied, and applied
        # using the advice to maintain the feature as it was when
        # initially implemented as part of the runtime.  This also allow
        # advice setup exceptions be handled as expected.
        spec.advise(SETUP, self.setup_apply_advice_packages, spec)

        try:
            # Finally, handle setup which may set up the deferred
            # advices, as all the toolchain (and its runtime and/or its
            # parent runtime and related toolchains) spec advises should
            # have been done.
            spec.handle(SETUP)

            process = ('prepare', 'compile', 'assemble', 'link', 'finalize')
            for p in process:
                spec.handle('before_' + p)
                getattr(self, p)(spec)
                spec.handle('after_' + p)
            spec.handle(SUCCESS)
        except ToolchainCancel:
            # quietly handle the issue and move on out of here.
            pass
        finally:
            spec.handle(CLEANUP)

    def __call__(self, spec):
        """
        Alias, also make this callable directly.
        """

        self.calf(spec)


class NullToolchain(Toolchain):
    """
    A null toolchain that does nothing except maybe move some files
    around.
    """

    def __init__(self):
        super(NullToolchain, self).__init__()

    def setup_transpiler(self):
        self.transpiler = null_transpiler

    def transpile_modname_source_target(self, spec, modname, source, target):
        """
        Calls the original version.
        """

        return self.simple_transpile_modname_source_target(
            spec, modname, source, target)

    def prepare(self, spec):
        """
        Does absolutely nothing
        """

        spec['prepare'] = 'prepared'

    def assemble(self, spec):
        """
        Does absolutely nothing
        """

        spec['assemble'] = 'assembled'

    def link(self, spec):
        """
        Does absolutely nothing
        """

        spec['link'] = 'linked'


class ES5Toolchain(Toolchain):
    """
    A null toolchain that does nothing except maybe move some files
    around, using the es5 Unparser, pretty printer version.
    """

    def __init__(self, *a, **kw):
        super(ES5Toolchain, self).__init__(*a, **kw)

    def setup_transpiler(self):
        self.transpiler = pretty_printer()
        self.parser = parse
