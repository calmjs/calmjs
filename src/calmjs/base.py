# -*- coding: utf-8 -*-
"""
calmjs.base

This module contains various base classes from which other parts of this
framework will inherit/extend from.
"""

import os

import json
import warnings
from locale import getpreferredencoding
from os import getcwd
from os.path import isdir
from os.path import join
from os.path import pathsep

from subprocess import Popen
from subprocess import PIPE

from collections import OrderedDict
from logging import getLogger
from pkg_resources import working_set

from calmjs.utils import which

NODE_PATH = 'NODE_PATH'
NODE = 'node'
locale = getpreferredencoding()

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
        Subclass need to implement this.
        """

        raise NotImplementedError

    def get_record(self, name):
        """
        Get a record by name
        """

        result = {}
        result.update(self.records.get(name, {}))
        return result

    def iter_records(self):
        """
        Iterates through the records.
        """

        for item in self.records.items():
            yield item


class BaseDriver(object):
    """
    The nodejs interfacing base driver class.

    Classes under the calmjs framework that make use of nodejs or nodejs
    binaries should make this as the base class to make accessing the
    nodejs environment in a manner consistent with the framework, where
    various defined attributes and helper methods that makes use of
    those will make interfacing with the nodejs environment be under a
    consistently managed scheme.

    Helper methods such as _exec will ensure the binary is executed
    with the right arguments (via _gen_call_kws).  The dump/dumps method
    invokes the underlying functions of the same name from the json
    module with the attributes defined to ensure human readability by
    default.  Finally, join_cwd joins a target path with the working
    directory defined for instances of this, so that target path can be
    accessed in a more explicit way.
    """

    def __init__(self, node_path=None, env_path=None, working_dir=None,
                 indent=4, separators=(',', ': ')):
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
        """

        self.node_path = node_path
        self.env_path = env_path
        self.working_dir = working_dir
        self.indent = indent
        self.separators = separators
        self.binary = None

    def which(self):
        """
        Figure out which binary this will execute.
        """

        if self.binary is None:
            return None

        return which(self.binary, path=self.env_path)

    def _set_env_path_with_node_modules(self, warn=False):
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
                default, modcls_name)
            return

        node_path = os.environ.get(NODE_PATH)
        if node_path:
            logger.debug(
                "environment variable '%s' defined (%s); "
                "selected as base directory for finding node binaries.",
                NODE_PATH, node_path,
            )
        else:
            node_path = self.join_cwd('node_modules')
            logger.debug(
                "environment variable '%s' undefined; using instance's "
                "working directory's node_modules (%s) as base directory for "
                "finding node binaries.",
                NODE_PATH, node_path,
            )

        env_path = join(node_path, '.bin')
        if which(self.binary, path=env_path):
            # Only setting the path specific for the binary; side effect
            # will be whoever else borrowing the _exec in here might not
            # get the binary they want.  That's why it's private.
            logger.debug(
                "located '%s' binary at '%s'; setting PATH environment "
                "variable for '%s' instance.",
                self.binary, env_path, modcls_name
            )
            self.env_path = env_path
        elif warn:
            msg = (
                "Unable to locate the '%(binary)s' binary; default module "
                "level functions will not work. Please either provide "
                "%(PATH)s and/or update %(PATH)s environment variable "
                "with one that provides '%(binary)s'; or specify a "
                "working %(NODE_PATH)s environment variable with "
                "%(binary)s installed; or have install '%(binary)s' into "
                "the current working directory (%(cwd)s) either through "
                "npm or calmjs framework for this package. Restart or "
                "reload this module once that is done. Alternatively, "
                "create a manual Driver instance for '%(binary)s' with "
                "explicitly defined arguments." % {
                    'binary': self.binary,
                    'PATH': 'PATH',
                    'NODE_PATH': NODE_PATH,
                    'cwd': self.join_cwd(),
                }
            )
            warnings.warn(msg, RuntimeWarning)
            # Yes there may be duplicates, but warnings are governed
            # differently.
            logger.debug(msg)
        else:
            logger.debug(
                "Unable to locate '%s'; not modifying PATH environment "
                "variable for instance of '%s'.",
                self.binary, modcls_name
            )

    def _gen_call_kws(self, **env):
        kw = {}
        if self.node_path is not None:
            _check_isdir_assign_key(env, NODE_PATH, self.node_path)
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
        if env:
            kw['env'] = env
        return kw

    def _exec(self, binary, stdin='', args=(), env={}):
        """
        Executes the binary using stdin and args with environment
        variables.

        Returns a tuple of stdout, stderr.  Format determined by the
        input text (either str or bytes), and the encoding of str will
        be determined by the locale this module was imported in.
        """

        call_kw = self._gen_call_kws(**env)
        call_args = [binary]
        call_args.extend(args)
        as_bytes = isinstance(stdin, bytes)
        source = stdin if as_bytes else stdin.encode(locale)
        p = Popen(call_args, stdin=PIPE, stdout=PIPE, stderr=PIPE, **call_kw)
        stdout, stderr = p.communicate(source)
        if as_bytes:
            return stdout, stderr
        return (stdout.decode(locale), stderr.decode(locale))

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
                "instance 'working_dir' set to '%s'", self.working_dir)
            cwd = self.working_dir
        else:
            cwd = getcwd()
            logger.debug(
                "instance 'working_dir' unset; default to process '%s'", cwd)

        if path:
            return join(cwd, path)
        return cwd
