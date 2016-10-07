# -*- coding: utf-8 -*-
"""
This is standalone to provide a stable location/callstack layout for
testing purposes.
"""


def apply_spec_event_fault(spec, event):
    def fault():
        raise Exception('an exception')
    spec.on_event(event, fault)


def create_spec_event_fault(spec, event):
    apply_spec_event_fault(spec, event)
