# Dependencies

PythonFMU3 doesn't package a Python environment inside the FMU. The FMU runs in a
Python installation on the machine that simulates it, so that Python needs the packages
your model imports (NumPy, SciPy, a machine-learning library, ...).

## Shipping your requirements with the FMU

**1. List the packages** in a `requirements.txt` (for pip) or an `environment.yml` (for
conda):

```text
numpy>=1.24
scipy
```

**2. Pass the file to `pythonfmu3 build`** after the script. It is packed into the FMU's
`resources/` folder:

```bash
pythonfmu3 build -f my_model.py requirements.txt
```

**3. On the machine that runs the FMU,** activate the Python environment the FMU will use
(see below) and install the packages from the FMU:

```bash
pythonfmu3 deploy -f MyModel.fmu
```

`deploy` finds `requirements.txt` or `environment.yml` in the FMU and installs it with pip
or conda. Choose the tool explicitly with `pythonfmu3 deploy -f MyModel.fmu pip` (or
`conda`), or name a different file inside the FMU with `-e`.

The machine running the FMU needs PythonFMU3 installed only if you use `deploy`: the FMU
itself carries its own copy of the `pythonfmu3` package.

## Which Python environment does the FMU use?

- **Python-based importer** (FMPy, for example): the interpreter running the importer,
  with its packages. Run `pythonfmu3 deploy` in that same environment.
- **Native importer on Linux or macOS** (OMSimulator, `fmusim`, Simulink, ...): the Python
  whose `libpython` the FMU loads (see
  [Running FMUs outside Python](install.md#running-fmus-outside-python-linux-and-macos)).
  That is a base installation, not a virtual environment: packages installed only in a
  venv aren't found unless you add its `site-packages` folder to `PYTHONPATH`, for example
  `export PYTHONPATH=/path/to/venv/lib/python3.12/site-packages`.
- **Windows:** the Python that provides the `python3.dll` found on the `PATH`.

## Keeping dependencies light

Every package a model imports has to be installed wherever the FMU runs, so the fewer the
better. The standard library and NumPy cover most models. For a trained machine-learning
model, consider exporting its weights and evaluating them with NumPy, rather than
requiring the full framework on every machine that runs the FMU.
