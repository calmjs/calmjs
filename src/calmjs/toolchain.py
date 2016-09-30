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
"""

from __future__ import absolute_import
from __future__ import unicode_literals

import codecs
import errno
import logging
import shutil
import sys
from functools import partial
from os import mkdir
from os import makedirs
from os.path import join
from os.path import dirname
from os.path import exists
from os.path import isfile
from os.path import isdir
from os.path import realpath
from tempfile import mkdtemp

from calmjs.base import BaseDriver
from calmjs.exc import ValueSkip
from calmjs.utils import raise_os_error

logger = logging.getLogger(__name__)

__all__ = ['Spec', 'Toolchain', 'null_transpiler']


def _opener(*a):
    return codecs.open(*a, encoding='utf-8')


def null_transpiler(spec, reader, writer):
    writer.write(reader.read())


class Spec(dict):
    """
    Instances of these will track the progress through a Toolchain
    instance.
    """

    def __init__(self, *a, **kw):
        super(Spec, self).__init__(*a, **kw)
        self._callbacks = {}

    def update_selected(self, other, selected):
        """
        Like update, however a list of selected keys must be provided.
        """

        self.update({k: other[k] for k in selected})

    def add_callback(self, name, f, *a, **kw):
        """
        Add a callback that can be called by do_callbacks.

        Arguments:

        name
            The name of the callback group
        f
            A callable method or function.

        The rest of the arguments will be passed as arguments and
        keyword arguments to f when it's invoked.
        """

        self._callbacks[name] = self._callbacks.get(name, [])
        self._callbacks[name].append((f, a, kw))

    def do_callbacks(self, name):
        """
        Do all the callbacks

        Arguments:

        name
            The name of the callback group.  All the callables
            registered to this group will be invoked, last-in-first-out
            style.
        """

        callbacks = self._callbacks.get(name, [])
        while callbacks:
            try:
                # cleanup basically done lifo (last in first out)
                values = callbacks.pop()
                callback, a, kw = values
                if not ((callable(callback)) and
                        isinstance(a, tuple) and
                        isinstance(kw, dict)):
                    raise TypeError
            except ValueError:
                logger.info('Spec callback extraction error: got %s', values)
            except TypeError:
                logger.info('Spec malformed: got %s', values)
            else:
                try:
                    callback(*a, **kw)
                except Exception:
                    logger.exception('Spec callback execution: got %s', values)


class Toolchain(BaseDriver):
    """
    For shared methods between all toolchains.

    The objective of this class is to provide a consistent interface
    from calmjs to the various cli Node.js tools, this class inherits
    from the BaseDriver class.  This means having the same foundation
    and also the ability to reuse a number of useful utility methods
    for talking to those scripts and binaries.
    """

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
        self.callback_keys = []

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

        self.transpiler = NotImplemented

    def setup_prefix_suffix(self):
        """
        Set up the compile prefix and the source suffix attribute, which
        are the prefix to the function name and the suffix to retrieve
        the values from for creating the generator function.
        """

        self.compile_prefix = 'compile_'
        self.sourcemap_suffix = '_source_map'
        self.path_suffix = '_paths'

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

        second element being the read key for the source map, which is
        the name to be read from the spec and it will be suffixed with
        the sourcemap_suffix, default being `_source_map`.

        third element being the write key for first return value of the
        method, it will be suffixed with the path_suffix, defaults to
        `_paths`.

        The method referenced SHOULD NOT assign values to the spec, and
        it must produce and return a 2-tuple:

        first element should be the map from the module to the written
        targets, the key being the module name (modname) and the value
        being the relative path of the final file to the build_dir

        the second element must be a list of module names that it
        exported.
        """

        return (
            # compile_*, *_source_map, *_paths
            ('transpile', 'transpile', 'transpiled'),
            ('bundle', 'bundle', 'bundled'),
        )

    # Default built-in methods referenced by build_compile_entries;
    # these are for the transpile and bundle processes.

    def _validate_build_target(self, spec, target):
        """
        Essentially validate that the target is inside the build_dir.
        """

        if not realpath(target).startswith(spec['build_dir']):
            raise ValueError('build_target %s is outside build_dir' % target)

    def transpile_modname_source_target(self, spec, modname, source, target):
        """
        The function that gets called by
        """

        bd_target = join(spec['build_dir'], target)
        self._validate_build_target(spec, bd_target)
        logger.info('Transpiling %s to %s', source, bd_target)
        if not exists(dirname(bd_target)):
            makedirs(dirname(bd_target))
        opener = self.opener
        with opener(source, 'r') as reader, opener(bd_target, 'w') as writer:
            self.transpiler(spec, reader, writer)

    def compile_transpile(self, spec, entries):
        """
        The transpile method for the compile process.  This invokes the
        transpiler that was set up to transpile the input files into the
        build directory.
        """

        # Contains a mapping of the module name to the compiled file's
        # relative path starting from the base build_dir.
        transpiled_paths = {}
        # List of exported module names, should be equal to all keys of
        # the compiled and bundled sources.
        module_names = []

        for modname, source, target, modpath in entries:
            transpiled_paths[modname] = modpath
            module_names.append(modname)
            self.transpile_modname_source_target(spec, modname, source, target)

        return transpiled_paths, module_names

    def compile_bundle(self, spec, entries):
        """
        The transpile method for the bundle process.  This copies the
        source file or directory into the build directory.
        """

        # Contains a mapping of the bundled name to the bundled file's
        # relative path starting from the base build_dir.
        bundled_paths = {}
        # List of exported module names, should be equal to all keys of
        # the compiled and bundled sources.
        module_names = []

        for modname, source, target, modpath in entries:
            bundled_paths[modname] = modpath
            if isfile(source):
                module_names.append(modname)
                copy_target = join(spec['build_dir'], target)
                if not exists(dirname(copy_target)):
                    makedirs(dirname(copy_target))
                shutil.copy(source, copy_target)
            elif isdir(source):
                copy_target = join(spec['build_dir'], modname)
                shutil.copytree(source, copy_target)

        return bundled_paths, module_names

    # The naming methods, which are needed by certain toolchains that
    # need to generate specific names to maintain compatibility.  The
    # intended use case for this set of methods is to provide a rigidly
    # defined name handling ruleset for a given implementation of a
    # toolchain, but for toolchains that have its own custom naming
    # schemes per whatever value combination, further handling can be
    # done within each of the compile_* methods that are registered for
    # use for that particular toolchain.

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
        build_dir.

        Default is to append the module name with the filename_suffix
        assigned to this instance (setup by setup_filename_suffix).

        Called by generator method `_gen_modname_source_target_modpath`.
        """

        return modname + self.filename_suffix

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

        Produces the following 4-tuple on iteration with the input dict

        modname
            CommonJS require/import module name.
        source
            path to JavaScript source file from a Python package.
        target
            the target write path relative to build_dir
        modpath
            the module path that is compatible with tool referencing
            the target
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

        spec['module_names'] = module_names = spec.get('module_names', [])
        if not isinstance(module_names, list):
            raise TypeError(
                "spec provided a 'module_names' but it is not of type list "
                "(got %r instead)" % module_names
            )

        for entry in self.compile_entries:
            m, read_key, store_key = entry
            if callable(m):
                method_name = m.__name__
                method = m
            else:
                method_name = self.compile_prefix + m
                method = getattr(self, method_name, None)
                if not callable(method):
                    logger.error(
                        "'%s' not a callable attribute for %r from "
                        "compile_entries entry %r; skipping", m, self, entry
                    )
                    continue

            spec_read_key = read_key + self.sourcemap_suffix
            spec_write_key = store_key + self.path_suffix

            if spec_write_key in spec:
                logger.error(
                    "compile map entry %r attempting to write to to key '%s' "
                    "which already exists in spec; not overwriting, skipping",
                    entry, spec_write_key,
                )
                continue

            source_map = spec.get(spec_read_key, {})
            entries = self._gen_modname_source_target_modpath(spec, source_map)
            spec[spec_write_key], new_module_names = method(spec, entries)
            logger.debug(
                "entry %r wrote %d entries to spec[%r], added %d module_names",
                entry, len(spec[spec_write_key]), spec_write_key,
                len(new_module_names),
            )
            module_names.extend(new_module_names)

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
        """

        self.prepare(spec)
        self.compile(spec)
        self.assemble(spec)
        self.link(spec)
        self.finalize(spec)

    def calf(self, spec):
        """
        Typical safe usage is this, which sets everything that could be
        problematic up.

        Requires the filename which everything will be produced to.
        """

        if not isinstance(spec, Spec):
            raise TypeError('spec must be of type Spec')

        if not spec.get('build_dir'):
            tempdir = realpath(mkdtemp())
            spec.add_callback('cleanup', shutil.rmtree, tempdir)
            build_dir = join(tempdir, 'build')
            mkdir(build_dir)
            spec['build_dir'] = build_dir
        else:
            if not exists(spec['build_dir']):
                raise_os_error(errno.ENOTDIR)
            check = realpath(spec['build_dir'])
            if check != spec['build_dir']:
                spec['build_dir'] = check
                logger.warning(
                    "realpath of build_dir resolved to '%s', spec is updated",
                    check
                )

        try:
            self._calf(spec)
            spec.do_callbacks('success')
        finally:
            spec.do_callbacks('cleanup')

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
