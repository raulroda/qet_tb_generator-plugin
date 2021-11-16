# Always prefer setuptools over distutils
from setuptools import setup, find_packages
from codecs import open
from os import path

setup(
    name="qet_tb_generator",
    version="1.3.0",
    description="Script that generates terminal blocks & connectors for QElectroTech",
    long_description = """Allows to generate terminal blocks and connectors for QElectroTech electrical diagram software.""",
    author="Raul Roda",
    author_email="raulroda8@gmail.com",
    #url="www.something.com",
    license='GPL',

    packages=find_packages(),
    #packages=['src'],
    include_package_data=True,
    package_data={'templates' : ['borne.elmt']},

                                       #name_of_executable = folder.module:function_to_execute
    entry_points={'console_scripts': ['qet_tb_generator=src.main:main']},
    install_requires=['PySimpleGUI'],
    keywords='qelectrotech terminal block electric',

    classifiers=[
    # How mature is this project? Common values are
    #   3 - Alpha
    #   4 - Beta
    #   5 - Production/Stable
    'Development Status :: 4 - Beta',
    'Environment :: Win32 (MS Windows)',
    'Environment :: X11 Applications :: Qt',
    'Environment :: MacOS X',
    'Intended Audience :: End Users/Desktop',
    # Pick your license as you wish (should match "license" above)
     'License :: OSI Approved :: GNU General Public License (GPL)',
    # Specify the Python versions you support here. In particular, ensure
    # that you indicate whether you support Python 2, Python 3 or both.
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Natural Language :: English',
    'Topic :: Scientific/Engineering'],
)
