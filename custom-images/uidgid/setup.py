#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

def load_requirements(filename):
    with open(filename) as file:
        return file.read().splitlines()

requirements = load_requirements("requirements.txt")

test_requirements = load_requirements("test_requirements.txt")

setup(
    author="Octarine",
    author_email='none',
    python_requires='>=3.9',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    description="Manages UNIX user/group names and ids for JupyterHub based on alternate identities provided by upstream ssystems like AD/ADX and Proper.",
    install_requires=requirements,
    license="none",
    long_description=readme,
    include_package_data=True,
    keywords='uidgid',
    name='uidgid',
    packages=find_packages(include=['uidgid', 'uidgid.*']),
    test_suite='tests',
    tests_require=test_requirements,
    extras_require = {
        "test": test_requirements,
    },
    url='none',
    version='0.1.0',
    zip_safe=False,
)
