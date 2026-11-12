# Changelog

## Unreleased

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
