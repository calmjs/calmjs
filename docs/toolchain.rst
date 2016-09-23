Toolchain
=========

The toolchain module and class is another fundament piece of the calmjs
framework, a way to jumpstart integration of a tool into Python (so I
supposed the js part could stand for that instead of JavaScript).

Firstly though, there is the ``Spec``.  The ``Spec`` class is an
orchestration object really a dictionary that has a helper method that
is like ``dict.update`` except it takes in a list of selected keys.  The
other bit is that it has callback handling which is useful for doing
things later such as cleaning up temporary directory, and the method
``add_callback`` does what it says, it will take in a ``name`` argument
for grouping up callbacks into groups, so that when ``do_callbacks`` is
invoked all the callables for the group will be called in the reverse
order they were added.

Then there is the ``Toolchain`` class.  The key thing needed is that the
methods ``assemble`` and ``link`` are unimplemented and they need to be
done for an implementation to work.  The ``assemble`` method is used for
assembling a configuration file or something that the target tool
supports so that it will understand how to turn everything in the build
directory into the final desired artifact file.  That final process is
to be implemented through ``link``, which typically involves calling
some external executable.

For more detailed documentation, please refer to the interactive help
within the Python console.
