# Install

The package can be installed using pip:

```bash
pip install pythonfmu3
```

Alternatively, the project can installed from source. First clone the repo,
```bash
git clone https://github.com/StephenSmith25/PythonFMU3.git
```

Next build the C++ wrapper. You need CMake (3.10 or later), a C++17 compiler and the
Python development headers (e.g. `python3-dev` on Debian/Ubuntu). The library is written
to `pythonfmu3/resources/binaries/<platform>/`.

```bash
cd PythonFMU3
cmake -S pythonfmu3/pythonfmu-export -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

On Windows, add `-A x64` to the first command for a 64-bit build. Prebuilt libraries in the
PyPI package cover Windows x86_64 and Linux x86_64; on macOS (Intel or Apple Silicon) and
ARM Linux, install from source this way.
Next the python project may be installed with either,

```bash
pip install -e .
```
or,

```bash
pip install .
```

## Running FMUs outside Python (Linux and macOS)

An FMU built with PythonFMU3 runs Python code, so the machine that simulates it needs a
Python 3 installation with a **shared** Python library (`libpython3.x.so` on Linux,
`libpython3.x.dylib` or a `Python.framework` on macOS), plus any packages the model imports.

When the importer is itself a Python program (e.g. FMPy), the FMU uses that interpreter.
Otherwise (OMSimulator, `fmusim`, Simulink, ...) the FMU loads `libpython` itself, looking in
this order:

1. the `PYTHONFMU_PYTHON_LIBRARY` environment variable, e.g.
   `export PYTHONFMU_PYTHON_LIBRARY=/usr/lib/x86_64-linux-gnu/libpython3.12.so.1.0`;
2. the library of the Python that built the FMU (recorded in
   `resources/pythonfmu_libpython.txt`);
3. standard library names for Python 3.8 to 3.14 (and the usual Homebrew and
   python.org framework locations on macOS).

If none can be loaded, instantiation fails with a message listing the paths tried.
Interpreters built without a shared library (some `pyenv` builds, for example) cannot be
used; with `pyenv`, reinstall with `PYTHON_CONFIGURE_OPTS="--enable-shared"`.

On Windows the FMU links `python3.dll`, which must be on the `PATH`.
