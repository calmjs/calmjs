# -*- coding: utf-8 -*-
"""
This is standalone to provide a stable location/callstack layout for
testing purposes.
"""

from os.path import exists


def apply_spec_advise_fault(spec, advice_name):
    def fault():
        raise Exception('an exception')
    spec.advise(advice_name, fault)


def create_spec_advise_fault(spec, advice_name):
    apply_spec_advise_fault(spec, advice_name)


def advice_order(spec, extras):
    # doing import internally here to comply with the import rules for
    # this project/framework.
    from calmjs import toolchain

    def verify_build_dir():
        build_dir = spec.get('build_dir')
        if not build_dir or not exists(build_dir):
            # should NEVER be called.
            raise toolchain.ToolchainAbort()  # pragma: no cover

    spec.advise(toolchain.CLEANUP, verify_build_dir)


def advice_marker(spec, extras):
    # this documents the behavior if the implementation of a toolchain
    # advice that was registered had acted immediately on the spec
    from calmjs import toolchain

    spec.setdefault('marker_too_soon', [])
    spec['marker_too_soon'].append(
        (list(spec.get('advice_packages', [])), extras)
    )

    # to properly manage the process, it should register a function as
    # an advice.
    def advice():
        spec.setdefault('marker_delayed', [])
        spec['marker_delayed'].append(
            (list(spec.get('advice_packages', [])), extras)
        )

    spec.advise(toolchain.SETUP, advice)
