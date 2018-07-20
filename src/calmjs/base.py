# -*- coding: utf-8 -*-
"""
calmjs.base

This module contains various base classes from which other parts of this
framework will inherit/extend from.
"""

from __future__ import absolute_import
import os

import errno
import json
from os import getcwd
from os.path import dirname
from os.path import isdir
from os.path import join
from os.path import pathsep
from os.path import realpath
from os.path import sep

from collections import OrderedDict
from collections import MutableMapping
from logging import getLogger
from pkg_resources import Distribution
from pkg_resources import working_set
from pkg_resources import safe_name

from calmjs.utils import which
from calmjs.utils import finalize_env
from calmjs.utils import fork_exec
from calmjs.utils import raise_os_error

NODE_PATH = 'NODE_PATH'
NODE_MODULES = 'node_modules'
# the usual path to binary within node modules.
NODE_MODULES_BIN = '.bin'
NODE = 'node'

logger = getLogger(__name__)
_marker = object()


def _import_module(module_name):
    return __import__(module_name, fromlist=['__name__'], level=0)


def _check_isdir_assign_key(d, key, value, error_msg=None):
    if isdir(value):
        d[key] = value
    else:
        extra_info = '' if not error_msg else '; ' + error_msg
        logger.error(
            "not manually setting '%s' to '%s' as it not a directory%s",
            key, value, extra_info
        )


def _get_exec_binary(binary, kw):
    """
    On win32, the subprocess module can only reliably resolve the
    target binary if it's actually a binary; as for a Node.js script
    it seems to only work iff shell=True was specified, presenting
    a security risk.  Resolve the target manually through which will
    account for that.

    The kw argument is the keyword arguments that will be passed into
    whatever respective subprocess.Popen family of methods.  The PATH
    environment variable will be used if available.
    """

    binary = which(binary, path=kw.get('env', {}).get('PATH'))
    if binary is None:
        raise_os_error(errno.ENOENT)
    return binary


class PackageKeyMapping(MutableMapping):
    """
    A mapping where keys are pkg_resources.Distribution.project_names
    mapping to some value.  As project_names are stored, lookup using
    the de-normalized values must go through the safe_name normalization
    such that the resolution will work as expected.
    """

    def __init__(self, *a, **kw):
        self.__map = {}
        # calling self.update instead to use the defined methods that
        # will call normalize.
        self.update(*a, **kw)

    def normalize(self, key):
        return safe_name(key)

    def __getitem__(self, key):
        return self.__map[self.normalize(key)]

    def __setitem__(self, key, value):
        if isinstance(key, Distribution):
            self.__map[key.project_name] = value
        else:
            self.__map[self.normalize(key)] = value

    def __delitem__(self, key):
        self.__map.__delitem__(self.normalize(key))

    def __iter__(self):
        return iter(self.__map)

    def __len__(self):
        return len(self.__map)

    def __contains__(self, key):
        return self.normalize(key) in self.__map

    def __repr__(self):
        return repr(self.__map)


class BaseRegistry(object):
    """
    A base registry implementation that make use of ``pkg_resources``
    entry points for its definitions.
    """

    def __init__(self, registry_name, *a, **kw):
        """
        Arguments:

        registry_name
            The name of this registry.
        """

        # The container for the resolved item.
        self.records = OrderedDict()
        self.registry_name = registry_name
        _working_set = kw.pop('_working_set', working_set)
        self.raw_entry_points = [] if _working_set is None else list(
            _working_set.iter_entry_points(self.registry_name))
        self._init(*a, **kw)

    def _init(self, *a, **kw):
        """
        Subclasses can completely override this for its instantiation,
        or it can override this by having its subclass override
        _init_entry_point and then have this method call

            self._init_entry_points(self.raw_entry_points)

        to initialize all entry points during instantiation.
        """

    def _init_entry_points(self, entry_points):
        """
        Default initialization loop.
        """

        logger.debug(
            "registering %d entry points for registry '%s'",
            len(entry_points), self.registry_name,
        )
        for entry_point in entry_points:
            try:
                logger.debug(
                    "registering entry point '%s' from '%s'",
                    entry_point, entry_point.dist,
                )
                self._init_entry_point(entry_point)
            except ImportError:
                logger.warning(
                    'ImportError: %s not found; skipping registration',
                    entry_point.module_name)
            except Exception:
                logger.exception(
                    "registration of entry point '%s' from '%s' to registry "
                    "'%s' failed with the following exception",
                    entry_point, entry_point.dist, self.registry_name,
                )

    def _init_entry_point(self, entry_point):
        """
        Default does nothing.
        """

    def get_record(self, name):
        raise NotImplementedError

    def get(self, name):
        return self.get_record(name)

    def iter_records(self):
        raise NotImplementedError


