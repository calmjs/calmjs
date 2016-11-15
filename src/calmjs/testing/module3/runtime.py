from inspect import currentframe
from inspect import getouterframes

from calmjs import runtime


class BadSimpleRuntime(runtime.DriverRuntime, runtime.Runtime):

    def entry_point_load_validated(self, entry_point):
        # skip the rest of the checks.
        return entry_point.load()

    def init_argparser(self, argparser):
        level = len(getouterframes(currentframe()))
        if level > self.recursionlimit:
            # turns out we need to emulate this to make pypy not
            # blow up coverage reporting; also make it die
            # quicker, and this emulation works good enough as
            # it turns out.
            raise RuntimeError('maximum recursion depth exceeded')
        super(BadSimpleRuntime, self).init_argparser(argparser)


class FakeBootstrapRuntime(runtime.BootstrapRuntime):
    pass


fake_bootstrap = FakeBootstrapRuntime()
