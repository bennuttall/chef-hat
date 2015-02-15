import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="chef_hat",
    version="0.0.0",
    author="Ben Nuttall",
    author_email="ben@raspberrypi.org",
    description="Sous vide cooking with the Raspberry Pi",
    license="BSD",
    keywords=[
        "chef hat",
        "sous vide",
        "raspberrypi",
    ],
    url="https://github.com/bennuttall/chef-hat",
    packages=[
        "chef_hat",
    ],
    install_requires=[
        "RPi.GPIO",
        "energenie",
        "w1thermsensor",
    ],
    long_description=read('README.rst'),
    classifiers=[
        "Development Status :: 1 - Planning",
        "Topic :: Home Automation",
        "License :: OSI Approved :: BSD License",
    ],
)
