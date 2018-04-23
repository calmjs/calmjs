# -*- coding: utf-8 -*-
"""
Management of the production and querying of prebuilt artifacts.

The design for the artifact registry system makes a number of tradeoffs
to increase end-user usability and simplicity, by not using another
registry to manage the sets of common functions for artifact production
that are designated to be compatible.  The usage of the
``EntryPoint.attrs`` as the authoritative identifier for the group of
common functions without delegating this role to another registry has
the benefit of simplifying lookup, but this means that any future
changes to the meaning of the name of that group should not be done as
the versioning of this can become quite complicated.

This also mean that the usage of extra metadata is required for
recording which version of what package actually resulted in the
construction of that package.  Also, this means the various toolchain
packages must cooperate on what the meaning of the words are, in order
for a single artifact registry instance to function in an unambiguous
manner.

To achieve this, the functions registered to the registry MUST accept
the two required arguments, ``package_names`` and ``export_target`` (for
the production of the ``Spec`` instance), and MUST NOT produce the
artifacts directly, but instead return a 2-tuple containing a
``Toolchain`` and ``Spec`` instance.  This return value is then invoked
by the build method within the ``ArtifactRegistry`` instance which will
complete the build task.  The results can be queried through the methods
offered by the registry.

Correct functionality, of course, depends fully on the package and the
developer who built the artifact, and requires that the process as
outlined in the API is fully followed without artificial out-of-band
manipulation, as there are zero enforcement options for guarding against
what actually goes into a wheel.

For example, given the two following packages that provide a calmjs
toolchain implementation:

- default.gloop
- default.glump

They could provide a module that contain functions such as:

- default.gloop.build:gloop_artifact
- default.glump.build:glump_artifact

A package that require artifacts built, ``example.package``, may have
this declaration in its entry points:

    [calmjs.artifacts]
    deploy.gloop.js = default.gloop.build:gloop_artifact
    deploy.glump.js = default.glump.build:glump_artifact

The build process for both artifacts can be manually trigger by the
following code:

    >>> from calmjs.registry import get
    >>> artifacts = get('calmjs.artifacts')
    >>> artifacts.process_package('example.package')
    Building artifact for deploy.gloop.js
    Building artifact for deploy.glump.js

When the build process is done, inside the egg-info or dist-info
directory of the ``example.package`` package will have a new
``calmjs_artifacts`` directory that contain both those new artifact
files.

Resolution for the location of the artifact can be done using the
``resolve_artifacts_by_builder_compat`` method on the registry instance,
for example:

    >>> list(artifacts.resolve_artifacts_by_builder_compat(
    ...     'example.package', 'gloop_artifact'))
    ['/.../src/example.package.egg-info/calmjs_artifacts/deploy.gloop.js']

However, if the ``example.package`` wish to have its own build process
for either of those artifacts, it can declare a new builder with the
same name in itself like so:

- example.package.builder:gloop_artifact

Thus changing the entry point to this:

    [calmjs.artifacts]
    deploy.gloop.js = example.package.builder:gloop_artifact
    deploy.glump.js = default.glump.builder:glump_artifact

The resolve method should bring up the information.

To enable the building of artifacts while building the package using
setuptools, in the ``setup`` function (typically of ``setup.py``) the
``build_calmjs_artifacts` should be set to True.  Combining together
with the entry point setup, the setup call may look something like this:

    setup(
        name='example.package',
        # ...
        build_calmjs_artifacts=True,
        entry_points={
            # module declaration
            'calmjs.module': [
                'example.package = example.package',
            ],
            'calmjs.artifacts': [
                'deploy.gloop.js = example.package.builder:gloop_artifact',
                'deploy.glump.js = default.glump.builder:glump_artifact',
            ],
        },
        build_calmjs_artifacts=True,
        # ...
    )
"""

from __future__ import absolute_import

import json
import warnings
from codecs import open
from inspect import getcallargs
from inspect import getmro
from logging import getLogger
from os.path import basename
from os.path import dirname
from os.path import exists
from os.path import isdir
from os.path import join
from os.path import normcase
from os import makedirs
from os import unlink
from shutil import rmtree

