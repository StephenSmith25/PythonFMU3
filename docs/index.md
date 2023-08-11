# PythonFMU3

> A lightweight framework that enables the packaging of Python 3 code as co-simulation FMUs (following FMI version 3.0).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/StephenSmith25/PythonFMU3/issues)

[![CI](https://github.com/StephenSmith25/PythonFMU3/workflows/CI/badge.svg)](https://github.com/StephenSmith25/PythonFMU3/actions?query=workflow%3ACI)
[![PyPI](https://img.shields.io/pypi/v/pythonfmu3)](https://pypi.org/project/pythonfmu3/)


This project is a fork of the original PythonFMU repository available at https://github.com/NTNU-IHB/PythonFMU, which was used as the basis for adding support for FMI 3.0. While we have made efforts to expand the functionality of this project, it currently has some limitations and does not support all the features of FMI 3.0. We would like to acknowledge and give credit to the original PythonFMU project for their contributions to this work.

## Support:

We currently support a basic FMU which follows the FMI3 standard. This includes support for:

- Float64, Int32, UInt64, String, Boolean variables
- Step Mode
- Arrays, which requires the numpy package

Please take a look at the examples bouncingBall.py and linearTransform.py for a demonstration of these features.

## Future:

In no particular order, we plan to add support for:

- Refactor Real, Integer ect .to match FMI3 specification
- Support more variable types from FMI3
- Improve array support
- Add event mode
- Include FMI3 related testing