class BasePkgRefRegistry(BaseRegistry):
    """
    A common base registry that deals with references for data within
    packages.
    """

    def __init__(self, registry_name, *a, **kw):
        super(BasePkgRefRegistry, self).__init__(registry_name, *a, **kw)
        self.package_module_map = PackageKeyMapping()
        self.register_entry_points(self.raw_entry_points)

    def register_entry_points(self, entry_points):
        """
        Register all entry_points provided by the list, if and only if
        the associated module can be imported.

        Arguments:

        entry_points
            a list of entry_points to be registered and activated into
            this registry instance.
        """

        return self._init_entry_points(entry_points)

    def _init_entry_point(self, entry_point):
        return self.register_entry_point(entry_point)

    def register_entry_point(self, entry_point):
        raise NotImplementedError

    def _dist_to_package_module_map(self, entry_point):
        # TODO fix the two following logging statement, likely indicates
        # that a proper cleanup/refactoring is needed for records in
        # this registry type.
        if entry_point.dist is None:
            # it's probably manually added not through the standard
            # setuptools procedures.
            logger.warning(
                "manually registering entry_point '%s' without associated "
                "distribution to registry '%s'",
                entry_point, self.registry_name,
            )
            return []  # just a dummy unconnected value.
        else:
            logger.debug(
                "registering entry_point '%s' from '%s' to registry '%s'",
                entry_point, entry_point.dist, self.registry_name,
            )
            if entry_point.dist.project_name not in self.package_module_map:
                self.package_module_map[entry_point.dist.project_name] = []
            return self.package_module_map[entry_point.dist.project_name]

    def store_records_for_package(self, entry_point, records):
        """
        Store the records in a way that permit lookup by package
        """

        # If provided records already exist in the module mapping list,
        # it likely means that a package declared multiple keys for the
        # same package namespace; while normally this does not happen,
        # this default implementation make no assumptions as to whether
        # or not this is permitted.
        pkg_module_records = self._dist_to_package_module_map(entry_point)
        pkg_module_records.extend(records)

    def iter_records(self):
        """
        Iterates through the records.
        """

        for item in self.records.items():
            yield item


class BaseModuleRegistry(BasePkgRefRegistry):
    """
    Extending off the BasePkgRefRegistry, ensure that there is a
    registration step that takes place that will verify the existence
    of the target.
    """

    def register_entry_point(self, entry_point):
        """
        Register a lone entry_point

        Will raise ImportError if the entry_point leads to an invalid
        import.
        """

        module = _import_module(entry_point.module_name)
        self._register_entry_point_module(entry_point, module)

    def _register_entry_point_module(self, entry_point, module):
        """
        Private method that registers an entry_point with a provided
        module.
        """

        records_map = self._map_entry_point_module(entry_point, module)
        self.store_records_for_package(entry_point, list(records_map.keys()))

        for module_name, records in records_map.items():
            if module_name in self.records:
                logger.info(
                    "module '%s' was already declared in registry '%s'; "
                    "applying new records on top.",
                    module_name, self.registry_name,
                )
                logger.debug("overwriting keys: %s", sorted(
                    set(self.records[module_name].keys()) &
                    set(records.keys())
                ))
                self.records[module_name].update(records)
            else:
                logger.debug(
                    "adding records for module '%s' to registry '%s'",
                    module_name, self.registry_name,
                )
                self.records[module_name] = records

    def _map_entry_point_module(self, entry_point, module):
        """
        Subclass need to implement this.

        The implementation is to return a map (dict) of the name of the
        module(s) with their mapped source files.
        """

        raise NotImplementedError

    def get_record(self, name):
        """
        Get a record by name
        """

        result = {}
        result.update(self.records.get(name, {}))
        return result

    def get_records_for_package(self, package_name):
        """
        Get all records identified by package.
        """

        names = self.package_module_map.get(package_name, [])
        result = {}
        for name in names:
            result.update(self.get_record(name))
        return result


