Changelog
=========

3.2.1 (2018-05-16)
------------------

- Pack related helpers for specific sets of package metadata files into
  functions that return them.  Naturally existing ones are provided,
  with the keys/filenames parameterized for reuse by dependants. [
  `#43 <https://github.com/calmjs/calmjs/issues/43>`_
  ]
- Use the ``ast`` module for parsing the es5 String Node value instead
  of the unicode-escape method as it encompasses more cases, including
  the line continuation escape sequence which can show up. [
  `#44 <https://github.com/calmjs/calmjs/issues/44>`_
  ]

3.1.0 (2018-04-30)
------------------

- Fix the modgen function in calmjs.indexer by actually not using the
  marked as deprecated indexer functions by default, but instead use the
  ``pkg_resources`` version as originally intended. [
  `#30 <https://github.com/calmjs/calmjs/issues/30>`_
  `#33 <https://github.com/calmjs/calmjs/issues/33>`_
  ]
- Ensure lookups on package names that have been normalized internally
  by pkg_resources can still be resolved by their original name. [
  `#31 <https://github.com/calmjs/calmjs/issues/31>`_
  ]
- Correctly return an unsuccessful exit code on various partial success
  while running ``calmjs artifact build`` command and for the distutils
  ``build_calmjs_artifacts`` command. [
  `#27 <https://github.com/calmjs/calmjs/issues/27>`_
  `#38 <https://github.com/calmjs/calmjs/issues/38>`_
  ]
- Correctly locate the subparser(s) that were responsible for whatever
  arguments they cannot recognize; includes cleaning up the interactions
  between the runtime and argparser classes and Python 3.7 compatibility
  fixes. [
  `#41 <https://github.com/calmjs/calmjs/issues/41>`_
  ]
- Fix handling of working directory flag as the validation should be
  done in the beginning rather than later.  Also clean up various
  logging/error messages surrounding that, plus a fix to toolchain test
  case isolation.  Note that downstream packages that did not set up the
  export target as an absolute part will result in a warning. [
  `#42 <https://github.com/calmjs/calmjs/issues/42>`_
  ]

3.0.0 (2018-01-10)
------------------

- The ``yarn`` subcommand is now provided as an alternative to ``npm``.
- Also decreased the log verbosity during the bootstrap runtime stage,
  so that for systems that don't have the required binaries available,
  the default ``calmjs`` command won't show those pile of warnings for
  that (increasing verbosity with ``-v`` will restore those warnings).
- Some confusing internal (but public) identifiers which are used in the
  Toolchain and Spec system have been renamed to better reflect their
  intended use and purpose.  Deprecation code is applied to aid
  transition, and these will be removed in 4.0.0.

  - For ``Spec``:

    - ``*_source_map`` -> ``*_sourcepath`` (except for the key that really
      amplified the confusion which was ``generate_source_map``)
    - ``*_targets`` -> ``*_targetpaths`` (to be consistent with paths on
      the filesystem).

  - On the ``Toolchain``, for the similar reasons as above:

    - ``sourcemap_suffix`` -> ``sourcepath_suffix``
    - ``target_suffix`` -> ``targetpath_suffix``

- Changed the order of binary resolution for Driver instances with
  configured NODE_PATH and current working directory to align with how
  Node.js inject them internally (in ``module.paths``, current working
  directory has higher order of precedence over NODE_PATH), for the
  method ``BaseDriver.find_node_modules_basedir``.
- Framework for predefined artifact generation for packages through the
  ``calmjs.artifacts`` registry.
- Also split off the directory resolution from the above method to
  ``BaseDriver.which_with_node_modules``.
- Deprecated the existing toolchain.transpiler function as a standard
  callable.  The new version must be an instance of ``BaseUnparser``
  provided by the ``calmjs.parse`` package.  The NullToolchain will
  retain the usage of the legacy transpiler.
- Generation of the full transpile targetpaths will be normalized.  Note
  that targetpath is still toolchain specific.
- Removed most of the ``vlqsm`` module as the functionality is now
  provided by ``calmjs.parse.vlq`` and ``calmjs.parse.sourcemap``.  Only
  the legacy ``SourceWriter`` class remain, which is deprecated.
- Provide generic first class support for loader plugins, such that
  downstream packages should no longer need to explicitly declare
  ``extras_calmjs`` to specify the location of loaders for all the
  different toolchains (which inevitably collide and cause conflicts).
  Toolchains downstream will need to implement support for this.
- Artifact production support, including integration with setuptools.

2.1.0 (2016-11-29)
------------------

- Namespace packages that have a module explicitly provided should still
  be able to be looked up if a valid entry point is provided; naturally
  if the module isn't declared correctly then the behavior remains
  unchanged (github issue #5)
- Name field in ``package.json`` should contain project names standard
  to Node.js, i.e. if extras are specified, it should be stripped.  This
  is done so that that ``npm`` will not choke on it with a warning and
  die. (github issue #4)

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
