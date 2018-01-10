from setuptools import setup
from setuptools import find_packages

version = '3.1.0'

classifiers = """
Development Status :: 5 - Production/Stable
Environment :: Console
Environment :: Plugins
Framework :: Setuptools Plugin
Intended Audience :: Developers
License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)
Operating System :: MacOS :: MacOS X
Operating System :: Microsoft :: Windows
Operating System :: POSIX
Operating System :: POSIX :: BSD
Operating System :: POSIX :: Linux
Operating System :: OS Independent
Programming Language :: JavaScript
Programming Language :: Python
Programming Language :: Python :: 2
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3
Programming Language :: Python :: 3.3
Programming Language :: Python :: 3.4
Programming Language :: Python :: 3.5
Programming Language :: Python :: 3.6
Programming Language :: Python :: Implementation :: CPython
Programming Language :: Python :: Implementation :: PyPy
Topic :: Software Development :: Build Tools
Topic :: Software Development :: Libraries
Topic :: System :: Software Distribution
Topic :: Utilities
""".strip().splitlines()

setup(
    name='calmjs',
    version=version,
    description=(
        'A Python framework for building toolchains and utilities for working '
        'with the Node.js ecosystem from within a Python environment.'
    ),
    long_description=(
        open('README.rst').read() + "\n" +
        open('CHANGES.rst').read()
    ),
    classifiers=classifiers,
    keywords='',
    author='Tommy Yu',
    author_email='tommy.yu@auckland.ac.nz',
    url='https://github.com/calmjs/',
    license='GPL',
    packages=find_packages('src', exclude=['ez_setup']),
    package_dir={'': 'src'},
    namespace_packages=['calmjs'],
    zip_safe=False,
    install_requires=[
        'setuptools>=12',
        'calmjs.types',
        'calmjs.parse>=1.0.0,<2',
    ],
    include_package_data=True,
    python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*',
    entry_points={
        'console_scripts': [
            'calmjs = calmjs.runtime:main',
        ],
        'calmjs.runtime': [
            'artifact = calmjs.runtime:artifact',
            'npm = calmjs.npm:npm.runtime',
            'yarn = calmjs.yarn:yarn.runtime',
        ],
        'calmjs.runtime.artifact': [
            'build = calmjs.runtime:artifact_build',
        ],
        'distutils.commands': [
            'npm = calmjs.npm:npm',
            'yarn = calmjs.yarn:yarn',
            'build_calmjs_artifacts = calmjs.artifact:build_calmjs_artifacts',
        ],
        'distutils.setup_keywords': [
            'package_json = calmjs.dist:validate_json_field',
            'extras_calmjs = calmjs.dist:validate_json_field',
            'calmjs_module_registry = calmjs.dist:validate_line_list',
            'build_calmjs_artifacts = calmjs.dist:build_calmjs_artifacts',
        ],
        'egg_info.writers': [
            'package.json = calmjs.npm:write_package_json',
            'extras_calmjs.json = calmjs.dist:write_extras_calmjs',
            ('calmjs_module_registry.txt = '
                'calmjs.dist:write_module_registry_names'),
        ],
        'calmjs.extras_keys': [
            'node_modules = enabled',
        ],
        'calmjs.registry': [
            'calmjs.registry = calmjs.registry:Registry',

            'calmjs.artifacts = calmjs.artifact:ArtifactRegistry',
            'calmjs.extras_keys = calmjs.module:ExtrasJsonKeysRegistry',
            'calmjs.module = calmjs.module:ModuleRegistry',
            'calmjs.module.tests = calmjs.module:ModuleRegistry',
            'calmjs.py.module = calmjs.module:PythonicModuleRegistry',
            'calmjs.py.module.tests = calmjs.module:PythonicModuleRegistry',
            'calmjs.toolchain.advice = calmjs.toolchain:AdviceRegistry',
        ],
        'calmjs.reserved': [
            'calmjs.artifacts = calmjs',
            'calmjs.artifacts.tests = calmjs.dev',
            'calmjs.dev.module = calmjs.dev',
            'calmjs.dev.module.tests = calmjs.dev',
            'calmjs.extras_keys = calmjs',
            'calmjs.module = calmjs',
            'calmjs.module.tests = calmjs',
            'calmjs.registry = calmjs',
            'calmjs.reserved = calmjs',
            'calmjs.py.module = calmjs',
            'calmjs.py.module.tests = calmjs',
            'calmjs.toolchain.advice = calmjs',
        ],
        'calmjs.toolchain.advice': [
            'calmjs.toolchain:Toolchain = calmjs.toolchain:debugger',
        ],
    },
    test_suite="calmjs.tests.make_suite",
)
