# Changelog

## Unreleased

### Fixed
- Several FMUs in one Python process (FMPy, or a Python co-simulation script) now each
  run their own model script. Each FMU's script is loaded under a module name unique to
  that FMU, so two FMUs whose scripts share a name (two different `model.py`), or a
  script named like a module the process had already imported, no longer pick up the
  wrong code. Native importers were not affected.
- MCP server: array outputs of up to 60 elements, such as a 30-segment pipe profile, are
  shown in full in simulation summaries; longer arrays as 30 samples.

## 1.3.0 (2026-11-18)

### Added
- **Jupyter support** (`%load_ext pythonfmu3`): the `%%fmu` cell magic saves, checks and
  displays a model; `simulate()` returns pandas DataFrames; `build()` builds the FMU; and
  `pythonfmu3.notebook.FMU` inspects and simulates any FMU. Install with
  `pip install "pythonfmu3[notebook]"`. See [Jupyter notebooks](notebooks.md) and
  `examples/notebooks/getting_started.ipynb`.
- **macOS binaries:** the PyPI packages now include the native library for Apple Silicon
  (`aarch64-darwin`) and Intel Macs (`x86_64-darwin`), so FMUs build on macOS without
  compiling anything. CI also runs the tests on macOS.
- `llms.txt` and `llms-full.txt` on the documentation site, so AI assistants can learn the
  PythonFMU3 API and its rules.

### Changed
- Clearer documentation: a variables guide (causality and variability), what the importer
  calls in your class, build options, per-platform installation, and dependencies.
- CI tests every supported Python version (3.11 to 3.15) on Linux, and the oldest and
  newest on Windows and macOS.

### Fixed
- MCP simulations record whole array outputs and summarise single-value outputs first,
  so long arrays no longer hide outputs such as an outlet temperature.
- Simulating in fmusim: array start values are passed in the format fmusim accepts, and
  fmusim's array and Boolean results are read correctly.
- MCP simulations report a misspelt start value instead of silently ignoring it.

## 1.2.0 (2026-11-16)

### Added
- **MCP server for AI agents** (`pythonfmu3 mcp`): Claude, GitHub Copilot in VS Code,
  Cursor and other MCP clients can write, check, simulate and build FMUs, using the same
  checks and simulators as the Studio. Install with `pip install "pythonfmu3[mcp]"`
  (Python 3.10+). See [AI agents (MCP)](mcp.md).

## 1.1.0 (2026-11-14)

### Added
- **PythonFMU3 Studio** (`pythonfmu3 studio`): a local web app to write, check, simulate,
  build and inspect FMUs, with no extra dependencies. It has an editor that checks the
  model on every save, a Python-preview simulator with live sliders (plus fmusim and
  FMPy), an FMU inspector for any FMI 2.0/3.0 FMU, and seven model templates. See
  [PythonFMU3 Studio](studio.md).
- Example: 1D pipe flow for conjugate heat transfer co-simulation
  (`examples/pipe_cht`), with the number of segments as a structural parameter.
- [Migrating from PythonFMU](migration.md): a guide for moving FMI 2.0 PythonFMU models
  to PythonFMU3.

## 1.0.0 (2026-11-12)

### Added
- FMUs can be loaded by native (non-Python) FMI importers on Linux and macOS, such as
  OMSimulator, `fmusim` and Simulink. Previously they only worked inside a Python-based
  importer such as FMPy. See
  [Running FMUs outside Python](install.md#running-fmus-outside-python-linux-and-macos).
- `PYTHONFMU_PYTHON_LIBRARY` environment variable to choose the Python library the FMU loads.
- Python errors raised by a model are reported with their full traceback in the FMU log.

### Changed
- On Linux and macOS, `binaries/<platform>/` now holds two libraries: `<modelIdentifier>`
  (the FMI entry point) and `libpythonfmu-backend`. Keep them together.
- `resources/slavemodule.txt` also records the model class name, and
  `resources/pythonfmu_libpython.txt` records the building interpreter's Python library.
- The builder finds the model class by importing the script, so class definitions whose
  base classes span several lines work. A script must define a single FMU class.
- `Fmi3UpdateDiscreteStatesResult` fields renamed to the FMI names
  `discreteStatesNeedUpdate` and `nominalContinuousStatesChanged`. The old names
  (`discreteStateNeedsUpdate`, `nominalsOfContinuousStatesChanged`) still work as aliases.
- Python 3.9 or later is required; the package is built from `pyproject.toml`.

### Fixed
- Crash (use-after-free) when freeing an instance after a Python exception.
- Possible deadlock when instantiation failed without a Python exception.
- Out-of-bounds reads when an importer requested more values than the model returned.
- `fmi3DoStep` now always sets `eventHandlingNeeded`, `terminateSimulation` and
  `earlyReturn`, and honours the matching `Fmi3StepResult` fields.
- Memory leaks in logging, FMU-state handling and failed instantiation.
- Crash when the importer passes no log callback (allowed by FMI 3.0).
- Default CoSimulation/ModelExchange capability flags in the model description when
  building from Python (e.g. `canHandleVariableCommunicationStepSize` came out `false`).
- `--terminals` packed the wrong file as `terminalsAndIcons.xml`.
- Array variable setters on NumPy 2.5 or later.
- `discreteStatesNeedUpdate` and `nominalContinuousStatesChanged` returned from
  `update_discrete_states` were ignored because of the field-name mismatch above.
- FMUs built on Apple Silicon and ARM Linux use the correct platform folders
  (`aarch64-darwin`, `aarch64-linux`).
- Documentation: corrected the PID controller and quick-start examples (their inputs and
  parameters could not be set), the `pythonfmu3 build` options, the list of supported
  types, and added a limitations section. Documentation examples are now checked to
  produce working models in the test suite.
