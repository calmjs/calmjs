# -*- coding: utf-8 -*-
"""
Loader plugin support

Originally created for calmjs.rjs for handling requirejs loaders, this
ported version is stripped down to make it more generic so that other
frameworks may be able to extend on this.
"""

from __future__ import absolute_import

import logging
import json
from os.path import exists
from os.path import join

from calmjs.base import BaseRegistry
from calmjs.toolchain import WORKING_DIR

logger = logging.getLogger(__name__)


class LoaderPluginRegistry(BaseRegistry):

    def _init(self):
        for entry_point in self.raw_entry_points:
            try:
                cls = entry_point.load()
            except ImportError:
                logger.warning(
                    "registry '%s' failed to load loader plugin handler for "
                    "entry point '%s'", self.registry_name, entry_point,
                )
                continue

            if not issubclass(cls, LoaderPluginHandler):
                logger.warning(
                    "entry point '%s' does not lead to a valid loader plugin "
                    "handler class", entry_point
                )
                continue

            try:
                inst = cls(self, entry_point.name)
            except Exception:
                logger.exception(
                    "the loader plugin class registered at '%s' failed "
                    "to be instantiated with the following exception",
                    entry_point,
                )
                continue

            if entry_point.name in self.records:
                old = type(self.records[entry_point.name])
                logger.warning(
                    "loader plugin handler for '%s' was already registered to "
                    "an instance of '%s:%s'; '%s' will now override this "
                    "registration",
                    entry_point.name, old.__module__, old.__name__, entry_point
                )
            self.records[entry_point.name] = inst

    def get_record(self, name):
        return self.records.get(name)


class LoaderPluginHandler(object):
    """
    Encapsulates a loader plugin; this provides a framework to deal with
    path mangling and/or resolution for setting up the paths for usage
    within frameworks that provide support for loader plugins.
    """

    # The npm module name for this particular loader plugin.  If
    # specified, the default lookup method will attempt to locate this
    # the from the node_modules directory in current working directory.
    # Otherwise, it's assumed to be available (e.g. as part of the
    # exported JavaScript modules or specified to be bundled).

    node_module = None

    def __init__(self, registry, name=None):
        """
        The registry itself (defined below) will try to construct the
        instance and pass itself into the constructor; leaving this as
        the default will enable specific plugins to load further plugins
        should the input modname has more loader plugin strings.
        """

        self.registry = registry
        self.name = name

    def locate_plugin_source(self, toolchain, spec):
        """
        Attempt to locate the plugin source; returns a mapping of
        modnames to the absolute path of the located sources.
        """

        if not self.node_module:
            return {}

        basedir = join(spec[WORKING_DIR], 'node_modules', self.node_module)
        package_json = join(basedir, 'package.json')
        if not exists(package_json):
            logger.warning(
                "could not locate package.json for the npm package %r which "
                "was specified to contain the loader plugin %r in the current "
                "working directory '%s'; the package may have been not "
                "installed, the build process may fail",
                self.node_module, self.name, spec[WORKING_DIR],
            )
            return {}

        with open(package_json) as fd:
            package_info = json.load(fd)

        if not ('browser' in package_info or 'main' in package_info):
            logger.warning(
                'package.json for the npm package %r does not contain a main '
                'entry point: sources required for loader plugin %r cannot '
                'be included automatically; the build process may fail.',
                self.node_module, self.name
            )
            return {}

        # assume the target file exists...
        target = join(
            basedir,
            *(package_info.get('browser') or package_info['main']).split('/')
        )
        logger.debug('picked %r for loader plugin %r', target, self.name)
        return {self.name: target}

    def strip_plugin(self, value):
        """
        Strip the first plugin fragment and return just the value.

        Note that the filter chaining can be very implementation
        specific, so the default implementation is not going to attempt
        to do everything in one go.
        """

        if value.startswith(self.name + '!'):
            result = value.split('!', 1)
            return result[-1]
        else:
            return value

    def __call__(self, toolchain, spec, modname, source, target, modpath):
        """
        These need to provide the actual implementation required for the
        production of the final artifact, so this will need to locate
        the resources needed for this set of arguments to function.

        Each of these should return the associated bundled_modpaths,
        bundled_targets, and the export_module_name, after the copying
        or transpilation step was done.
        """

        raise NotImplementedError
