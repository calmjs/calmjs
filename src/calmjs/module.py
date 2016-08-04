# -*- coding: utf-8 -*-
"""
Registry framework for calmjs

This intends to be an extensible, pluggable registry system for the
calmjs infrastructure that leverages on the underlying setuptools entry
point system.
"""

from logging import getLogger

from calmjs.base import BaseModuleRegistry
from calmjs.indexer import mapper_es6
from calmjs.indexer import mapper_python

logger = getLogger(__name__)


class ModuleRegistry(BaseModuleRegistry):
    """
    A registry that tracks all JavaScript modules that have been shipped
    with Python modules within the running Python environment.
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
    """

    def _init(self):
        self.mapper = mapper_python
