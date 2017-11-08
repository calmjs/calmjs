# -*- coding: utf-8 -*-
"""
Loader plugin support

Originally created for calmjs.rjs for handling requirejs loaders, this
ported version is stripped down to make it more generic so that other
frameworks may be able to extend on this.
"""

from __future__ import absolute_import

import logging
from os.path import exists
from os.path import join

from calmjs.npm import locate_package_entry_file
from calmjs.base import BaseLoaderPluginRegistry
from calmjs.base import BaseLoaderPluginHandler
from calmjs.toolchain import WORKING_DIR
from calmjs.toolchain import spec_update_loaderplugins_sourcepath_dict

logger = logging.getLogger(__name__)


class LoaderPluginRegistry(BaseLoaderPluginRegistry):
    """
    Standard loaderplugin registry - with the default _init method
    calling the _init_entry_point method for setting up the raw
    entry points captured from the working set.
    """

    def _init(self, *a, **kw):
        self._init_entry_points(self.raw_entry_points)


class LoaderPluginHandler(BaseLoaderPluginHandler):
    """
    Generic loader plugin handler encapsulates the specific handling
    rules for a successful build; this includes dealing with injection
    of specific bundle sourcepaths and the like for the target framework
    to be supported by subclasses.
    """

    def locate_bundle_sourcepath(self, toolchain, spec, plugin_sourcepath):
        """
        The default implementation is a recursive lookup method, which
        subclasses may make use of.

        Subclasses must implement this to return a mapping of modnames
        the the absolute path of the desired sourcefiles.  Example:

        return {
            'text': '/tmp/src/example_module/text/index.js'
            'json': '/tmp/src/example_module/json/index.js'
        }

        Implementation must also accept both the toolchain and the spec
        argument, along with the plugin_sourcepath argument which will
        be a mapping of {modname: sourcepath} that are relevant to this
        specific plugin handler.  Instances of subclasses may then
        derive the the bundle_sourcepath required for a successful build
        for the given toolchain and spec.

        For nested/chained plugins, the recommended handling method is
        to also make use of the registry instance assigned to this
        handler instance to lookup specific handler(s) that may also
        be registered here, and use their locate_bundle_sourcepath
        method to generate the mapping required.
        """

        # since the plugin_sourcepath values is the complete modpath
        # with the loader plugin, the values must be stripped before
        # making use of the filtering helper function for grouping
        # the inner mappings
        fake_spec = {}
        spec_update_loaderplugins_sourcepath_dict(fake_spec, {
            self.strip_plugin(k): v
            for k, v in plugin_sourcepath.items()
        }, 'current', 'nested')
        result = {}
        for plugin_name, sourcepath in fake_spec['nested'].items():
            if sourcepath == plugin_sourcepath:
                logger.warning(
                    "loaderplugin '%s' extracted same sourcepath of while "
                    "locating chain loaders: %s; skipping",
                    self.name, sourcepath
                )
                continue
            plugin = self.registry.get_record(plugin_name)
            if not plugin:
                logger.warning(
                    "loaderplugin '%s' from registry '%s' cannot find "
                    "sibling loaderplugin handler for '%s'; processing "
                    "may fail for the following nested/chained sources: "
                    "%s",
                    self.name, self.registry.registry_name, plugin_name,
                    sourcepath,
                )
                continue
            result.update(plugin.locate_bundle_sourcepath(
                toolchain, spec, sourcepath))
        return result


class NPMLoaderPluginHandler(LoaderPluginHandler):
    """
    Encapsulates a loader plugin sourced from NPM (i.e. node_modules);
    this provides a framework to deal with path mangling and/or
    resolution for setting up the paths for usage within frameworks that
    provide support for loader plugins.
    """

    # The npm module name for this particular loader plugin.  If
    # specified, the default lookup method will attempt to locate this
    # the from the node_modules directory in current working directory.
    # Otherwise, it's assumed to be available (e.g. as part of the
    # exported JavaScript modules or specified to be bundled).

    node_module_pkg_name = None

    def locate_bundle_sourcepath(self, toolchain, spec, plugin_sourcepath):
        """
        Attempt to locate the plugin source; returns a mapping of
        modnames to the absolute path of the located sources.
        """

        if not self.node_module_pkg_name:
            return {}

        working_dir = spec.get(WORKING_DIR, None)
        if working_dir is None:
            logger.info(
                "attempting to derive working directory using %s, as the "
                "provided spec is missing working_dir", toolchain
            )
            working_dir = toolchain.join_cwd()

        logger.debug("deriving npm loader plugin from '%s'", working_dir)

        target = locate_package_entry_file(
            working_dir, self.node_module_pkg_name)
        if target:
            logger.debug('picked %r for loader plugin %r', target, self.name)
            # use the parent recursive lookup.
            result = super(
                NPMLoaderPluginHandler, self).locate_bundle_sourcepath(
                    toolchain, spec, plugin_sourcepath)
            result.update({self.name: target})
            return result

        # the expected package file is not found, use the logger to show
        # why.
        # Also note that any inner/chained loaders will be dropped.
        if exists(join(
                working_dir, 'node_modules', self.node_module_pkg_name,
                'package.json')):
            logger.warning(
                "'package.json' for the npm package '%s' does not contain a "
                "valid entry point: sources required for loader plugin '%s' "
                "cannot be included automatically; the build process may fail",
                self.node_module_pkg_name, self.name,
            )
        else:
            logger.warning(
                "could not locate 'package.json' for the npm package '%s' "
                "which was specified to contain the loader plugin '%s' in the "
                "current working directory '%s'; the missing package may "
                "be installed by running 'npm install %s' for the mean time "
                "as a workaround, though the package that owns that source "
                "file that has this requirement should declare an explicit "
                "dependency; the build process may fail",
                self.node_module_pkg_name, self.name, working_dir,
                self.node_module_pkg_name,
            )

        return {}
