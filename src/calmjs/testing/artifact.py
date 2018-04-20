# -*- coding: utf-8 -*-
from __future__ import absolute_import

from calmjs.toolchain import Spec
from calmjs.toolchain import NullToolchain
from calmjs.toolchain import TOOLCHAIN_BIN_PATH


class ArtifactToolchain(NullToolchain):

    def link(self, spec):
        spec[TOOLCHAIN_BIN_PATH] = 'artifact'
        if spec.get('force_fail'):
            return
        with open(spec['export_target'], 'w') as fd:
            fd.write('\n'.join(spec['package_names']))


# the generic builder
def generic_builder(package_names, export_target):
    return ArtifactToolchain(), Spec(
        package_names=package_names,
        export_target=export_target,
    )


def fail_builder(package_names, export_target):
    return ArtifactToolchain(), Spec(
        package_names=package_names,
        export_target=export_target,
        force_fail=True,
    )
