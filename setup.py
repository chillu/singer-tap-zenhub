#!/usr/bin/env python
from setuptools import setup

setup(
    name="tap-zenhub",
    version="0.1.0",
    description="Singer.io tap for extracting data from Zenhub",
    author="Ingo Schommer, SilverStripe Ltd",
    url="http://singer.io",
    classifiers=["Programming Language :: Python :: 3 :: Only"],
    py_modules=["tap_zenhub"],
    install_requires=[
        "singer-python>=5.0.12",
        "requests",
        "pendulum"
    ],
    entry_points="""
    [console_scripts]
    tap-zenhub=tap_zenhub:main
    """,
    packages=["tap_zenhub"],
    package_data = {
        "schemas": ["tap_zenhub/schemas/*.json"]
    },
    include_package_data=True,
)