class BaseChildModuleRegistry(BaseModuleRegistry):
    """
    To enable more generic support of child module registries, where the
    records depend on a parent registry, this class provides the basic
    framework to do so.
    """

    def __init__(self, registry_name, *a, **kw):
        # TODO whenever there is time to move the BaseRegistry to a
        # bootstrap module of some sort (that will break tests that
        # override calmjs.base.working_set if done naively), and have
        # the calmjs.registry.Registry inherit from that (and this
        # module also to maintain the BaseRegistry import location,
        # this import should be moved to the top
        from calmjs.registry import get
        # resolve parent before the parent class, as the construction
        # should be able to reference this parent.
        parent_name = self.resolve_parent_registry_name(registry_name)
        _parent = kw.pop('_parent', NotImplemented)
        if _parent is NotImplemented:
            self.parent = get(parent_name)
        else:
            self.parent = _parent

        if not self.parent:
            raise ValueError(
                "could not construct child module registry '%s' as its "
                "parent registry '%s' could not be found" % (
                    registry_name, parent_name)
            )
        super(BaseChildModuleRegistry, self).__init__(registry_name, *a, **kw)

    def resolve_parent_registry_name(self, registry_name, suffix):
        """
        Subclasses should override to specify the default suffix, as the
        invocation is done without a suffix.
        """

        if not registry_name.endswith(suffix):
            raise ValueError(
                "child module registry name defined with invalid suffix "
                "('%s' does not end with '%s')" % (registry_name, suffix))
        return registry_name[:-len(suffix)]


class BaseExternalModuleRegistry(BasePkgRefRegistry):
    """
    A registry for storing references to scripts sourced from JavaScript
    or Node.js module manager, i.e. node_modules.

    The intent of this registry is to have register paths that point to
    targets managed in those external systems via the key portion of the
    entry points.  The interpretation of the values will be specific to
    the implementation.

    At the very least, a value of true can simply be used to denote that
    a given package will want to do something with it.

    Another use case might be for the referencing of prebuilt artifacts
    and optionally give them an alias (however, it must be one that is
    compatible to the Python module name scheme given the limitations
    due to the entry point format).
    """

    # TODO decide on providing support for a handler, if an attribute to
    # some provided module was provided instead, so that it will resolve
    # the actual name with that callable - this means supplimentary info
    # can be provided, which could be provided via something like
    # calmjs_extras.

    def register_entry_point(self, entry_point):
        # for storing a mapping from the Python module that the
        # declarations to the JavaScript modules themselves.
        paths = self.process_entry_point(entry_point)
        self.store_record(entry_point, paths)
        self.store_records_for_package(entry_point, paths)

    def store_record(self, entry_point, paths):
        # the record is stored as an inverse mapping to the set of
        # paths that called on that module_name.
        self.records[entry_point.module_name] = self.records.get(
            entry_point.module_name, set()).union(paths)

    def process_entry_point(self, entry_point):
        """
        The default implementation simply return the entry point to a
        path.

        Result type should be an iterable.
        """

        return [entry_point.name]

    def get_record(self, name):
        """
        Get a record for the registered name, which will be a set of
        matching desired "module names" for the given path.
        """

        return set().union(self.records.get(name, set()))

    def get_records_for_package(self, package_name):
        """
        Get all records identified by package.
        """

        result = []
        result.extend(self.package_module_map.get(package_name))
        return result


