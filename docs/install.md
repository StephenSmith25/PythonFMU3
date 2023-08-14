# Install

The package can be installed using pip:

```bash
pip install pythonfmu3
```

Alternatively, the project can installed from source. First clone the repo,
```bash
git clone https://github.com/StephenSmith25/PythonFMU3.git
```

Next build the C++ code,
```bash
mkdir build
cd build 
cmake -S ../pythonfmu3/pythonfmu-export/
make
```
Next the python project may be installed with either,

```bash
pip install -e .
```
or,

```bash
pip install .
```
