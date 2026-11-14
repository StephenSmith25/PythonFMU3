# PythonFMU3 Studio

PythonFMU3 Studio is a local web app for writing, checking, simulating, building and
inspecting FMUs. It ships with PythonFMU3 and has no extra dependencies.

```bash
pythonfmu3 studio            # use the current folder as the workspace
pythonfmu3 studio my_models  # or another folder
```

Your browser opens on the Studio. Everything runs on your computer: the server only
listens on `127.0.0.1` and needs the access token in the link it prints.

![Simulating a model in PythonFMU3 Studio](assets/studio-simulate.png)

## Editor

- Pick any `.py` file in the workspace, edit it, and save with **Ctrl+S** (**Cmd+S** on macOS).
- On every save the model is loaded and checked. The **FMU block** tab draws its inputs,
  outputs and parameters, and the **modelDescription.xml** tab shows exactly what will go
  into the FMU.
- The **Checks** tab and the variables table flag common mistakes:
    - no independent (time) variable;
    - inputs or parameters that can't be set, usually because the attribute was created after
      `register_variable`;
    - integer, Boolean or string variables marked continuous;
    - names starting with `_`;
    - `author`, `description` and similar set as class attributes, which PythonFMU3 ignores.
- **Build FMU** writes the FMU to `build/` in the workspace and offers a download.
- **Validate** builds the FMU and checks it with
  [fmusim](https://github.com/modelica/fmusim) when it's installed, or runs basic
  archive checks otherwise.

## Simulate

Choose a simulator, set the stop time and output interval, and press **Run**:

| Simulator | What it does |
| --- | --- |
| Python preview | Runs your class directly: `do_step` for Co-Simulation, a fixed-step RK4 with event location for Model Exchange. Fast enough to re-run while you change values. |
| fmusim | Builds the FMU and runs it in fmusim, a native (non-Python) importer, the way most simulation tools would load it. |
| FMPy | Builds the FMU and runs it with [FMPy](https://github.com/CATIA-Systems/FMPy) (`pip install fmpy`). |

Every scalar parameter and input gets a number box and a slider. With **Re-run on
change** ticked, the Python preview re-runs as you drag. Pick which variables to plot,
hover a chart to read values, and download the result as CSV.

fmusim is found on your `PATH`; set `PYTHONFMU3_FMUSIM` to point at it otherwise.

## Inspector

Drop any FMU (FMI 2.0 or 3.0, from any tool) on the Inspector, or pick one from the
workspace. It shows:

- the model's details, interfaces, platforms and capabilities;
- the variables, filterable by inputs, outputs and parameters;
- archive checks, and the fmusim validation when fmusim is installed.

## Templates

Start a new model from a working template: PID controller, bouncing ball, Van der Pol,
Dahlquist, thermostat, polynomial surrogate (the pattern for ML models) or signal
generator. The template is copied into the workspace and opened in the editor.

## Options

```
pythonfmu3 studio [folder] [--port PORT] [--no-browser]
```

Only the workspace folder is read or written. Uploaded FMUs are stored in a temporary
folder that is deleted when the Studio stops. Model code runs in a separate Python
process for each request, so an error in your model can't take the Studio down.
