from setuptools import setup
from setuptools import find_packages

version = '1.0.0'

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
    long_description=open('README.rst').read(),
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
        'setuptools>=11.3',
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
        ],
        'egg_info.writers': [
            'package.json = calmjs.npm:write_package_json',
            'extras_calmjs.json = calmjs.dist:write_extras_calmjs',
        ],
        'calmjs.extras_keys': [
            'node_modules = enabled',
        ],
        'calmjs.registry': [
            'calmjs.extras_keys = calmjs.module:ExtrasJsonKeysRegistry',
            'calmjs.registry = calmjs.registry:Registry',
            'calmjs.module = calmjs.module:ModuleRegistry',
            'calmjs.module.pythonic = calmjs.module:PythonicModuleRegistry',
            'calmjs.tests = calmjs.module:ModuleRegistry',
            'calmjs.tests.pythonic = calmjs.module:PythonicModuleRegistry',
        ],
    },
    test_suite="calmjs.tests.make_suite",
)
