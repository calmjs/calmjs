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
    modpaths are supported by most JavaScript/Node.js based import
    systems, its usage from within calmjs framework is discouraged.

source
    An absolute path on the local filesystem to the source file for a
    given modpath.  These two values (modpath and source) serves as the
    foundational mapping from a JavaScript module name to its
    corresponding source file.

target
    A relative path to a build_dir.  The relative path MUST not contain
    relative references.  A mapping from modpath to target is generated
    from a modpath to source mapping, where the source file has been
    somehow transformed into the target at the target location.  The
    relative path version (again, from build_dir) is typically recorded
    by instances of ``Spec`` objects that have undergone a ``Toolchain``
    run.

modpath
    Typically identical to modname, however the slight difference is
    that this is the transformed value that is to be better understood
    by the underlying tools.  Think of this as the post compiled value,
    or an alternative import location that is only applicable in the
    post-compiled context.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

import codecs
import errno
import logging
import shutil
import sys
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
from os.path import realpath
from tempfile import mkdtemp

from pkg_resources import Requirement

from calmjs.base import BaseDriver
from calmjs.base import BaseRegistry
from calmjs.exc import AdviceAbort
from calmjs.exc import AdviceCancel
from calmjs.exc import ValueSkip
from calmjs.exc import ToolchainAbort
from calmjs.exc import ToolchainCancel
from calmjs.utils import raise_os_error
from calmjs.vlqsm import SourceWriter
from calmjs.vlqsm import create_sourcemap

logger = logging.getLogger(__name__)

__all__ = [
    'AdviceRegistry', 'Spec', 'Toolchain', 'null_transpiler',

    'CALMJS_TOOLCHAIN_ADVICE',

    'SETUP', 'CLEANUP', 'SUCCESS',

    'AFTER_FINALIZE', 'BEFORE_FINALIZE', 'AFTER_LINK', 'BEFORE_LINK',
    'AFTER_ASSEMBLE', 'BEFORE_ASSEMBLE', 'AFTER_COMPILE', 'BEFORE_COMPILE',
    'AFTER_PREPARE', 'BEFORE_PREPARE', 'AFTER_TEST', 'BEFORE_TEST',

    'ADVICE_PACKAGES', 'ARTIFACT_PATHS', 'BUILD_DIR',
    'CALMJS_MODULE_REGISTRY_NAMES', 'CALMJS_TEST_REGISTRY_NAMES',
    'CONFIG_JS_FILES', 'DEBUG',
    'EXPORT_MODULE_NAMES', 'EXPORT_PACKAGE_NAMES',
    'EXPORT_TARGET', 'EXPORT_TARGET_OVERWRITE',
    'SOURCE_MODULE_NAMES', 'SOURCE_PACKAGE_NAMES',
    'TEST_MODULE_NAMES', 'TEST_MODULE_PATHS_MAP', 'TEST_PACKAGE_NAMES',
    'WORKING_DIR',
]

CALMJS_TOOLCHAIN_ADVICE = 'calmjs.toolchain.advice'

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
# listing of absolute locations on the file system where these bundled
# artifact files are.
ARTIFACT_PATHS = 'artifact_paths'
# build directory
BUILD_DIR = 'build_dir'
# source registries that have been used
CALMJS_MODULE_REGISTRY_NAMES = 'calmjs_module_registry_names'
CALMJS_TEST_REGISTRY_NAMES = 'calmjs_test_registry_names'
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
# mapping of test module to their paths; i.e. a source_map, but not
# labled as one to prevent naming conflicts (and they ARE to be
# standalone modules to be used directly by the toolchain and testing
# integration layer.
TEST_MODULE_PATHS_MAP = 'test_module_paths_map'
# name of test package
TEST_PACKAGE_NAMES = 'test_package_names'
# the working directory
WORKING_DIR = 'working_dir'


def _opener(*a):
    return codecs.open(*a, encoding='utf-8')


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


def null_transpiler(spec, reader, writer):
    writer.write(reader.read())


