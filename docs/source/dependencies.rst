
How do I build an FMU from python code with third-party dependencies?
---------------------------------------------------------------------

Often, Python scripts depends on non-builtin libraries like `numpy`, `scipy`, etc.
_PythonFMU_ does not package a full environment within the FMU.
However, you can package a `requirements.txt` or `environment.yml` file within your FMU following these steps:

1. Install _pythonfmu_ package: `pip install pythonfmu3`
2. Create a new class extending the `Fmi3Slave` class declared in the `pythonfmu3.fmi3slave` module (see below for an example).
3. Create a `requirements.txt` file (to use _pip_ manager) and/or a `environment.yml` file (to use _conda_ manager) that defines your dependencies.
4. Run `pythonfmu3 build -f myscript.py requirements.txt` to create the fmu including the dependencies file.

And using `pythonfmu3 deploy`, end users will be able to update their local Python environment. The steps to achieve that:

1. Install _pythonfmu_ package: `pip install pythonfmu3`
2. Be sure to be in the Python environment to be updated. Then execute `pythonfmu3 deploy -f my.fmu`


.. code-block:: bash 
  pythonfmu3 deploy [-h] -f FMU [-e ENVIRONMENT] [{pip,conda}]

Deploy a Python FMU. The command will look in the `resources` folder for one of the following files:
`requirements.txt` or `environment.yml`. If you specify a environment file but no package manager, `conda` will be selected for `.yaml` and `.yml` otherwise `pip` will be used. The tool assume the Python environment in which the FMU should be executed is the current one.

positional arguments:
  {pip,conda}           Python packages manager

optional arguments:
  -h, --help            show this help message and exit
  -f FMU, --file FMU    Path to the Python FMU.
  -e ENVIRONMENT, --env ENVIRONMENT
                        Requirements or environment file.