from calmjs.base import BaseRegistry
from calmjs.base import PackageKeyMapping
from calmjs.dist import find_packages_requirements_dists
from calmjs.dist import find_pkg_dist
from calmjs.dist import is_json_compat
from calmjs.dist import pkg_names_to_dists
from calmjs.cli import get_bin_version_str
from calmjs.command import BuildArtifactCommand
from calmjs.registry import get
from calmjs.types.exceptions import ToolchainAbort
from calmjs.toolchain import Toolchain
from calmjs.toolchain import Spec
from calmjs.toolchain import TOOLCHAIN_BIN_PATH
from calmjs.toolchain import BEFORE_PREPARE
from calmjs.toolchain import EXPORT_TARGET

ARTIFACT_BASENAME = 'calmjs_artifacts'
ARTIFACT_REGISTRY_NAME = 'calmjs.artifacts'

logger = getLogger(__name__)


def _cls_lookup_dist(cls):
    """
    Attempt to resolve the distribution from the provided class in the
    most naive way - this assumes the Python module path to the class
    contains the name of the package that provided the module and class.
    """

    frags = cls.__module__.split('.')
    for name in ('.'.join(frags[:x]) for x in range(len(frags), 0, -1)):
        dist = find_pkg_dist(name)
        if dist:
            return dist


def verify_builder(builder):
    """
    To ensure that the provided builder has a signature that is at least
    compatible.
    """

    try:
        d = getcallargs(builder, package_names=[], export_target='some_path')
    except TypeError:
        return False
    return d == {'package_names': [], 'export_target': 'some_path'}


def extract_builder_result(builder_result, toolchain_cls=Toolchain):
    """
    Extract the builder result to produce a ``Toolchain`` and ``Spec``
    instance.
    """

    try:
        toolchain, spec = builder_result
    except Exception:
        return None, None
    if not isinstance(toolchain, toolchain_cls) or not isinstance(spec, Spec):
        return None, None
    return toolchain, spec


def trace_toolchain(toolchain):
    """
    Trace the versions of the involved packages for the provided
    toolchain instance.
    """

    pkgs = []
    for cls in getmro(type(toolchain)):
        if not issubclass(cls, Toolchain):
            continue
        dist = _cls_lookup_dist(cls)
        value = {
            'project_name': dist.project_name,
            'version': dist.version,
        } if dist else {}
        key = '%s:%s' % (cls.__module__, cls.__name__)
        pkgs.append({key: value})
    return pkgs


def setup_export_location(export_target):
    target_dir = dirname(export_target)
    try:
        if not exists(target_dir):
            makedirs(target_dir)
            logger.debug("created '%s' for '%s'", target_dir, export_target)
        elif not isdir(target_dir):
            logger.error(
                "cannot export to '%s' as its dirname does not lead to a "
                "directory", export_target
            )
            return False
        elif isdir(export_target):
            logger.debug(
                "removing existing export target directory at '%s'",
                export_target
            )
            rmtree(export_target)
        elif exists(export_target):
            logger.debug(
                "removing existing export target at '%s'", export_target)
            unlink(export_target)
    except (IOError, OSError) as e:
        logger.error(
            "failed to prepare export location '%s': %s; ensure that any file "
            "permission issues are corrected and/or remove the egg-info "
            "directory for this package before trying again",
            target_dir, e)
        return False

    return True


def prepare_export_location(export_target):
    """
    The version of setup_export_location for use with spec advice
    before_prepare step.
    """

    if not setup_export_location(export_target):
        raise ToolchainAbort()
    return True