class Spec(dict):
    """
    Instances of these will track the progress through a Toolchain
    instance.
    """

    def __init__(self, *a, **kw):
        super(Spec, self).__init__(*a, **kw)
        self._advices = {}
        self._frames = {}
        self._called = set()

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
                # cleanup basically done lifo (last in first out)
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
                    logger.warning(
                        "advice %s in group '%s' raised an error "
                        "during its execution: %s; toolchain execution will "
                        "continue, however", advice, name, e
                    )
                    if self.get(DEBUG):
                        logger.warning(
                            'showing traceback for error', exc_info=1,
                        )
                except ToolchainCancel:
                    raise
                except ToolchainAbort as e:
                    logger.critical(
                        "an advice in group '%s' triggered an abort: %s",
                        name, str(e)
                    )
                    raise
                except KeyboardInterrupt:
                    raise ToolchainCancel('interrupted')
                except Exception:
                    logger.exception('Spec advice execution: got %s', values)


class AdviceRegistry(BaseRegistry):
    """
    Registry for package level optional setup for advices.

    These are specific to one given toolchain.
    """

    def _init(self):
        for entry_point in self.raw_entry_points:
            key = entry_point.dist.project_name
            records = self.records[key] = self.records.get(key, {})
            records[entry_point.name] = entry_point

    def get_record(self, name):
        return self.records.get(name)

    def _to_name(self, cls):
        return '%s:%s' % (cls.__module__, cls.__name__)

    def process_toolchain_spec_package(self, toolchain, spec, value):
        if not isinstance(toolchain, Toolchain):
            logger.debug(
                'must call process_toolchain_spec_package with a toolchain, '
                'not %s', toolchain,
            )
            return

        toolchain_cls = type(toolchain)
        req = Requirement.parse(value)
        pkg_name = req.project_name
        toolchain_advices = self.get_record(pkg_name)

        if not toolchain_advices:
            return

        logger.debug(
            "found advice setup steps registered for package '%s' for "
            "toolchain '%s'", value, self._to_name(toolchain_cls)
        )

        for cls in getattr(toolchain_cls, '__mro__'):
            # traverse the entire subclass for relevant registration.
            if not issubclass(cls, Toolchain):
                continue

            entry_point = toolchain_advices.get(self._to_name(cls))
            if entry_point:
                try:
                    f = entry_point.load()
                except ImportError:
                    logger.error(
                        "ImportError: entry_point '%s' in group '%s'",
                        entry_point, self.registry_name,
                    )
                    return None

                try:
                    f(spec, sorted(req.extras))
                except Exception:
                    logger.exception(
                        "failure encountered while setting up advices through "
                        "entry_point '%s' in group '%s'",
                        entry_point, self.registry_name,
                    )


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
        self.modpath_suffix = '_modpaths'
        self.target_suffix = '_targets'

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
        method, it will be suffixed with the modpath_suffix, defaults to
        `_modpaths`, and the target_suffix, default to `_targets`.

        The method referenced SHOULD NOT assign values to the spec, and
        it must produce and return a 2-tuple:

        first element should be the map from the module to the written
        targets, the key being the module name (modname) and the value
        being the relative path of the final file to the build_dir

        the second element must be a list of module names that it
        exported.
        """

        return (
            # compile_*, *_source_map, (*_modpaths, *_targets)
            ('transpile', 'transpile', 'transpiled'),
            ('bundle', 'bundle', 'bundled'),
        )

    # Default built-in methods referenced by build_compile_entries;
    # these are for the transpile and bundle processes.

    def _validate_build_target(self, spec, target):
        """
        Essentially validate that the target is inside the build_dir.
        """

        if not realpath(target).startswith(spec[BUILD_DIR]):
            raise ValueError('build_target %s is outside build_dir' % target)

    def transpile_modname_source_target(self, spec, modname, source, target):
        """
        The function that gets called by
        """

        bd_target = join(spec[BUILD_DIR], target)
        self._validate_build_target(spec, bd_target)
        logger.info('Transpiling %s to %s', source, bd_target)
        if not exists(dirname(bd_target)):
            makedirs(dirname(bd_target))
        opener = self.opener
        with opener(source, 'r') as reader, opener(bd_target, 'w') as _writer:
            writer = SourceWriter(_writer)
            self.transpiler(spec, reader, writer)
            if writer.mappings and spec.get(GENERATE_SOURCE_MAP):
                source_map_path = bd_target + '.map'
                with open(source_map_path, 'w') as sm_fd:
                    self.dump(create_sourcemap(
                        filename=bd_target,
                        mappings=writer.mappings,
                        sources=[source],
                    ), sm_fd)

                # just use basename
                source_map_url = basename(source_map_path)
                _writer.write('\n//# sourceMappingURL=')
                _writer.write(source_map_url)
                _writer.write('\n')

    def compile_transpile(self, spec, entries):
        """
        The transpile method for the compile process.  This invokes the
        transpiler that was set up to transpile the input files into the
        build directory.
        """

        # Contains a mapping of the module name to the compiled file's
        # relative path starting from the base build_dir.
        transpiled_modpaths = {}
        transpiled_targets = {}
        # List of exported module names, should be equal to all keys of
        # the compiled and bundled sources.
        export_module_names = []

        for modname, source, target, modpath in entries:
            transpiled_modpaths[modname] = modpath
            transpiled_targets[modname] = target
            export_module_names.append(modname)
            self.transpile_modname_source_target(spec, modname, source, target)

        return transpiled_modpaths, transpiled_targets, export_module_names

    def compile_bundle(self, spec, entries):
        """
        The transpile method for the bundle process.  This copies the
        source file or directory into the build directory.
        """

        # Contains a mapping of the bundled name to the bundled file's
        # relative path starting from the base build_dir.
        bundled_modpaths = {}
        bundled_targets = {}
        # List of exported module names, should be equal to all keys of
        # the compiled and bundled sources.
        export_module_names = []

        for modname, source, target, modpath in entries:
            bundled_modpaths[modname] = modpath
            bundled_targets[modname] = target
            if isfile(source):
                export_module_names.append(modname)
                copy_target = join(spec[BUILD_DIR], target)
                if not exists(dirname(copy_target)):
                    makedirs(dirname(copy_target))
                shutil.copy(source, copy_target)
            elif isdir(source):
                copy_target = join(spec[BUILD_DIR], modname)
                shutil.copytree(source, copy_target)

        return bundled_modpaths, bundled_targets, export_module_names

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
        assigned to this instance (setup by setup_filename_suffix), iff
        the provided source also end with this filename suffix.

        Called by generator method `_gen_modname_source_target_modpath`.
        """

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

        spec[EXPORT_MODULE_NAMES] = export_module_names = spec.get(
            EXPORT_MODULE_NAMES, [])
        if not isinstance(export_module_names, list):
            raise TypeError(
                "spec provided a '%s' but it is not of type list "
                "(got %r instead)" % (EXPORT_MODULE_NAMES, export_module_names)
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
            spec_modpath_key = store_key + self.modpath_suffix
            spec_target_key = store_key + self.target_suffix

            if _check_key_exists(spec, [spec_modpath_key, spec_target_key]):
                logger.error(
                    "aborting compile step %r due to existing key", entry,
                )
                continue

            source_map = spec.get(spec_read_key, {})
            entries = self._gen_modname_source_target_modpath(spec, source_map)
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

    def calf(self, spec):
        """
        Typical safe usage is this, which sets everything that could be
        problematic up.

        Requires the filename which everything will be produced to.
        """

        if not isinstance(spec, Spec):
            raise TypeError('spec must be of type Spec')

        if not spec.get(BUILD_DIR):
            tempdir = realpath(mkdtemp())
            spec.advise(CLEANUP, shutil.rmtree, tempdir)
            build_dir = join(tempdir, 'build')
            mkdir(build_dir)
            spec[BUILD_DIR] = build_dir
        else:
            if not exists(spec[BUILD_DIR]):
                raise_os_error(errno.ENOTDIR)
            check = realpath(spec[BUILD_DIR])
            if check != spec[BUILD_DIR]:
                spec[BUILD_DIR] = check
                logger.warning(
                    "realpath of build_dir resolved to '%s', spec is updated",
                    check
                )

        # Finally, handle setup which may set up the deferred advices,
        # as all the toolchain (and its runtime and/or its parent
        # runtime and related toolchains) spec advises should have been
        # done.
        spec.handle(SETUP)

        try:
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
