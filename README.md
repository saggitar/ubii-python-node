# Ubi Interact Python Node

This project implements the [Ubi-Interact](https://github.com/SandroWeber/ubi-interact) Protocol in Pyhton.
Ubi Interact is a framework developed at TUM (Technical University of Munich) for developing distributed and reactive applications, the main focus
of the Python node is to allow the implementation of ``processing-modules`` in Python.

## Install requirements

### Python Version
The ``Ubi-Interact-Python-Node`` should be compatible with all python versions __>= 3.7__.
If you experience bugs feel free to report them, so I can get them fixed as soon as possible.
(To keep things simple all Python packages developed as part of the ``ubii`` namespace don't rely on any third party build tools such as ``poetry``, but instead
use the de-facto standard ``setuptools`` backend. This allows for editable installs, but makes it harder to correctly track all dependencies, leading to erorrs
which are hard to spot, but easy to fix :)

### Windows:
Python support for Windows has drastically improved, but some of the interesting computational packages are basically only usable on a Linux system. Nontheless the ``Ubi-Interact-Python-Node`` aims to be cross-platform. Installtion via ``pip`` is recommended, if you use something fancy (e.g. ``Anaconda``) refer to the documentation of your python distribution / package management tool how to install packages from pypi.

You can use the Windows python wrapper ``py.exe`` (detailed instructions in the [Python Documentation](https://docs.python.org/3/using/windows.html)) to
choose the python version of your environment.
 
   > :warning: If you plan to use a virtual environment - which is recommended - typically an _Unrestricted_ execution policy is needed to run the activation script for the python environment. The following instructions assume you are using _Powershell_, and have the right [_ExecutionPolicy_](https://docs.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies) set.

*  Python version 3.7 or greater
*  Virtual Environment (recommended) with pip installed (``py -m venv env`` followed by ``./env/Scripts/activate.ps1``)
* Continue at [PyPi](#pypi)

### Linux (and MacOS)
If you are not using Windows, you probably have a working python installation. Sometimes the different versions have aliases such as ``python3``, so make sure
to create the virtual environment with the appropriate python executable (or specify the executable for the environment during creation).

* Python version 3.7 of greater
* Virtual Environment (recommended) with pip installed (e.g. ``python3 -m venv env`` followed by ``source ./env/bin/activate``)
* Continue at [PyPi](#pypi)

### PyPi
After activating the environment you can install the package from pypi. 
The package supplies different [extras](#extras), to install additional dependencies
for optional features. 

Test if everything is working correctly by calling the ``ubii-client`` script which get's installed as part of the package.


```
$ python -m pip install ubii-interact-python
$ ubii-client --help 
```

### Editable / Local Install
Instead of installing from PyPi you can clone the repository and install the package this way. Editable installs are supported.
```
$ git clone git@github.com:SandroWeber/ubii-node-python.git
$ cd ubii-node-python
$ < create and acitvate virtual env>
$ pip install -e .
$ ubii-client --help
```


### Extras
This packages uses [extras](https://www.python.org/dev/peps/pep-0508/#id12).

* ``[test]``: Requirements to run ``pytest`` suite - mainly useful if you install the package from source, and not from PyPi

   > :warning: might depend on some processing-module packages, make sure you have all requirements installed (especially on Windows some processing dependencies are not in pypi)



## Usage
To use the ``ubi-interact-python`` package to implement your own python nodes refer to the [package documentation](#ubi-interact-python-node).
To start a python client refer to (cli)[#CLI].

### CLI
Basic functionality is provided through a command line interface which allows to run a python node which is able to import and load processing modules.
```
$ ubii-client --help

usage: ubii-client [-h]
                   [--processing-modules PROCESSING_MODULES]
                   [--verbose] [--debug]
                   [--log-config LOG_CONFIG]

options:
  -h, --help            show this help message and exit
  --processing-modules PROCESSING_MODULES
  --verbose, -v
  --debug
  --log-config LOG_CONFIG

```
(non obvious) arguments:

* ``--debug``: Debug mode changes the exception handling, and increases verbosity. In debug mode the Node does not try to handle exceptions, and fails loudly.
* ``--log-config``: optional path to a __.yaml__ file containing a dictionary of logging options consistent with the [``logggin.config.dictConfig``](https://docs.python.org/3/library/logging.config.html#logging.config.dictConfig) format. ([example config](src/ubii/interact/util/logging_config.yaml))
* ``--processing-modules``: specify a list of import paths for _Ubi Interact Procesing Modules_ implemented using the ``ubi-interact-python`` framework, see [processing-modules](#processing-modules) 

#### processing-modules
Below is a list of processing modules that are compatible with the python node.
To try them, install them inside the same virtual environment (refer to the documentation of the specific module), and run the client with the correct import path.
_(Autodetection for installed modules will be implemented soon)_

* [ubii-ocr-module](https://github.com/saggitar/ubii-interact-ocr-module)

Example usage after install of module:
```
$ ubii-client --processing-modules ubii.processing_modules.ocr.tesseract_ocr.TesseractOCR_EAST
$ Imported <class 'ubii.processing_modules.ocr.tesseract_ocr.TesseractOCR_EAST'>
$ ...
```


## Known bugs
* Exception handling on windows is not as refined as on Linux. Please report bugs!
* If the master node is closed during the lifetime of the python node, don't expect it to reconnect cleanly
* Starting and stopping sessions is working, but restarting a session (i.e. Start Session -> Stop Session -> Start Session) is still buggy
* Default logging behaviour is ... hard to explain :D