class BaseArtifactRegistry(BaseRegistry):
    """
    The base artifact registry implementation.
    A registry to allow a central place for Python packages to declare
    which method to generate the artifact and what name to use.
    """

    def _init(self):
        # default (self.records) is a map of package + name to path
        # this is the reverse lookup for that
        self.reverse = {}
        self.packages = PackageKeyMapping()
        # metadata file about the artifacts for the package
        self.metadata = PackageKeyMapping()
        # for storing builders that are assumed to be compatible due to
        # their identical attribute names.
        self.compat_builders = PackageKeyMapping()
        # TODO determine if the full import name lookup table is
        # required.
        # self.builders = {}

        for ep in self.raw_entry_points:
            # the expected path to the artifact.
            self.register_entry_point(ep)

    def register_entry_point(self, ep):
        path = join(ep.dist.egg_info, ARTIFACT_BASENAME, ep.name)
        nc_path = normcase(path)

        if nc_path in self.reverse:
            logger.error(
                "entry point '%s' from package '%s' resolves to the path '%s' "
                "which was already registered to entry point '%s'; "
                "conflicting entry point registration will be ignored.",
                ep, ep.dist, path, self.reverse[nc_path]
            )
            if normcase(ep.name) != ep.name:
                logger.error(
                    "the file mapping error is caused by this platform's case-"
                    "insensitive filename and the package '%s' defined case-"
                    "sensitive names for the affected artifact"
                )
            return

        # for lookup of the generator(s) for the given package
        p = self.packages[ep.dist.project_name] = self.packages.get(
            ep.dist.project_name, {})
        p[ep.name] = ep

        # for lookup of the path by the builder identified by the
        # compat name (the attrs of the provided entry points) for
        # Python packages.
        cb_key = '.'.join(ep.attrs)
        cb = self.compat_builders[cb_key] = self.compat_builders.get(
            cb_key, PackageKeyMapping())
        cb[ep.dist.project_name] = path

        # for looking up/storage of metadata about the built artifacts.
        self.metadata[ep.dist.project_name] = join(
            ep.dist.egg_info, ARTIFACT_BASENAME + '.json')

        # standard get_artifact_filename lookup for standalone,
        # complete artifacts at some path.
        # TODO consider changing the storage implementation to not use
        # tuple but rather use the PackageKeyMapping for the package
        # name, then a secondary inner lookup for the artifact_name.
        # This is to maintain consistency across implementation
        self.records[(ep.dist.project_name, ep.name)] = path
        # only the reverse lookup must be normalized
        self.reverse[nc_path] = ep

    def iter_records(self):
        # not especially useful, but implementing for completeness.
        for k in self.records.keys():
            yield k

    def belongs_to(self, path):
        """
        Lookup which entry point generated this path.
        """

        return self.reverse.get(normcase(path))

    def get_artifact_filename(self, package_name, artifact_name):
        """
        Similar to pkg_resources.resource_filename, however this works
        with the information cached in this registry instance, and
        arguments are not quite the same.

        Arguments:

        package_name
            The name of the package to get the artifact from
        artifact_name
            The exact name of the artifact.

        Returns the path of where the artifact should be if it has been
        declared, otherwise None.
        """

        project_name = self.packages.normalize(package_name)
        return self.records.get((project_name, artifact_name))

    def resolve_artifacts_by_builder_compat(
            self, package_names, builder_name, dependencies=False):
        """
        Yield the list of paths to the artifacts in the order of the
        dependency resolution

        Arguments:

        package_names
            The names of the packages to probe the dependency graph, to
            be provided as a list of strings.
        artifact_name
            The exact name of the artifact.
        dependencies
            Trace dependencies.  Default is off.

        Returns the path of where the artifact should be if it has been
        declared, otherwise None.
        """

        paths = self.compat_builders.get(builder_name)
        if not paths:
            # perhaps warn, but just return
            return

        resolver = (
            # traces dependencies for distribution.
            find_packages_requirements_dists
            if dependencies else
            # just get grabs the distribution.
            pkg_names_to_dists
        )
        for distribution in resolver(package_names):
            path = paths.get(distribution.project_name)
            if path:
                yield path

    def get_artifact_metadata(self, package_name):
        """
        Return metadata of the artifacts built through this registry.
        """

        filename = self.metadata.get(package_name)
        if not filename or not exists(filename):
            return {}
        with open(filename, encoding='utf8') as fd:
            contents = fd.read()

        try:
            is_json_compat(contents)
        except ValueError:
            logger.info("artifact metadata file '%s' is invalid", filename)
            return {}

        return json.loads(contents)

    def generate_metadata_entry(self, entry_point, toolchain, spec):
        """
        After the toolchain and spec have been executed, this may be
        called to generate the artifact export entry for persistence
        into the metadata file.
        """

        export_target = spec['export_target']
        toolchain_bases = trace_toolchain(toolchain)
        toolchain_bin_path = spec.get(TOOLCHAIN_BIN_PATH)
        toolchain_bin = ([
            basename(toolchain_bin_path),  # bin_name
            get_bin_version_str(toolchain_bin_path),  # bin_version
        ] if toolchain_bin_path else [])

        return {basename(export_target): {
            'toolchain_bases': toolchain_bases,
            'toolchain_bin': toolchain_bin,
            'builder': '%s:%s' % (
                entry_point.module_name, '.'.join(entry_point.attrs)),
        }}

    def update_artifact_metadata(self, package_name, new_metadata):
        metadata = self.get_artifact_metadata(package_name)
        metadata_filename = self.metadata.get(package_name, NotImplemented)
        if metadata_filename is NotImplemented:
            logger.info(
                "package '%s' has not declare any artifacts; not applying "
                "updates to metadata information", package_name)
            return

        artifacts = metadata[ARTIFACT_BASENAME] = metadata.get(
            ARTIFACT_BASENAME, {})
        artifacts.update(new_metadata)
        metadata['versions'] = sorted(set(
            '%s' % i for i in find_packages_requirements_dists(
                [package_name])))

        with open(metadata_filename, 'w', encoding='utf8') as fd:
            json.dump(metadata, fd)

    def iter_records_for(self, package_name):
        """
        Iterate records for a specific package.
        """

        entry_points = self.packages.get(package_name, NotImplemented)
        if entry_points is NotImplemented:
            logger.debug(
                "package '%s' has not declared any entry points for the '%s' "
                "registry for artifact construction",
                package_name, self.registry_name,
            )
            return iter([])

        logger.debug(
            "package '%s' has declared %d entry points for the '%s' "
            "registry for artifact construction",
            package_name, len(entry_points), self.registry_name,
        )
        return iter(entry_points.values())

    def verify_builder(self, builder):
        return verify_builder(builder)

    def verify_export_target(self, export_target):
        # this is the pre-flight verification, it will prevent the
        # entry point loaded/associated with this export_target from
        # creating a builder entry in the iter_builders_for method.
        return True

    def setup_export_location(self, export_target):
        """
        This will be used by prepare_export_location; it must return True
        for the final export to proceed.
        """

        return setup_export_location(export_target)

    def prepare_export_location(self, export_target):
        """
        The wrapped version for this class for use directly by the spec
        in the before_prepare advice.  Must raise some kind of Toolchain
        specific exception to halt Toolchain execution for the given
        export target.
        """

        if not self.setup_export_location(export_target):
            raise ToolchainAbort()

    def extract_builder_result(self, builder_result):
        return extract_builder_result(builder_result)

    def iter_export_targets_for(self, package_name):
        for entry_point in self.iter_records_for(package_name):
            export_target = self.records[
                (entry_point.dist.project_name, entry_point.name)]

            yield entry_point, export_target

    def generate_builder(self, entry_point, export_target):
        """
        Yields exactly one builder if both the provided entry point and
        export target satisfies the checks required.
        """

        try:
            builder = entry_point.resolve()
        except ImportError:
            logger.error(
                "unable to import the target builder for the entry point "
                "'%s' from package '%s' to generate artifact '%s'",
                entry_point, entry_point.dist, export_target,
            )
            return

        if not self.verify_builder(builder):
            logger.error(
                "the builder referenced by the entry point '%s' "
                "from package '%s' has an incompatible signature",
                entry_point, entry_point.dist,
            )
            return

        # CLEANUP see deprecation notice below
        verifier = self.verify_export_target(export_target)
        if not verifier:
            logger.error(
                "the export target '%s' has been rejected", export_target)
            return

        toolchain, spec = self.extract_builder_result(builder(
            [entry_point.dist.project_name], export_target=export_target))
        if not toolchain:
            logger.error(
                "the builder referenced by the entry point '%s' "
                "from package '%s' failed to produce a valid "
                "toolchain",
                entry_point, entry_point.dist,
            )
            return

        if spec.get(EXPORT_TARGET) != export_target:
            logger.error(
                "the builder referenced by the entry point '%s' "
                "from package '%s' failed to produce a spec with the "
                "expected export_target",
                entry_point, entry_point.dist,
            )
            return

        if callable(verifier):
            warnings.warn(
                "%s:%s.verify_export_target returned a callable, which "
                "will no longer be passed to spec.advise by calmjs-4.0.0; "
                "please instead override 'setup_export_location' or "
                "'prepare_export_location' in that class" % (
                    self.__class__.__module__, self.__class__.__name__),
                DeprecationWarning
            )
            spec.advise(BEFORE_PREPARE, verifier, export_target)
        else:
            spec.advise(
                BEFORE_PREPARE,
                self.prepare_export_location, export_target)
        yield entry_point, toolchain, spec

    def iter_builders_for(self, package_name):
        for entry_point, export_target in self.iter_export_targets_for(
                package_name):
            # yield from...
            for builder in self.generate_builder(entry_point, export_target):
                yield builder

    def execute_builder(self, entry_point, toolchain, spec):
        """
        Accepts the arguments provided by the builder and executes them.
        """

        toolchain(spec)
        if not exists(spec['export_target']):
            logger.error(
                "the entry point '%s' from package '%s' failed to "
                "generate an artifact at '%s'",
                entry_point, entry_point.dist, spec['export_target']
            )
            return {}
        return self.generate_metadata_entry(entry_point, toolchain, spec)

    def process_package(self, package_name):
        results = {}
        for builder in self.iter_builders_for(package_name):
            results.update(self.execute_builder(*builder))
        return results


