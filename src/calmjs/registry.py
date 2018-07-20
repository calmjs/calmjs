# -*- coding: utf-8 -*-
"""
Registry of all registries for calmjs.

This module provides the implementation for working with the entry point
group ``calmjs.registry``, where it will be able to instantiate and
cache registries for the rest of the calmjs framework.

Typically, usage is done through this::

    >>> from calmjs.registry import get
    >>> calmjs_module = get('calmjs.module')
    >>> calmjs_module  # doctest: +ELLIPSIS
    <calmjs.module.ModuleRegistry object ...>
    >>> calmjs_module.iter_records()  # doctest: +ELLIPSIS
    <generator object ...>

The iter_records is typically used by the other parts of the calmjs
framework to produce configuration files and/or transpile the source
into the usable final form.
"""

from __future__ import absolute_import

from pkg_resources import working_set
from pkg_resources import Requirement

from logging import getLogger
from calmjs.base import BaseRegistry

logger = getLogger(__name__)

PACKAGE_NAME = 'calmjs'
CALMJS_RESERVED = 'calmjs.reserved'


class Registry(BaseRegistry):

    def __init__(
            self, registry_name,
            package_name=PACKAGE_NAME, reserved=CALMJS_RESERVED, *a, **kw):
        """
        The root registry will also track the undocumented working set
        specification
        """

        working_set_ = kw.get('_working_set') or working_set
        self.reserved = {}
        if reserved:
            dist = working_set_.find(Requirement.parse(package_name))
            if dist is None:
                logger.error(
                    "failed to set up registry_name reservations for "
                    "registry '%s', as the specified package '%s' could "
                    "not found in the current working_set; maybe it is not "
                    "correctly installed?", registry_name, package_name,
                )
            else:
                # module_name is the package_name in our context.
                self.reserved = {
                    k: v.module_name for k, v in dist.get_entry_map(
                        reserved).items()
                }
        super(Registry, self).__init__(registry_name, *a, **kw)

    def _init(self):
        """
        Turn the records into actual usable keys.
        """

        self._entry_points = {}
        for entry_point in self.raw_entry_points:
            if entry_point.dist.project_name != self.reserved.get(
                    entry_point.name, entry_point.dist.project_name):
                logger.error(
                    "registry '%s' for '%s' is reserved for package '%s'",
                    entry_point.name, self.registry_name,
                    self.reserved[entry_point.name],
                )
                continue

            if self.get_record(entry_point.name):
                logger.warning(
                    "registry '%s' for '%s' is already registered.",
                    entry_point.name, self.registry_name,
                )
                existing = self._entry_points[entry_point.name]
                logger.debug(
                    "registered '%s' from '%s'", existing, existing.dist)
                logger.debug(
                    "discarded '%s' from '%s'", entry_point, entry_point.dist)
                continue

            logger.debug(
                "recording '%s' from '%s'", entry_point, entry_point.dist)
            self._entry_points[entry_point.name] = entry_point

        # No pre-caching for below, let the get_record load things into
        # records on-demand.

    def get_record(self, name):
        if name in self.records:
            # maybe do some other sanity check if pedantic.
            logger.debug('found existing registry %s', name)
            return self.records[name]

        entry_point = self._entry_points.get(name)
        if not entry_point:
            logger.debug("'%s' does not resolve to a registry", name)
            return

        try:
            cls = entry_point.load()
        except ImportError:
            logger.debug(
                "ImportError '%s' from '%s'",
                entry_point, entry_point.dist)
            return

        if cls is type(self) and entry_point.name == self.registry_name:
            logger.debug(
                "registry '%s' has entry point '%s' which is the identity "
                "registration", name, entry_point,
            )
            self.records[name] = self
            return self

        logger.debug(
            "registering '%s' from '%s'", entry_point, entry_point.dist)
        try:
            self.records[name] = cls(name)
        except Exception:
            logger.exception(
                "'%s' from '%s' does not lead to a valid registry constructor",
                entry_point, entry_point.dist,
            )
            return
        return self.records[name]


# Initialize the root registry instance
_inst = Registry(__name__)  # __name__ == calmjs.registry


def get(registry_name):
    return _inst.get(registry_name)