class BaseDriver(object):
    """
    The Node.js interfacing base driver class.

    Classes under the calmjs framework that make use of Node.js or
    Node.js binaries should make this as the base class to make
    accessing the Node.js environment in a manner consistent with the
    framework, where various defined attributes and helper methods that
    makes use of those will make interfacing with the Node.js
    environment be under a consistently managed scheme.

    Helper methods such as _exec will ensure the binary is executed
    with the right arguments (via _gen_call_kws).  The dump/dumps method
    invokes the underlying functions of the same name from the json
    module with the attributes defined to ensure human readability by
    default.  Finally, join_cwd joins a target path with the working
    directory defined for instances of this, so that target path can be
    accessed in a more explicit way.
    """

    def __init__(self, node_path=None, env_path=None, working_dir=None,
                 indent=4, separators=(',', ': '), description=None):
        """
        Optional Arguments (defaults to None when not stated):

        node_path
            Overrides NODE_PATH environment variable for calling out.
        env_path
            Extra directory that will be assigned to the environment's
            PATH variable, so that that will be used first to look up a
            binary for exec calls.
        working_dir
            The working directory where the driver will operate at.
        indent
            JSON indentation level.  Defaults to 4.
        separators
            Set as a workaround to remove trailing spaces.  Should be
            left as is (',', ': ').
        description
            A description for this driver.  Optional string.
        """

        self.node_path = node_path or os.environ.get(NODE_PATH)
        self.env_path = env_path
        self.working_dir = working_dir
        self.indent = indent
        self.separators = separators
        self.binary = None
        self.description = description

    def which(self):
        """
        Figure out which binary this will execute.

        Returns None if the binary is not found.
        """

        if self.binary is None:
            return None

        return which(self.binary, path=self.env_path)

    def find_node_modules_basedir(self):
        """
        Find all node_modules directories configured to be accessible
        through this driver instance.

        This is typically used for adding the direct instance, and does
        not traverse the parent directories like what Node.js does.

        Returns a list of directories that contain a 'node_modules'
        directory.
        """

        paths = []

        # First do the working dir.
        local_node_path = self.join_cwd(NODE_MODULES)
        if isdir(local_node_path):
            paths.append(local_node_path)

        # do the NODE_PATH environment variable last, as Node.js seem to
        # have these resolving just before the global.
        if self.node_path:
            paths.extend(self.node_path.split(pathsep))

        return paths

    def which_with_node_modules(self):
        """
        Which with node_path and node_modules
        """

        if self.binary is None:
            return None

        # first, log down the pedantic things...
        if isdir(self.join_cwd(NODE_MODULES)):
            logger.debug(
                "'%s' instance will attempt to locate '%s' binary from "
                "%s%s%s%s%s, located through the working directory",
                self.__class__.__name__, self.binary,
                self.join_cwd(), sep, NODE_MODULES, sep, NODE_MODULES_BIN,
            )
        if self.node_path:
            logger.debug(
                "'%s' instance will attempt to locate '%s' binary from "
                "its %s of %s",
                self.__class__.__name__, self.binary,
                NODE_PATH, self.node_path,
            )

        paths = self.find_node_modules_basedir()
        whichpaths = pathsep.join(join(p, NODE_MODULES_BIN) for p in paths)

        if paths:
            logger.debug(
                "'%s' instance located %d possible paths to the '%s' binary, "
                "which are %s",
                self.__class__.__name__, len(paths), self.binary, whichpaths,
            )

        return which(self.binary, path=whichpaths)

    @classmethod
    def create(cls):
        """
        Freeze an instance to the current working directory and its
        related environmental settings.
        """

        inst = cls()
        inst._set_env_path_with_node_modules()
        return inst

    def _set_env_path_with_node_modules(self):
        """
        Attempt to locate and set the paths to the binary with the
        working directory defined for this instance.
        """

        modcls_name = ':'.join((
            self.__class__.__module__, self.__class__.__name__))

        if self.binary is None:
            raise ValueError(
                "binary undefined for '%s' instance" % modcls_name)

        logger.debug(
            "locating '%s' node binary for %s instance...",
            self.binary, modcls_name,
        )

        default = self.which()
        if default is not None:
            logger.debug(
                "found '%s'; "
                "not modifying PATH environment variable in instance of '%s'.",
                realpath(default), modcls_name)
            return True

        target = self.which_with_node_modules()

        if target:
            # Only setting the path specific for the binary; side effect
            # will be whoever else borrowing the _exec in here might not
            # get the binary they want.  That's why it's private.
            self.env_path = dirname(target)
            logger.debug(
                "located '%s' binary at '%s'; setting PATH environment "
                "variable for '%s' instance.",
                self.binary, self.env_path, modcls_name
            )
            return True
        else:
            logger.debug(
                "Unable to locate '%s'; not modifying PATH environment "
                "variable for instance of '%s'.",
                self.binary, modcls_name
            )
            return False

    def _gen_call_kws(self, **env):
        kw = {}
        if self.node_path is not None:
            env[NODE_PATH] = self.node_path
        if self.env_path is not None:
            # Initial assignment with check
            _check_isdir_assign_key(env, 'PATH', self.env_path)
            # then append the rest of it
            env['PATH'] = pathsep.join([
                env.get('PATH', ''), os.environ.get('PATH', '')])
        if self.working_dir:
            _check_isdir_assign_key(
                kw, 'cwd', self.working_dir,
                error_msg="current working directory left as default")
        kw['env'] = finalize_env(env)
        return kw

    def _get_exec_binary(self, kw):
        """
        This wraps the base function for BaseDriver classes; should only
        be called by this instance's binary execution methods as they
        will be also invoke _gen_call_kws to pass into the call_kw
        argument.

        This is different from the `which` method as the underlying
        function will raise the correct exception as if the underlying
        Popen method was called directly with the self.binary argument,
        while `which` will simply return None.
        """

        return _get_exec_binary(self.binary, kw)

    def _exec(self, binary, stdin='', args=(), env={}):
        """
        Executes the binary using stdin and args with environment
        variables.

        Returns a tuple of stdout, stderr.  Format determined by the
        input text (either str or bytes), and the encoding of str will
        be determined by the locale this module was imported in.
        """

        call_kw = self._gen_call_kws(**env)
        call_args = [self._get_exec_binary(call_kw)]
        call_args.extend(args)
        return fork_exec(call_args, stdin, **call_kw)

    @property
    def cwd(self):
        return self.working_dir or getcwd()

    def dump(self, blob, stream):
        """
        Call json.dump with the attributes of this instance as
        arguments.
        """

        json.dump(
            blob, stream, indent=self.indent, sort_keys=True,
            separators=self.separators,
        )

    def dumps(self, blob):
        """
        Call json.dumps with the attributes of this instance as
        arguments.
        """

        return json.dumps(
            blob, indent=self.indent, sort_keys=True,
            separators=self.separators,
        )

    def join_cwd(self, path=None):
        """
        Join the path with the current working directory.  If it is
        specified for this instance of the object it will be used,
        otherwise rely on the global value.
        """

        if self.working_dir:
            logger.debug(
                "'%s' instance 'working_dir' set to '%s' for join_cwd",
                type(self).__name__, self.working_dir,
            )
            cwd = self.working_dir
        else:
            cwd = getcwd()
            logger.debug(
                "'%s' instance 'working_dir' unset; "
                "default to process '%s' for join_cwd",
                type(self).__name__, cwd,
            )

        if path:
            return join(cwd, path)
        return cwd


