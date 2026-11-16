# PythonFMU3 examples

Each example is a Python script that becomes an FMI 3.0 FMU when you build it:

```bash
pip install pythonfmu3
pythonfmu3 build -f bouncingBall.py          # writes BouncingBall.fmu
```

The FMUs aren't stored in the repository because the script is the source. Building
takes a second, and the FMU gets the PythonFMU3 binaries for your platform. To run an
FMU, the machine needs Python 3 with a shared Python library, plus any packages the
model imports (see [Running FMUs outside Python](../docs/install.md#running-fmus-outside-python-linux-and-macos)).

## The examples

| Script | Model | Interface | Shows | Extra packages |
| --- | --- | --- | --- | --- |
| `demoslave.py` | Resistor | Co-Simulation | A simple resistor: inputs, outputs, a tunable parameter and a String parameter | – |
| `bouncingBall.py` | BouncingBall | Co-Simulation | Events handled inside `do_step` | – |
| `bouncingBall_me.py` | BouncingBall | Model Exchange | State events with event indicators, units | – |
| `dahlquist_me.py` | Dahlquist | Model Exchange | A single continuous state | – |
| `dahlquist_me_cs.py` | Dahlquist | Model Exchange and Co-Simulation | One model supporting both interfaces | – |
| `vanderpol_me.py` | VanDerPol | Model Exchange | Two coupled continuous states | – |
| `robertson_me.py` | Robertson | Model Exchange | A stiff chemical kinetics problem | – |
| `alltypes.py` | AllTypes | Co-Simulation | Scalar variables of each type: Float64, Int32, Int64, UInt64 and Boolean | – |
| `arraytypes.py` | ArrayTypes | Co-Simulation | Array variables of the same types | NumPy |
| `linearTransform.py` | LinearTransformFixed | Co-Simulation | A fixed-size matrix-vector product with arrays | NumPy |
| `Enum.py` | Enum | Co-Simulation | Enumeration variables and types | – |
| `sympyslave.py` | SympySlave | Co-Simulation | A model that uses a third-party package | SymPy (`environment.yml`) |
| `mldemo.py` | MLDemo | Co-Simulation | A TensorFlow model inside an FMU (train it with `tensorflow-model-export/`) | TensorFlow, NumPy (`requirements.txt`) |
| [`pipe_cht/`](pipe_cht/) | Pipe1D | Co-Simulation | 1D pipe flow for conjugate heat transfer, with the number of segments as a structural parameter | NumPy |

For examples with extra packages, pack the requirements file into the FMU and install it
on the machine that runs it:

```bash
pythonfmu3 build -f mldemo.py requirements.txt
pythonfmu3 deploy -f MLDemo.fmu        # installs the packed requirements
```

## Tested importers

| Example | FMPy | fmusim 0.16.0 (Linux x86_64) |
| --- | --- | --- |
| `demoslave.py` | ✓ | ✓ CS |
| `bouncingBall.py` | ✓ | ✓ CS |
| `bouncingBall_me.py` | ✓ | ✓ ME |
| `dahlquist_me.py` | ✓ | ✓ ME |
| `dahlquist_me_cs.py` | ✓ | ✓ CS, ✓ ME |
| `vanderpol_me.py` | ✓ | ✓ ME |
| `robertson_me.py` | ✓ | ✓ ME (stiff: needs `--output-interval 0.001`) |
| `alltypes.py` | ✓ | ✓ CS |
| `arraytypes.py` | ✓ | ✓ CS |
| `linearTransform.py` | ✓ | ✓ CS |
| `Enum.py` | ✓ | ✓ CS |
| `sympyslave.py` | ✓ | – |
| `mldemo.py` | ✓ | – |
| `pipe_cht/pipe1d.py` | ✓ | ✓ CS |

FMPy runs the FMU inside its own Python process. fmusim is a native (C/Rust) importer, so
it loads the FMU the way most simulation tools do. For fmusim, every FMU passed
`fmusim validate` and simulated to 1 s:

```bash
fmusim validate BouncingBall.fmu
fmusim simulate --interface-type me --stop-time 1 BouncingBall.fmu
```

`sympyslave.py` and `mldemo.py` weren't run in fmusim because the test environment
didn't have SymPy or TensorFlow installed.

PythonFMU3's test suite also builds FMUs and simulates them with FMPy on Linux and
Windows, for Python 3.9 to 3.14, on every change.
