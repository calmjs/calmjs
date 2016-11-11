Module layout
=============

To give a guide on how modules should be laid out, in the case for other
packages that that may depend on ``calmjs`` for integration and other
uses, the following are how things are done here:

exc
    Generic exception classes specific for this project.

utils
    Utilities for use from within calmjs (maybe elsewhere).  Must NOT
    inherit from other calmjs modules.  As a result this is safe to be
    imported from any ``test_`` modules.

vlqsm
    VLQ and source map module.

argparse
    Extensions to the built-in ``argparse`` module.  Due to this name,
    ``absolute_import`` must be used.

base
    Module providing Base* classes.  Should only inherit from utils and
    nothing else.

ui
    For functions and classes that provide user interfacing features,
    including constants that are used for rendering output to logs and
    users.  The interactive mode features are typically reserved for
    usage by the runtime module, although often other modules may use
    provide references to functions here as default callbacks.

registry
    Root registry class.  Inherits from base.  Should not inherit from
    anything else.

indexer
    Contains a microregistry and a number of functions for generation
    of mappings of files within modules in Python packages for the
    purpose of exporting the paths of the JavaScript sources they hold.
    Shouldn't really need expanding or shouldn't need to inherit from
    calmjs.

module
    Defines module related registries, uses the indexer to generate the
    module path mapping entries.

dist
    Module that interfaces with distutils/setuptools in order to provide
    functions for dealing with distributions (i.e. dependencies and
    requirements for packages).  Should not really inherit from
    anything, however it is done for the core registry stuff which
    provides the functions that interfaces with the registry system that
    setuptools provide.

toolchain
    The exported primitive of this project.  Provides the skeleton
    Toolchain class for other packages to extend upon.  While some
    toolchain modules might provide cli interfacing functionalities,
    they should not inherit from cli as this is not the module that will
    provide the user facing entry points.

cli
    Module that provides the functions that call out to cli tools that
    will support the functionality needed by the calmjs framework.
    Provides the expanded driver classes for interfacing with Node.js
    and its tools, and also the primitive exposed functions that provide
    its own shell.  This latter part could be exposed as the runtime
    library.

runtime
    The module that provides the classes and functions that aid with
    providing the entry point into calmjs from cli and elsewhere.
    Supports the generation of the texts for users from the shell.

command
    Provides the primitive package manager command.  While it doesn't
    really inherit from anything here, implementations will likely
    inherit from dist for helpers, cli for the actual cli interfacing
    part for the underlying binary for the command, and runtime for the
    help tests.  The classes will hold onto an instance of a cli Driver
    and also the appropriate runtime constructed using that.

npm
    The npm specific tools.  Whole module can in theory be generated
    from code, however without the source users will be lost.  So that's
    done like so for the integrated thing that could inherit from
    anything.

As a general rule, a module should not inherit from modules listed below
their respective position on the above list.
