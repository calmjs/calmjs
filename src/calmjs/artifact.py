# -*- coding: utf-8 -*-
"""
Classes for tracking of built artifacts.
"""

from __future__ import absolute_import

from os.path import join

from calmjs.base import BaseRegistry
from calmjs.dist import find_packages_requirements_dists
from calmjs.dist import pkg_names_to_dists

ARTIFACT_BASENAME = 'calmjs_artifacts'


class ArtifactRegistry(BaseRegistry):
    """
    A registry to allow a central place for Python packages to declare
    which method to generate the artifact and what name to use.
    """

    def _init(self):
        self.packages = {}
        # for storing builders that are assumed to be compatible due to
        # their identical attribute names.
        self.compat_builders = {}
        # TODO determine if the full import name lookup table is
        # required.
        # self.builders = {}

        for ep in self.raw_entry_points:
            # the expected path to the artifact.
            path = join(ep.dist.egg_info, ARTIFACT_BASENAME, ep.name)

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

    def iter_records(self):
        # not especially useful, but implementing for completeness.
        for k in self.records.keys():
            yield k

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
