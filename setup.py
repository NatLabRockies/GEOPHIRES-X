#!/usr/bin/env python
import re
from pathlib import Path

from setuptools import find_packages
from setuptools import setup


def read(*names, **kwargs):
    with Path(__file__).parent.joinpath(*names).open(encoding=kwargs.get('encoding', 'utf8')) as fh:
        return fh.read()


setup(
    name='geophires-x',
    version='3.11.12',
    license='MIT',
    description='GEOPHIRES is a free and open-source geothermal techno-economic simulator.',
    long_description='{}\n{}'.format(
        re.compile('^.. start-badges.*^.. end-badges', re.M | re.S).sub('', read('README.rst')),
        re.sub(':[a-z]+:`~?(.*?)`', r'``\1``', read('CHANGELOG.rst')),
    ),
    author='NREL',
    author_email='Koenraad.Beckers@nrel.gov',
    url='https://github.com/NREL/GEOPHIRES-X',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    py_modules=[path.stem for path in Path('src').glob('*.py')],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Unix',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        # uncomment if you test on these interpreters:
        # "Programming Language :: Python :: Implementation :: IronPython",
        # "Programming Language :: Python :: Implementation :: Jython",
        # "Programming Language :: Python :: Implementation :: Stackless",
        'Topic :: Utilities',
        'Private :: Do Not Upload',
    ],
    project_urls={
        'Changelog': 'https://github.com/NREL/GEOPHIRES-X/blob/master/CHANGELOG.rst',
        'Issue Tracker': 'https://github.com/NREL/GEOPHIRES-X/issues',
        'Documentation': 'https://nrel.github.io/GEOPHIRES-X/',
    },
    keywords=['geothermal'],
    python_requires='>=3.8',
    install_requires=[
        'numpy==1.24; python_version == "3.8"',  # Last version compatible with Python 3.8
        'numpy; python_version > "3.8"',
        'numpy-financial',
        'pint',
        'forex_python',
        'jsons',
        'mpmath',
        'deepdiff',
        'mysql.connector',
        'cryptography',
        'pandas',
        'matplotlib',
        # Used by Adv*/AGS extensions; may break tox pypy jobs if those are re-enabled
        'h5py',
        'scipy',
        'iapws',
        # coolprop 7.0.0 fails on macOS + Python > 3.8, see
        # https://github.com/softwareengineerprogrammer/GEOPHIRES/actions/runs/16888333182/job/47841807973
        'coolprop == 6.8.0; python_version > "3.8"',
        # coolprop > 6.7.0 fails on Python 3.8, see
        # https://github.com/softwareengineerprogrammer/GEOPHIRES/actions/runs/14599234458/job/40952924048?pr=69#step:5:302
        'coolprop==6.7.0; python_version == "3.8"',
        'rich',
        'pylocker',
        'nrel-pysam',
        'tabulate',
    ],
    extras_require={
        # eg:
        #   "rst": ["docutils>=0.11"],
        #   ":python_version=="2.6"": ["argparse"],
        'development': ['bumpversion', 'sphinx_py3doc_enhanced_theme']
    },
)
