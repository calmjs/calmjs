# -*- coding: utf-8 -*-
"""
Registry framework for calmjs

This intends to be an extensible, pluggable registry system for the
calmjs infrastructure that leverages on the underlying setuptools entry
point system.
"""

from __future__ import absolute_import
import logging

from calmjs.base import BaseRegistry
from calmjs.base import BaseModuleRegistry
from calmjs.base import BaseChildModuleRegistry
from calmjs.indexer import mapper_es6
from calmjs.indexer import mapper_python

logger = logging.getLogger(__name__)


class ExtrasJsonKeysRegistry(BaseRegistry):
    """
    Python package may declare extra JSON information that will specify
    what they need from the packages they declared, and so package
    managers should declare the keys that those information should be
    supplied from, in order to give downstream packages a specific set
    of keys to merge.
    """

    def _init(self):
        self.keys = [ep.name for ep in self.raw_entry_points]

    def iter_records(self):
        for k in self.keys:
            yield k


class ModuleRegistry(BaseModuleRegistry):
    """
    A registry that tracks all JavaScript modules that have been shipped
    with Python modules within the running Python environment.

    Subclass can either override ``_init`` completely to specify its own
    mapper, or override `_map_entry_point_module`` and use the same
    mapper but modify its results before returning for usage by parent
    class.

    This is to be registered in calmjs.registry entry point as
    ``calmjs.module``.
    """

    def _init(self):
        self.mapper = mapper_es6

    def _map_entry_point_module(self, entry_point, module):
        return {module.__name__: self.mapper(module, entry_point)}


class PythonicModuleRegistry(ModuleRegistry):
    """
    A registry that tracks all JavaScript modules that have been shipped
    with Python modules within the running Python environment, with the
    modules exported using Pythonic namespace style.

    This is to be registered in calmjs.registry entry point as
    ``calmjs.module.pythonic``.
    """

    def _init(self):
        self.mapper = mapper_python


def resolve_child_module_registries_lineage(registry):
    """
    For a given child module registry, attempt to resolve the lineage.

    Return an iterator, yielding from parent down to the input registry,
    inclusive of the input registry.
    """

    children = [registry]
    while isinstance(registry, BaseChildModuleRegistry):
        if registry.parent in children:
            # this should never normally occur under normal usage where
            # classes have been properly subclassed with methods defined
            # to specificiation and with standard entry point usage, but
            # non-standard definitions/usage can definitely trigger this
            # self-referential loop.
            raise TypeError(
                "registry '%s' was already recorded in the lineage, "
                "indicating that it may be some (grand)child of itself, which "
                "is an illegal reference in the registry system; previously "
                "resolved lineage is: %r" % (registry.parent.registry_name, [
                    r.registry_name for r in reversed(children)
                ])
            )

        pl = len(registry.parent.registry_name)
        if len(registry.parent.registry_name) > len(registry.registry_name):
            logger.warning(
                "the parent registry '%s' somehow has a longer name than its "
                "child registry '%s'; the underlying registry class may be "
                "constructed in an invalid manner",
                registry.parent.registry_name,
                registry.registry_name,
            )
        elif registry.registry_name[:pl] != registry.parent.registry_name:
            logger.warning(
                "child registry '%s' does not share the same common prefix as "
                "its parent registry '%s'; there may be errors with how the "
                "related registries are set up or constructed",
                registry.registry_name,
                registry.parent.registry_name,
            )
        children.append(registry.parent)
        registry = registry.parent
    # the lineage down from parent to child.
    return iter(reversed(children))
