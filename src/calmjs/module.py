# -*- coding: utf-8 -*-
"""
Registry framework for calmjs

This intends to be an extensible, pluggable registry system for the
calmjs infrastructure that leverages on the underlying setuptools entry
point system.
"""

from logging import getLogger

from calmjs.base import BaseRegistry
from calmjs.base import BaseModuleRegistry
from calmjs.indexer import mapper_es6
from calmjs.indexer import mapper_python

logger = getLogger(__name__)


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
    mapper, or subclass `_register_entry_point_module`` and use the same
    mapper but modify its results before assigment to ``self.records``.

    This is to be registered in calmjs.registry entry point as
    ``calmjs.module``.
    """

    def _init(self):
        self.mapper = mapper_es6

    def _register_entry_point_module(self, entry_point, module):
        self.records[module.__name__] = self.mapper(module)


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
