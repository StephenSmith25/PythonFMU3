# Jupyter notebooks

Write a model in a notebook cell, check it, simulate it, run parameter studies and build
the FMU without leaving Jupyter. It works in JupyterLab, the classic notebook, VS Code and
Google Colab.

[Open the example notebook in Colab](https://colab.research.google.com/github/StephenSmith25/PythonFMU3/blob/master/examples/notebooks/getting_started.ipynb)

## Install

```bash
pip install "pythonfmu3[notebook]"
```

This adds pandas and Matplotlib, for results and plots.

## Write a model in a cell

Load the extension once per notebook, then start a cell with `%%fmu`:

```ipython
%load_ext pythonfmu3
```

```ipython
%%fmu
class Tank(Fmi3Slave):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.time = 0.0
        self.q_in = 0.2
        self.level = 1.0
        self.register_variable(Float64("time", causality=Fmi3Causality.independent,
                                       variability=Fmi3Variability.continuous))
        self.register_variable(Float64("q_in", causality=Fmi3Causality.input, start=0.2))
        self.register_variable(Float64("level", causality=Fmi3Causality.output))

    def do_step(self, current_time, step_size):
        self.level += self.q_in * step_size
        self.time = current_time + step_size
        return True
```

Running the cell:

- saves it as a model file, `tank.py` (named after the class), in the notebook's folder.
  The `pythonfmu3` import is added if the cell doesn't have one;
- loads the model in a separate Python process and runs the same checks as
  [PythonFMU3 Studio](studio.md);
- shows the FMU block (inputs, outputs and parameters), any problems, and a table of the
  variables;
- binds the class name, `Tank`, to a model handle you use in the next cells.

Options: `%%fmu my_tank.py` chooses the file name, `--dir models` the folder, `--build`
also builds the FMU, and `--overwrite` replaces a file that wasn't written by `%%fmu`.
Files written by `%%fmu` start with a comment saying so; edit the cell, not the file.

## Simulate

```ipython
res = Tank.simulate(stop_time=100, start_values={"q_in": 0.4})
res.plot(y="level")
```

`simulate()` returns a pandas DataFrame indexed by time, with a column per output and
local variable (array elements as `name[1]`, `name[2]`, ...), so analysis and plotting work
as usual. Events are in `res.attrs["events"]`.

| Argument | Meaning |
| --- | --- |
| `stop_time` | End time (default 10) |
| `step_size` | Output interval (default `stop_time / 500`) |
| `start_values` | Values for parameters and inputs, e.g. `{"q_in": 0.4}`; unknown names are an error |
| `interface` | `"cs"` or `"me"`, for models that support both |
| `simulator` | `"python"` (default) runs the class directly; `"fmpy"` or `"fmusim"` build the FMU and run it in that importer |
| `outputs` | Only record these variables |

A parameter study is a loop:

```ipython
import pandas as pd

sweep = pd.DataFrame({f"q_in = {q}": Tank.simulate(stop_time=100, start_values={"q_in": q})["level"]
                      for q in (0.1, 0.2, 0.4)})
sweep.plot()
```

`Tank.ok`, `Tank.problems` and `Tank.variables` give the check results in code.

## Build the FMU

```ipython
fmu = Tank.build()        # writes Tank.fmu next to tank.py; Tank.build("out") for another folder
fmu                       # shows the FMU: interfaces, platforms, variables
fmu.simulate(stop_time=100)   # runs the FMU itself, in FMPy or fmusim
fmu.validate()            # fmusim validation if installed, otherwise archive checks
```

## Models in files, and any FMU

`Model` works with any model file, and `FMU` with any FMI 2.0 or 3.0 FMU from any tool:

```ipython
from pythonfmu3.notebook import FMU, Model

Model("controller.py")          # checks and shows it, like %%fmu
FMU("supplier_model.fmu")       # inspects it; the FMU is only read
```

## Notes

- Each check and simulation runs in a fresh Python process, so re-running a cell always
  uses the current code, and an error in a model can't crash the notebook.
- Error line numbers refer to the saved file, which has one extra line at the top (the
  `%%fmu` comment, and the import if one was added).
- Building FMUs needs PythonFMU3's native library for your platform, as for any FMU
  build. The PyPI packages include it for Windows and Linux x86_64, so Colab works out of
  the box.