class ArtifactRegistry(BaseArtifactRegistry):
    """
    A registry to allow a central place for Python packages to declare
    which method to generate the artifact and what name to use.
    """

    def process_package(self, package_name):
        """
        Build artifacts declared for the given package.
        """

        metadata = super(ArtifactRegistry, self).process_package(package_name)
        if metadata:
            self.update_artifact_metadata(package_name, metadata)


class ArtifactBuilder(object):
    """
    A generic artifact builder.  Provides a callable object that will
    accept a list of package_names to generate prebuilt artifacts for
    based on the registry name used to construct this builder instance.
    """

    def __init__(self, registry_name=ARTIFACT_REGISTRY_NAME):
        """
        Arguments:

        registry_name
            the registry used to generate the artifacts for.
        """

        self.registry_name = registry_name

    def __call__(self, package_names):
        """
        Generic artifact builder function.

        Arguments:

        package_names
            List of package names to be built

        Returns True if the build is successful without errors, False if
        errors were found or if no artifacts were built.
        """

        result = True
        registry = get(self.registry_name)
        for package_name in package_names:
            metadata = {}
            for entry_point, export_target in registry.iter_export_targets_for(
                    package_name):
                builder = next(registry.generate_builder(
                    entry_point, export_target), None)
                if not builder:
                    # immediate failure if builder does not exist.
                    result = False
                    continue
                entries = registry.execute_builder(*builder)
                # whether the builder produced an artifact entry.
                result = bool(entries) and result
                metadata.update(entries)
            # whether the package as a whole produced artifacts entries.
            result = bool(metadata) and result
            registry.update_artifact_metadata(package_name, metadata)
        return result


class build_calmjs_artifacts(BuildArtifactCommand):
    """
    The main artifact build command for calmjs
    """

    artifact_builder = ArtifactBuilder(registry_name=ARTIFACT_REGISTRY_NAME)
