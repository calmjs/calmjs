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

from calmjs import base as calmjs_base
from calmjs.base import PackageKeyMapping
from calmjs.npm import locate_package_entry_file
from calmjs.base import BaseLoaderPluginRegistry
from calmjs.base import BaseLoaderPluginHandler
from calmjs.base import BaseChildModuleRegistry
from calmjs.toolchain import WORKING_DIR
from calmjs.toolchain import CALMJS_LOADERPLUGIN_REGISTRY
from calmjs.toolchain import spec_update_sourcepath_filter_loaderplugins

logger = logging.getLogger(__name__)
MODULE_LOADER_SUFFIX = '.loader'


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

    def generate_handler_sourcepath(
            self, toolchain, spec, loaderplugin_sourcepath):
        """
        The default implementation is a recursive lookup method, which
        subclasses may make use of.

        Subclasses must implement this to return a mapping of modnames
        the the absolute path of the desired sourcefiles.  Example:

        return {
            'text': '/tmp/src/example_module/text/index.js',
            'json': '/tmp/src/example_module/json/index.js',
        }

        Subclasses of this implementation must accept the same
        arguments, and they should invoke this implementation via super
        and merge its results (e.g. using dict.update) with one provided
        by this one.  Also, this implementation depends on a correct
        unwrap implementation for the loaderplugin at hand, if required.
        """

        # since the loaderplugin_sourcepath values is the complete
        # modpath with the loader plugin, the values must be stripped
        # before making use of the filtering helper function for
        # grouping the inner mappings
        fake_spec = {}
        registry = spec.get(CALMJS_LOADERPLUGIN_REGISTRY)
        if registry:
            fake_spec[CALMJS_LOADERPLUGIN_REGISTRY] = registry
        spec_update_sourcepath_filter_loaderplugins(fake_spec, {
            self.unwrap(k): v
            for k, v in loaderplugin_sourcepath.items()
        }, 'current', 'nested')
        result = {}
        for plugin_name, sourcepath in fake_spec['nested'].items():
            if sourcepath == loaderplugin_sourcepath:
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
            result.update(plugin.generate_handler_sourcepath(
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

    def find_node_module_pkg_name(self, toolchain, spec):
        return None

    def generate_handler_sourcepath(
            self, toolchain, spec, loaderplugin_sourcepath):
        """
        Attempt to locate the plugin source; returns a mapping of
        modnames to the absolute path of the located sources.
        """

        # TODO calmjs-4.0.0 consider formalizing to the method instead
        npm_pkg_name = (
            self.node_module_pkg_name
            if self.node_module_pkg_name else
            self.find_node_module_pkg_name(toolchain, spec)
        )

        if not npm_pkg_name:
            cls = type(self)
            registry_name = getattr(
                self.registry, 'registry_name', '<invalid_registry/handler>')
            if cls is NPMLoaderPluginHandler:
                logger.error(
                    "no npm package name specified or could be resolved for "
                    "loaderplugin '%s' of registry '%s'; please subclass "
                    "%s:%s such that the npm package name become specified",
                    self.name, registry_name, cls.__module__, cls.__name__,
                )
            else:
                logger.error(
                    "no npm package name specified or could be resolved for "
                    "loaderplugin '%s' of registry '%s'; implementation of "
                    "%s:%s may be at fault",
                    self.name, registry_name, cls.__module__, cls.__name__,
                )
            return {}

        working_dir = spec.get(WORKING_DIR, None)
        if working_dir is None:
            logger.info(
                "attempting to derive working directory using %s, as the "
                "provided spec is missing working_dir", toolchain
            )
            working_dir = toolchain.join_cwd()

        logger.debug("deriving npm loader plugin from '%s'", working_dir)

        target = locate_package_entry_file(working_dir, npm_pkg_name)
        if target:
            logger.debug('picked %r for loader plugin %r', target, self.name)
            # use the parent recursive lookup.
            result = super(
                NPMLoaderPluginHandler, self).generate_handler_sourcepath(
                    toolchain, spec, loaderplugin_sourcepath)
            result.update({self.name: target})
            return result

        # the expected package file is not found, use the logger to show
        # why.
        # Also note that any inner/chained loaders will be dropped.
        if exists(join(
                working_dir, 'node_modules', npm_pkg_name,
                'package.json')):
            logger.warning(
                "'package.json' for the npm package '%s' does not contain a "
                "valid entry point: sources required for loader plugin '%s' "
                "cannot be included automatically; the build process may fail",
                npm_pkg_name, self.name,
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
                npm_pkg_name, self.name, working_dir,
                npm_pkg_name,
            )

        return {}


class ModuleLoaderRegistry(BaseChildModuleRegistry):
    """
    This registry works in tandem with the prefix it is defined for, to
    ease the declaration of resource files that are also to be exported
    alongside with the modules declared for export.  For example,
    declaring an instance of this registry under the calmjs.registry
    entry point group with the name `calmjs.module.loader` will make
    this work in tandem with `calmjs.module`.
    """

    def __init__(self, registry_name, *a, **kw):
        self.package_loader_map = PackageKeyMapping()
        super(ModuleLoaderRegistry, self).__init__(registry_name, *a, **kw)

    def resolve_parent_registry_name(
            self, registry_name, suffix=MODULE_LOADER_SUFFIX):
        return super(ModuleLoaderRegistry, self).resolve_parent_registry_name(
            registry_name, suffix)

    def register_entry_point(self, entry_point):
        # use the module names registered on the parent registry, but
        # apply the entry points defined for this registry name.
        module_names = self.parent.package_module_map[
            entry_point.dist.project_name]
        for module_name in module_names:
            module = calmjs_base._import_module(module_name)
            self._register_entry_point_module(entry_point, module)

    def store_records_for_package(self, entry_point, records):
        """
        Given that records are based on the parent, and the same entry
        point(s) will reference those same records multiple times, the
        actual stored records must be limited.
        """

        pkg_records_entry = self._dist_to_package_module_map(entry_point)
        pkg_records_entry.extend(
            rec for rec in records if rec not in pkg_records_entry)
        # TODO figure out a more efficient way to do this with a bit
        # more reuse.
        if entry_point.dist is not None:
            if entry_point.dist.project_name not in self.package_loader_map:
                self.package_loader_map[entry_point.dist.project_name] = []
            self.package_loader_map[entry_point.dist.project_name].append(
                entry_point.name)

    def get_loaders_for_package(self, package_name):
        return self.package_loader_map.get(package_name, [])

    def generate_complete_modname(self, prefix, modname, extension):
        # typically the filename extension should be reapplied, assuming
        # the parent mapper function strip that out for the ES5 name, as
        # loaders typically need the full path.
        return '%s!%s%s' % (prefix, modname, extension)

    def _map_entry_point_module(self, entry_point, module):
        mapping = {}
        result = {module.__name__: mapping}
        for extra in entry_point.extras:
            # since extras cannot contain leading '.', the full filename
            # extension must be built.
            extension = '.' + extra
            mapping.update({
                self.generate_complete_modname(
                    entry_point.name, modname, extension): targetpath
                for modname, targetpath in self.parent.mapper(
                    module, entry_point, fext=extension).items()
            })
        return result
