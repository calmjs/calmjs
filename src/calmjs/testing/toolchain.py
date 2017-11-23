# -*- coding: utf-8 -*-
from __future__ import absolute_import

from calmjs.toolchain import NullToolchain
from calmjs.toolchain import TOOLCHAIN_BIN_PATH


class ArtifactToolchain(NullToolchain):

    def link(self, spec):
        spec[TOOLCHAIN_BIN_PATH] = 'artifact'
        with open(spec['export_target'], 'w') as fd:
            fd.write('\n'.join(spec['package_names']))
