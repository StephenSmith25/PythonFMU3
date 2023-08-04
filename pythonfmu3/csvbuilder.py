import argparse
import tempfile
from pathlib import Path
from typing import Union
from .fmi3slave import FMI3_MODEL_OPTIONS
from .builder import FmuBuilder

FilePath = Union[str, Path]


def create_csv_slave(csv_file: FilePath):
    classname = csv_file.stem.capitalize()
    filename = csv_file.name
    return f"""
import re
import csv
from math import isclose  # requires >= python 3.5
from pythonfmu3.fmi3slave import Fmi3Type, Fmi3Slave, Fmi3Causality, Fmi3Variability, Integer, Real, Boolean, String

def lerp(v0: float, v1: float, t: float) -> float:
    return (1 - t) * v0 + t * v1

def normalize(x: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    x = max(min(x, in_max), in_min)
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def get_fmi3_type(s: str) -> Fmi3Type:
    s_lower = s.lower()
    for type in Fmi3Type:
        if type.name in s_lower:
            if type == Fmi3Type.enumeration:
                raise NotImplementedError(f"Unsupported type: {{Fmi3Type.enumeration.name}}")
            else:
                return type
    raise TypeError(f"Could not process type from input string: {{s}}")

TYPE2OBJ = {{
    Fmi3Type.integer: Integer,
    Fmi3Type.real: Real,
    Fmi3Type.boolean: Boolean,
    Fmi3Type.string: String
    }}

class Header:

    def __init__(self, s):
        matches = re.findall(r"\\[(.*?)\\]", s)
        if len(matches) > 0:
            match = matches[-1]
            self.name = s.replace("[" + match + "]", "").rstrip()
            self.type = get_fmi3_type(match)
        else:
            self.name = s
            self.type = Fmi3Type.real
        

    def __repr__(self):
        return f"Header(name={{self.name}}, type={{self.type.name}})"


class {classname}(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.current_index = 0
        self.next_index = None
        self.current_time = 0.0
        self.interpolate = True
        data = dict()

        def read_csv():
            with open(self.resources + '/' + "{filename}") as f:
                return list(csv.reader(f, skipinitialspace=True, delimiter=',', quotechar='"'))

        read = read_csv()
        header_row = read[0]
        headers = list(map(lambda h: Header(h.strip()), header_row[1:len(header_row)]))
        rows = read[1:len(read)]
        self.num_rows = len(rows)
        self.times = []

        for header in headers:
            data[header.name] = []

            def get_value(header):
                current_value = data[header.name][self.current_index]
                if self.next_index is None or header.type is not Fmi3Type.real:
                    return current_value

                next_value = data[header.name][self.next_index]
                
                if current_value == next_value:
                    return current_value
                
                current_value_t = self.times[self.current_index]
                next_value_t = self.times[self.next_index]

                t = normalize(self.current_time, current_value_t, next_value_t, 0, 1)
                return lerp(current_value, next_value, t)

            self.register_variable(
                TYPE2OBJ[header.type](header.name,
                     causality=Fmi3Causality.output,
                     variability=Fmi3Variability.constant,
                     getter=lambda header=header: get_value(header)), nested=False)

        for i in range(0, self.num_rows):
            row = rows[i]
            self.times.append(float(row[0]))

            for j in range(1, len(row)):
                header = headers[j-1]
                if header.type == Fmi3Type.integer:
                    data[header.name].append(int(row[j]))
                elif header.type == Fmi3Type.real:
                    data[header.name].append(float(row[j]))
                elif header.type == Fmi3Type.boolean:
                    data[header.name].append(row[j] == 'true')
                elif header.type == Fmi3Type.string:
                    data[header.name].append(row[j])

        self.register_variable(Integer("num_rows",
                                    causality=Fmi3Causality.output,
                                    variability=Fmi3Variability.constant))
        self.register_variable(Real("end_time",
                                    causality=Fmi3Causality.output,
                                    variability=Fmi3Variability.constant,
                                    getter=lambda: self.times[-1]))
        self.register_variable(Boolean("interpolate",
                                    causality=Fmi3Causality.parameter,
                                    variability=Fmi3Variability.tunable))

    def find_indices(self, t, dt):
        current_t = self.times[self.current_index]
        while current_t < t:
            if self.current_index == self.num_rows-1:
                break
            self.current_index += 1
            current_t = self.times[self.current_index]
        if current_t > t and not isclose(current_t, t, rel_tol=1e-6):
            self.current_index -= 1
            current_t = self.times[self.current_index]

        if self.interpolate and self.current_index <= self.num_rows-2:
            self.next_index = self.current_index+1
            next_t = self.times[self.next_index]
            while t+dt >= next_t and not isclose(t+dt, next_t, abs_tol=1e-6):
                if self.next_index + 1 < self.num_rows:
                    self.next_index += 1
                    next_t = self.times[self.next_index]

    def setup_experiment(self, start_time: float):
        self.current_time = start_time
        self.find_indices(start_time, 0)

    def do_step(self, current_time: float, step_size: float) -> bool:
        if (self.current_index == self.num_rows):
            return False
        self.current_time = current_time + step_size
        self.find_indices(self.current_time, step_size)
        return True
    """


class CsvFmuBuilder:

    @staticmethod
    def build_FMU(
        csv_file: FilePath,
        dest: FilePath = ".",
        **options,
    ) -> Path:
        csv_file = Path(csv_file)
        if not csv_file.exists():
            raise ValueError(f"No such file {csv_file!s}")
        if not csv_file.suffix.endswith(".csv"):
            raise ValueError(f"File {csv_file!s} must have extension '.csv'!")

        options["dest"] = dest
        options["project_files"] = {csv_file}

        with tempfile.TemporaryDirectory(prefix="pythonfmu_") as tempd:
            temp_dir = Path(tempd)
            script_file = temp_dir / (csv_file.stem + ".py")
            with open(script_file, "+w") as f:
                f.write(create_csv_slave(csv_file))
            options["script_file"] = script_file
            return FmuBuilder.build_FMU(**options)


def create_command_parser(parser: argparse.ArgumentParser):

    parser.add_argument(
        "-f",
        "--file",
        dest="csv_file",
        help="Path to the CSV file.",
        required=True
    )

    parser.add_argument(
        "-d", "--dest", dest="dest", help="Where to save the FMU.", default="."
    )

    parser.add_argument(
        "--doc",
        dest="documentation_folder",
        help="Documentation folder to include in the FMU.",
        default=None
    )

    for option in FMI3_MODEL_OPTIONS:
        action = "store_false" if option.value else "store_true"
        parser.add_argument(
            f"--{option.cli}",
            dest=option.name,
            help=f"If given, {option.name}={action[6:]}",
            action=action
        )

    parser.set_defaults(execute=CsvFmuBuilder.build_FMU)
