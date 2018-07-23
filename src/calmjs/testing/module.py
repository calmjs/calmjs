# -*- coding: utf-8 -*-
from calmjs.base import BaseChildModuleRegistry


class ChildModuleRegistry(BaseChildModuleRegistry):
    def resolve_parent_registry_name(self, registry_name):
        return super(ChildModuleRegistry, self).resolve_parent_registry_name(
            registry_name, '.child')