class BaseLoaderPluginRegistry(BaseRegistry):

    def _init_entry_point(self, entry_point):
        try:
            cls = entry_point.load()
        except ImportError:
            logger.warning(
                "registry '%s' failed to load loader plugin handler for "
                "entry point '%s'", self.registry_name, entry_point,
            )
            return

        if not issubclass(cls, BaseLoaderPluginHandler):
            logger.warning(
                "entry point '%s' does not lead to a valid loader plugin "
                "handler class", entry_point
            )
            return

        inst = cls(self, entry_point.name)

        if entry_point.name in self.records:
            old = type(self.records[entry_point.name])
            logger.warning(
                "loader plugin handler for '%s' was already registered to "
                "an instance of '%s:%s'; '%s' will now override this "
                "registration",
                entry_point.name, old.__module__, old.__name__, entry_point
            )
        self.records[entry_point.name] = inst

    def to_plugin_name(self, value):
        """
        Find the plugin name from the provided value
        """

        return value.split('!', 1)[0].split('?', 1)[0]

    def get_record(self, name):
        # it is possible for subclasses to provide a fallback lookup on
        # "common" registries through the registry framework, e.g.
        # calmjs.registry.get('some.plugin.reg').get_record(name)
        return self.records.get(self.to_plugin_name(name))


