# Installation

## Which install do you need?

| Your computer | Install |
| --- | --- |
| Windows x86_64, Linux x86_64 | `pip install pythonfmu3`. Ready to build FMUs. |
| macOS (Apple Silicon or Intel), ARM Linux | `pip install pythonfmu3`, then build the native library once (below). Until you do, everything except building runnable FMUs works: built FMUs contain no binaries. |
| Developing PythonFMU3 itself | Install from source (below). |

PythonFMU3 needs Python 3.9 or later. Optional extras add the
[Jupyter support](notebooks.md) (`pip install "pythonfmu3[notebook]"`) and the
[MCP server for AI agents](mcp.md) (`pip install "pythonfmu3[mcp]"`, Python 3.10+).

Check the installation with `pythonfmu3 --version`.

## Installing from source, or building the native library

Every FMU contains a small native library that implements the FMI 3.0 C API and runs your
Python code. The PyPI packages include it for Windows x86_64 and Linux x86_64; on other
platforms, build it with CMake (3.10 or later), a C++17 compiler and the Python
development headers (`python3-dev` on Debian/Ubuntu; included with Homebrew and
python.org Python on macOS):

```bash
git clone https://github.com/StephenSmith25/PythonFMU3.git
cd PythonFMU3
cmake -S pythonfmu3/pythonfmu-export -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
pip install -e .            # or: pip install .
```

On Windows, add `-A x64` to the first `cmake` command for a 64-bit build. The library is
written to `pythonfmu3/resources/binaries/<platform>/`, for example `aarch64-darwin` on
Apple Silicon, and every FMU you build from then on includes it.

If `pip install -e .` fails with "editable mode currently requires a setuptools-based
build", your pip is too old: run `python -m pip install --upgrade pip` first.

To check that an FMU has binaries, list its `binaries/` folder (`unzip -l MyModel.fmu`),
or open it in [PythonFMU3 Studio](studio.md)'s Inspector, which lists the platforms it
has binaries for.

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
3. standard library names for Python 3.8 to 3.20, newest first (and the usual Homebrew and
   python.org framework locations on macOS).

If none can be loaded, instantiation fails with a message listing the paths tried.
Interpreters built without a shared library (some `pyenv` builds, for example) cannot be
used; with `pyenv`, reinstall with `PYTHON_CONFIGURE_OPTS="--enable-shared"`.

On Windows the FMU links `python3.dll`, which must be on the `PATH`.
