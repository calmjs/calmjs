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
from os.path import exists
from os.path import isdir
from os.path import join
from os.path import pathsep
from os.path import realpath

from collections import OrderedDict
from logging import getLogger
from pkg_resources import working_set

from calmjs.utils import which
from calmjs.utils import finalize_env
from calmjs.utils import fork_exec
from calmjs.utils import raise_os_error

NODE_PATH = 'NODE_PATH'
NODE = 'node'

logger = getLogger(__name__)
_marker = object()


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
        Subclasses can override this for setting up its single instance.
        """

    def get_record(self, name):
        raise NotImplementedError

    def get(self, name):
        return self.get_record(name)

    def iter_records(self):
        raise NotImplementedError


class BaseModuleRegistry(BaseRegistry):
    """
    Extending off the BaseRegistry, ensure that there is a registration
    step that takes place that will verify the existence of the target.
    """

    def __init__(self, registry_name, *a, **kw):
        super(BaseModuleRegistry, self).__init__(registry_name, *a, **kw)
        self.package_module_map = {}
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

        for entry_point in entry_points:
            try:
                self.register_entry_point(entry_point)
            except ImportError:
                logger.warning(
                    'ImportError: %s not found; skipping registration',
                    entry_point.module_name)
                continue

    def register_entry_point(self, entry_point):
        """
        Register a lone entry_point

        Will raise ImportError if the entry_point leads to an invalid
        import.
        """

        module = __import__(
            entry_point.module_name, fromlist=['__name__'], level=0)

        self._register_entry_point_module(entry_point, module)

    def _register_entry_point_module(self, entry_point, module):
        """
        Private method that registers an entry_point with a provided
        module.
        """

        records_map = self._map_entry_point_module(entry_point, module)

        if entry_point.dist is None:
            # it's probably manually added not through the standard
            # setuptools procedures.
            logger.warning(
                "manually registering entry_point '%s' without associated "
                "distribution to registry '%s'",
                entry_point, self.registry_name,
            )
        else:
            logger.debug(
                "registering entry_point '%s' from '%s' to registry '%s'",
                entry_point, entry_point.dist, self.registry_name,
            )
            if entry_point.dist.project_name not in self.package_module_map:
                self.package_module_map[entry_point.dist.project_name] = []
            # if duplicates exist, it means a package declared multiple
            # keys for the same namespace and they really shouldn't do
            # that.
            self.package_module_map[entry_point.dist.project_name].extend(
                list(records_map.keys()))

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

    def iter_records(self):
        """
        Iterates through the records.
        """

        for item in self.records.items():
            yield item


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

    def which_with_node_modules(self):
        """
        Which with node_path and node_modules
        """

        if self.binary is None:
            return None

        paths = []
        if self.node_path:
            paths.extend(self.node_path.split(pathsep))
            logger.debug(
                "environment variable '%s' defined '%s'; "
                "their bin directories will be searched.",
                NODE_PATH, self.node_path,
            )
        local_node_path = self.join_cwd('node_modules')
        if exists(local_node_path):
            logger.debug(
                "including instance's working directory's '%s' for location "
                "of '%s'",
                local_node_path, self.binary,
            )
            paths.append(local_node_path)

        return which(self.binary, path=pathsep.join(
            join(p, '.bin') for p in paths))

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
