## FMU Dependencies

Often, Python scripts depends on non-builtin libraries like `numpy`, `scipy`, etc.
_PythonFMU3_ does not package a full environment within the FMU.
However, you can package a `requirements.txt` or `environment.yml` file within your FMU following these steps:

1. Install _pythonfmu3_ package: `pip install pythonfmu3`
2. Create a new class extending the `Fmi3Slave` class declared in the `pythonfmu3.fmi3slave` module (see below for an example).
3. Create a `requirements.txt` file (to use _pip_ manager) and/or a `environment.yml` file (to use _conda_ manager) that defines your dependencies.
4. Run `pythonfmu3 build -f myscript.py requirements.txt` to create the fmu including the dependencies file.

And using `pythonfmu3 deploy`, end users will be able to update their local Python environment. The steps to achieve that:

1. Install _pythonfmu3_ package: `pip install pythonfmu3`
2. Be sure to be in the Python environment to be updated. Then execute `pythonfmu3 deploy -f my.fmu`

```
usage: pythonfmu3 deploy [-h] -f FMU [-e ENVIRONMENT] [{pip,conda}]

Deploy a Python FMU. The command will look in the `resources` folder for one of the following files:
`requirements.txt` or `environment.yml`. If you specify a environment file but no package manager, `conda` will be selected for `.yaml` and `.yml` otherwise `pip` will be used. The tool assume the Python environment in which the FMU should be executed is the current one.

positional arguments:
  {pip,conda}           Python packages manager

optional arguments:
  -h, --help            show this help message and exit
  -f FMU, --file FMU    Path to the Python FMU.
  -e ENVIRONMENT, --env ENVIRONMENT
                        Requirements or environment file.
```

### Which Python environment does the FMU use?

- **Python-based importer** (e.g. FMPy): the interpreter running the importer, with its
  packages. Run `pythonfmu3 deploy` in that same environment.
- **Native importer on Linux/macOS** (OMSimulator, `fmusim`, Simulink, ...): the Python
  whose `libpython` the FMU loads (see
  [Running FMUs outside Python](install.md#running-fmus-outside-python-linux-and-macos)).
  That is a base installation, not a virtual environment: packages installed only in a
  venv are not found unless you add its `site-packages` folder to `PYTHONPATH`, e.g.
  `export PYTHONPATH=/path/to/venv/lib/python3.12/site-packages`.
- **Windows**: the Python providing the `python3.dll` found on the `PATH`.
