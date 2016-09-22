# -*- coding: utf-8 -*-
"""
This provides a JavaScript "toolchain".

When I have a hammer every problem starts to look like JavaScript.

Honestly, it's a bit easier to deal with JavaScript when one treats that
as a compilation target.

How this supposed to work?

1) Write raw JS code without any UMD wrappers, but treat everything in
the file as UMD.  Remember to import everything needed using ``require``
and declare the exported things by assigning it to ``exports``.
2) Leave that file somewhere in the src directory, along with Python
code.
3) Run compile.  They will be compiled into the corresponding thing that
correlates to the Pythonic namespace identifiers.

At least this is the idea, have to see whether this idea actually end up
being sane (it won't be sane, when the entire thing was insane to begin
with).

One final thing: es6 does have modules, imports and exports done in a
different but dedicated syntax.  Though to really support them a proper
es6 compatible environment will be needed, however those are not a norm
at the moment yet, especially given the fact that browsers do not have
support for them quite just yet as of mid 2016.
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


def _opener(*a):
    return codecs.open(*a, encoding='utf-8')


def null_transpiler(spec, reader, writer):
    writer.write(reader.read())


class Spec(dict):

    def __init__(self, *a, **kw):
        super(Spec, self).__init__(*a, **kw)
        self._callbacks = {}

    def update_selected(self, other, selected):
        self.update({k: other[k] for k in selected})

    def add_callback(self, name, f, *a, **kw):
        self._callbacks[name] = self._callbacks.get(name, [])
        self._callbacks[name].append((f, a, kw))

    def do_callbacks(self, name):
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

    filename_suffix = '.js'

    def __init__(self, *a, **kw):
        """
        Refer to parent for exact arguments.
        """

        super(Toolchain, self).__init__(*a, **kw)
        self.opener = _opener
        self.setup_transpiler()

    def setup_transpiler(self):
        """
        Subclasses will need to implement this to setup the transpiler
        attribute, which the compile method will invoke.
        """

        self.transpiler = NotImplemented

    def _validate_build_target(self, spec, target):
        if not realpath(target).startswith(spec['build_dir']):
            raise ValueError('build_target %s is outside build_dir' % target)

    def transpile_modname_source_target(self, spec, modname, source, target):
        bd_target = join(spec['build_dir'], target)
        self._validate_build_target(spec, bd_target)
        logger.info('Transpiling %s to %s', source, bd_target)
        if not exists(dirname(bd_target)):
            makedirs(dirname(bd_target))
        opener = self.opener
        with opener(source, 'r') as reader, opener(bd_target, 'w') as writer:
            self.transpiler(spec, reader, writer)

    def modname_source_to_modname(self, spec, modname, source):
        """
        Subclass has the option to override this
        """

        return modname

    def modname_source_to_source(self, spec, modname, source):
        """
        Subclass has the option to override this
        """

        return source

    def modname_source_to_target(self, spec, modname, source):
        """
        Create a target file name from the input module name and its
        source file name.

        Default is to append the module name with the filename_suffix
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
        Same as above, but includes the original raw key-value as a
        2-tuple.
        """

        return self.modname_source_target_to_modpath(
            spec, modname, source, target)

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
                        "toolchain purposely skipping on '%s' where "
                        "modname='%s', source='%s'",
                    )
                else:
                    log = partial(
                        logger.warning,
                        "toolchain failed to acquire name with '%s' where "
                        "modname='%s', source='%s'; skipping",
                    )

                log(f_name, *modname_source)
                continue
            yield modname, source, target, modpath

    def prepare(self, spec):
        """
        Optional preparation step.

        Implementation can make use of this to do pre-compilation
        checking and/or other validation steps in order to result in a
        successful compilation run.
        """

    def compile_transpile_all(self, spec):
        transpile_source_map = spec.get('transpile_source_map', {})
        # Contains a mapping of the module name to the compiled file's
        # relative path starting from the base build_dir.
        transpiled_paths = {}
        # List of exported module names, should be equal to all keys of
        # the compiled and bundled sources.
        module_names = []

        itr = self._gen_modname_source_target_modpath(
            spec, transpile_source_map)
        for modname, source, target, modpath in itr:
            transpiled_paths[modname] = modpath
            module_names.append(modname)
            self.transpile_modname_source_target(spec, modname, source, target)

        return transpiled_paths, module_names

    def compile_bundle_all(self, spec):
        bundle_source_map = spec.get('bundle_source_map', {})
        # Contains a mapping of the bundled name to the bundled file's
        # relative path starting from the base build_dir.
        bundled_paths = {}
        # List of exported module names, should be equal to all keys of
        # the compiled and bundled sources.
        module_names = []

        itr = self._gen_modname_source_target_modpath(spec, bundle_source_map)
        for modname, source, target, modpath in itr:
            bundled_paths[modname] = modpath
            if isfile(source):
                module_names.append(modname)
                copy_target = join(spec['build_dir'], target)
                shutil.copy(source, copy_target)
            elif isdir(source):
                copy_target = join(spec['build_dir'], modname)
                shutil.copytree(source, copy_target)

        return bundled_paths, module_names

    def compile(self, spec):
        """
        Generic step that compiles from a spec to build the specified
        things into the build directory `build_dir`, by gathering all
        the files and feed them through the transpilation process or by
        simple copying.
        """

        transpiled_paths, transpiled_module_names = self.compile_transpile_all(
            spec)
        bundled_paths, bundled_module_names = self.compile_bundle_all(spec)
        module_names = transpiled_module_names + bundled_module_names
        spec.update_selected(locals(), [
            'transpiled_paths', 'bundled_paths', 'module_names'])

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
        The main call, assuming everything is prepared.
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
