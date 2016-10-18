# -*- coding: utf-8 -*-
"""
This is standalone to provide a stable location/callstack layout for
testing purposes.
"""


def apply_spec_advise_fault(spec, advice_name):
    def fault():
        raise Exception('an exception')
    spec.advise(advice_name, fault)


def create_spec_advise_fault(spec, advice_name):
    apply_spec_advise_fault(spec, advice_name)
