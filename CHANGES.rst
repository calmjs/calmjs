Changelog
=========

2.0.0 (Unreleased)
------------------

- Expose the indexer module functions mapper and modgen as public.
- Completely refactored the Toolchain class to have much more consistent
  method naming convention and argument lists.
- The compile method now reads from an instance specific list of methods
  which allow very customizable compilation steps.
- Specific ways for a toolchain to skip specific names based.

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
