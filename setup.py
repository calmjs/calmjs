from setuptools import setup
from setuptools import find_packages

version = '2.0.0'

classifiers = """
Development Status :: 5 - Production/Stable
Environment :: Console
Framework :: Setuptools Plugin
Intended Audience :: Developers
License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)
Operating System :: OS Independent
Programming Language :: JavaScript
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3.3
Programming Language :: Python :: 3.4
Programming Language :: Python :: 3.5
""".strip().splitlines()

setup(
    name='calmjs',
    version=version,
    description="Toolchain for deploying JavaScript with Python modules.",
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
    zip_safe=True,
    install_requires=[
        'setuptools>=12',
    ],
    include_package_data=True,
    python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*',
    entry_points={
        'console_scripts': [
            'calmjs = calmjs.runtime:main',
        ],
        'calmjs.runtime': [
            'npm = calmjs.npm:npm.runtime',
        ],
        'distutils.commands': [
            'npm = calmjs.npm:npm',
        ],
        'distutils.setup_keywords': [
            'package_json = calmjs.dist:validate_json_field',
            'extras_calmjs = calmjs.dist:validate_json_field',
            'calmjs_module_registry = calmjs.dist:validate_line_list',
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

            'calmjs.extras_keys = calmjs.module:ExtrasJsonKeysRegistry',
            'calmjs.module = calmjs.module:ModuleRegistry',
            'calmjs.module.tests = calmjs.module:ModuleRegistry',
            'calmjs.py.module = calmjs.module:PythonicModuleRegistry',
            'calmjs.py.module.tests = calmjs.module:PythonicModuleRegistry',
            'calmjs.toolchain.advice = calmjs.toolchain:AdviceRegistry',
        ],
        'calmjs.reserved': [
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
        ]
    },
    test_suite="calmjs.tests.make_suite",
)
