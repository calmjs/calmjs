Changelog
=========

2.0.0 (2016-11-16)
------------------

- Expose the indexer module functions mapper and modgen as public.
- Completely refactored the Toolchain class to have much more consistent
  method naming convention and argument lists.
- The compile method now reads from an instance specific list of methods
  which allow very customizable compilation steps.
- Specific ways for a toolchain to skip specific names based.
- Fixed copying of bundle sources to targets nested in subdirectories.
- The ``Spec`` callback system is now renamed to advice system and more
  comprehensively implemented; every step within the toolchain will
  execute advices before and after for each respective step that have
  been registered under the matching identifiers.  The identifiers for
  advices are are formalized as constants that can be imported from the
  ``calmjs.toolchain`` module.
- The advice system has dedicated exceptions which can be raised to
  signal an abort or cleanly stop a run.
- A couple spec keys were formalized, which are BUILD_DIR and
  CONFIG_JS_FILES, reserved for the build directory and marking out
  configuration JavaScript files.
- On a successful toolchain call, all advices registered to the spec
  under the key ``calmjs.toolchain.SUCCESS`` will now be invoked.
- Dedicated runtime provided for ``Toolchain`` subclasses, joining the
  ranks of a few other ``BaseDriver`` subclasses.  This is implemented
  as ``calmjs.runtime.ToolchainRuntime``.
- ``calmjs.runtime.Runtime`` can be subclassed and nested as it will now
  nest all ``BaseRuntime``.  Also the ``init`` method is removed, just
  use ``__init__`` and standard subclassing ``super`` usage rules.
- The default ``ArgumentParser`` instance for every ``Runtime`` will no
  longer be created until accessed, as it is now a property.
- Provide a way for packages to declare the primary module registry or
  registries it declared packages for through a new setup keyword
  ``calmjs_module_registry``, if required and desired.
- The default set of module registry names have been changed.  Registry
  ``calmjs.pythonic`` is renamed to ``calmjs.py.module``; the related
  testing related registry is renamed to include the full name of its
  implied target.
- Reserved a small set of core (already defined) registries for the
  calmjs framework, which is formally defined and enforce by the
  registry itself.
- Corrected interactive-mode detection.
- Helpers for source map generation for simple transpilation.

1.0.3 (2016-09-07)
------------------

- Fixed the issue with bad environmental variables for subprocess.Popen
  for Windows under Python 2.7.
- Other minor testing fixes on CI platforms.

1.0.2 (2016-09-04)
------------------

- Fixed invocation of binaries on the Windows platform.
- Corrected some minor wording.

1.0.0 (2016-09-02)
------------------

- Initial release of the ``calmjs`` framework foundation.
- A cli runtime entry point is provided, named ``calmjs``.
- Provide core integration with ``npm`` and generation of
  ``package.json`` through the ``setuptools`` framework; this is
  accessible as a ``setuptool`` command or through ``calmjs`` runtime.
- Provide a registry framework for use within ``calmjs``.
- Provide core registries for registering packages for use by ``calmjs``
  through the predefined ``setuptools`` entry points and groups.
- Provide a cli tool driver framework for interacting with ``node`` and
  other Node.js based or other command line tools.
- Provide the base toolchain framework, built on top of the tool driver
  framework.
- Provide modules for doing integration testing for modules that build
  on top of the ``calmjs`` framework.
