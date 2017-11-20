# -*- coding: utf-8 -*-
"""
Classes for tracking of built artifacts.
"""

from __future__ import absolute_import

from inspect import getcallargs
from logging import getLogger
from os.path import dirname
from os.path import exists
from os.path import isdir
from os.path import join
from os.path import normcase
from os import makedirs
from os import unlink

from calmjs.base import BaseRegistry
from calmjs.dist import find_packages_requirements_dists
from calmjs.dist import pkg_names_to_dists

ARTIFACT_BASENAME = 'calmjs_artifacts'

logger = getLogger(__name__)


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


class ArtifactRegistry(BaseRegistry):
    """
    A registry to allow a central place for Python packages to declare
    which method to generate the artifact and what name to use.
    """

    def _init(self):
        # default (self.records) is a map of package + name to path
        # this is the reverse lookup for that
        self.reverse = {}
        self.packages = {}
        # for storing builders that are assumed to be compatible due to
        # their identical attribute names.
        self.compat_builders = {}
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
                "entry point '%s' from package '%s' will generate an artifact "
                "at '%s' but it was already registered to entry point '%s'; "
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
        # compat name for Python packages.
        cb_key = '.'.join(ep.attrs)
        cb = self.compat_builders[cb_key] = self.compat_builders.get(
            cb_key, {})
        cb[ep.dist.project_name] = path

        # standard get_artifact_filename lookup for standalone,
        # complete artifacts at some path.
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

        return self.records.get((package_name, artifact_name))

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

    def build_artifacts(self, package_name):
        """
        Build artifacts declared for the given package.
        """

        entry_points = self.packages.get(package_name, NotImplemented)
        if entry_points is NotImplemented:
            logger.debug(
                "package '%s' has not declared any entry points for the '%s' "
                "registry for artifact construction",
                package_name, self.registry_name,
            )
            return

        logger.debug(
            "package '%s' has declared %d entry points for the '%s' "
            "registry for artifact construction",
            package_name, len(entry_points), self.registry_name,
        )

        for ep in entry_points.values():
            try:
                builder = ep.resolve()
            except ImportError:
                logger.error(
                    "unable to import the target builder for the entry point "
                    "'%s' from package '%s'", ep, ep.dist,
                )
                continue

            export_target = self.records[(ep.dist.project_name, ep.name)]
            target_dir = dirname(export_target)
            if not exists(target_dir):
                makedirs(target_dir)
            elif not isdir(target_dir):
                logger.error(
                    "cannot export to '%s' as this target's parent is not a "
                    "directory", export_target
                )
                continue

            if not verify_builder(builder):
                logger.error(
                    "the builder referenced by the entry point '%s' "
                    "from package '%s' has an incompatible signature",
                    ep, ep.dist,
                )
                continue

            if exists(export_target):
                logger.debug(
                    "unlinking existing export target at '%s'", export_target)
                unlink(export_target)

            builder([ep.dist.project_name], export_target=export_target)

            if not exists(export_target):
                logger.error(
                    "the entry point '%s' from package '%s' failed to "
                    "generate an artifact at '%s'", ep, ep.dist, export_target
                )