class BaseLoaderPluginHandler(object):
    """
    The base loaderplugin handler class provides only the stub methods;
    for a more concrete implementation, refer to the loaderplugin module
    for the subclass.
    """

    def __init__(self, registry, name=None):
        """
        The LoaderPluginRegistry will try to construct the instance and
        pass itself into the constructor; leaving this as the default
        will enable specific plugins to load further plugins should the
        input modname has more loader plugin strings.
        """

        self.registry = registry
        self.name = name

    def modname_source_to_target(
            self, toolchain, spec, modname, source):
        """
        This is called by the Toolchain for modnames that contain a '!'
        as that signifies a loaderplugin syntax.  This will be used by
        the toolchain (which will also be supplied as the first argument)
        to resolve the copy target, which must be a path relative to the
        spec[WORKING_DIR].

        If the provided modname points contains a chain of loaders, the
        registry associated with this handler instance will be used to
        resolve the subsequent handlers until none are found, which that
        handler will be used to return this result.
        """

        stripped_modname = self.unwrap(modname)
        chained = (
            self.registry.get_record(stripped_modname)
            if '!' in stripped_modname else None)
        if chained:
            # ensure the stripped_modname is provided as by default the
            # handler will only deal with its own kind
            return chained.modname_source_to_target(
                toolchain, spec, stripped_modname, source)
        return stripped_modname

    def generate_handler_sourcepath(
            self, toolchain, spec, loaderplugin_sourcepath):
        """
        This returns the sourcepath (mapping) that may be added to the
        appropriate mapping within the spec for a successful toolchain
        execution.  The value generated is specific to the current
        spec that is being passed through the toolchain.

        The return value must be a modname: sourcepath mapping, e.g:

        return {
            'text': '/tmp/src/example_module/text/index.js',
            'json': '/tmp/src/example_module/json/index.js',
        }

        Subclasses must implement this to return a mapping of modnames
        the the absolute path of the desired sourcefiles.  Example:

        Implementation must also accept both the toolchain and the spec
        argument, along with the loaderplugin_sourcepath argument which
        will be a mapping of {modname: sourcepath} that are relevant to
        the current spec being processed through the toolchain.

        For nested/chained plugins, the recommended handling method is
        to make use of the assigned registry instance to lookup relevant
        loaderplugin handler(s) instances, and make use of their
        ``generate_handler_sourcepath`` method to generate the mapping
        required.  The immediate subclass in the loaderplugin module
        has a generic implementation done in this manner.
        """

        return {}

    def unwrap(self, value):
        """
        A helper method for unwrapping the loaderplugin fragment out of
        the provided value (typically a modname) and return it.

        Note that the filter chaining is very implementation specific to
        each and every loader plugin and their specific toolchain, so
        this default implementation is not going to attempt to consume
        everything in one go.

        Another note: if this is to be subclassed and if the return
        value does not actually remove the loaderplugin fragment, issues
        like default implmenetation of ``modname_source_to_target`` in
        this class to recurse forever.
        """

        globs = value.split('!', 1)
        if globs[0].split('?', 1)[0] == self.name:
            return globs[-1]
        else:
            return value

    def __call__(self, toolchain, spec, modname, source, target, modpath):
        """
        These need to provide the actual implementation required for the
        production of the final artifact, so this will need to locate
        the resources needed for this set of arguments to function.

        Implementations must return the associated modpaths, targets, and
        the export_module_name as a 3-tuple, after the copying or
        transpilation step was done.  Example:

        return (
            {'text!text_file.txt': 'text!/some/path/text_file.txt'},
            {'text_file.txt': 'text_file.txt'},
            ['text!text_file.txt'],
        )

        Note that implementations can trigger further lookups through
        the registry instance attached to this instance of the plugin,
        and implementations must also address the handling of this
        lookup and usage of the return values.

        Also note that while the toolchain and spec arguments are also
        provided, they should only be used for lookups; out of band
        modifications results in convoluted code flow.
        """

        raise NotImplementedError
