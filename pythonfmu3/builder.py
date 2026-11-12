"""Python FMU builder"""
import argparse
import importlib.util
import itertools
import logging
import re
import shutil
import sys
import sysconfig
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union
from xml.dom.minidom import parseString
from xml.etree.ElementTree import Element, SubElement, tostring
from .osutil import get_lib_extension, get_platform
from .fmi3slave import FMI3_MODEL_OPTIONS_COMMON, FMI3_MODEL_OPTIONS_COSIM, FMI3_MODEL_OPTIONS_MX, Fmi3Slave, Fmi3SlaveBase

FilePath = Union[str, Path]
HERE = Path(__file__).parent

logger = logging.getLogger(__name__)


_SLAVE_CLASS_RE = re.compile(r'^class (\w+)\(([^)]*\bFmi3Slave(?:Base)?\b[^)]*)\)\s*:', re.MULTILINE)


def get_class_name(file_name: Path) -> str:
    """Find the name of the first class in *file_name* that textually extends Fmi3Slave/Fmi3SlaveBase."""
    data = Path(file_name).read_text(encoding="utf-8")
    match = _SLAVE_CLASS_RE.search(data)
    if match is None:
        raise ValueError(f"Unable to find a class extending Fmi3Slave or Fmi3SlaveBase in {file_name!s}")
    return match.group(1)


def _find_slave_class(module, filepath: Path) -> type:
    """Locate the FMU class in an imported module.

    Classes defined in the module that inherit from Fmi3SlaveBase are candidates. If the
    regex-based lookup (also used by the native wrapper as a fallback) matches one of them
    it wins, so behaviour stays identical for existing scripts; otherwise a single
    candidate is accepted (this handles multi-line base lists and indirect inheritance).
    """
    candidates = {
        name: obj for name, obj in vars(module).items()
        if isinstance(obj, type)
        and obj.__module__ == module.__name__
        and any(base.__name__ == Fmi3SlaveBase.__name__ for base in obj.__mro__)
    }
    try:
        preferred = get_class_name(filepath)
    except ValueError:
        preferred = None
    if preferred in candidates:
        return candidates[preferred]
    if len(candidates) == 1:
        return next(iter(candidates.values()))
    if not candidates:
        raise ValueError(f"No class inheriting from {Fmi3SlaveBase.__qualname__} found in {filepath!s}")
    raise ValueError(
        f"Several FMU classes found in {filepath!s} ({', '.join(sorted(candidates))}); "
        "keep a single Fmi3Slave subclass per script."
    )


def get_model_description(filepath: Path, module_name: str) -> Tuple[str, Element, str]:
    """Extract the FMU model description as XML.

    Args:
        filepath (pathlib.Path) : script file path
        module_name (str) : python module to load

    Returns:
        Tuple[str, xml.etree.TreeElement.Element, str] : FMU model name, model description, class name
    """
    # Add current folder to handle local dependencies
    sys.path.insert(0, str(filepath.parent))
    try:
        # Import the user interface
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        fmu_interface = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fmu_interface)
        # Instantiate the interface
        slave_class = _find_slave_class(fmu_interface, filepath)
        class_name = slave_class.__name__
        instance = slave_class(instance_name="dummyInstance", resources=str(filepath.parent))
    finally:
        sys.path.remove(str(filepath.parent))  # remove inserted temporary path

    if not isinstance(instance, Fmi3SlaveBase):
        raise TypeError(
            f"The provided class '{class_name}' does not inherit from {Fmi3SlaveBase.__qualname__}"
        )
    # Produce the xml
    return instance.modelName, instance.to_xml(), class_name


def _is_fmu_entry_library(path: Path) -> bool:
    """True for the library exporting the FMI functions (renamed to the model identifier)."""
    return path.stem in ("pythonfmu-export", "libpythonfmu-export")


def _libpython_candidates() -> List[str]:
    """Paths of the shared libpython of the running interpreter, if it has one."""
    if sys.platform == "win32":
        return []  # the Windows library links python3.dll directly
    libdir = sysconfig.get_config_var("LIBDIR") or ""
    framework_prefix = sysconfig.get_config_var("PYTHONFRAMEWORKPREFIX") or ""
    candidates = []
    for name in (sysconfig.get_config_var("INSTSONAME"), sysconfig.get_config_var("LDLIBRARY")):
        if not name or name.endswith(".a"):
            continue  # statically linked interpreter: nothing to point at
        for base in (libdir, framework_prefix):
            if base:
                candidate = Path(base) / name
                if candidate.is_file() and str(candidate) not in candidates:
                    candidates.append(str(candidate))
    return candidates


class FmuBuilder:

    @staticmethod
    def build_FMU(
        script_file: FilePath,
        dest: FilePath = ".",
        project_files: Iterable[FilePath] = (),
        documentation_folder: Optional[FilePath] = None,
        terminals : Optional[FilePath] = None,
        **options,
    ) -> Path:
        script_file = Path(script_file)
        if not script_file.exists():
            raise ValueError(f"No such file {script_file!s}")
        if not script_file.suffix.endswith(".py"):
            raise ValueError(f"File {script_file!s} must have extension '.py'!")

        dest = Path(dest)
        if not dest.exists():
            dest.mkdir(parents=True)
        project_files = set(map(Path, project_files))

        if documentation_folder is not None:
            documentation_folder = Path(documentation_folder)
            if not documentation_folder.exists():
                raise ValueError(
                    f"The documentation folder does not exists {documentation_folder!s}"
                )
        
        if terminals is not None:
            terminals = Path(terminals)
            if not terminals.exists():
                raise ValueError(
                    f"The specified terminalsAndIcons file does not exists {terminals!s}"
                )
            if not terminals.name == "terminalsAndIcons.xml":
                raise ValueError(
                    f"Incorrect terminal name {terminals!s}. Terminal file must be named terminalsAndIcons.xml"
                )

        module_name = script_file.stem

        with tempfile.TemporaryDirectory(prefix="pythonfmu_") as tempd:
            temp_dir = Path(tempd)
            shutil.copy2(script_file, temp_dir)

            # Embed pythonfmu in the FMU so it does not need to be included
            dep_folder = temp_dir / "pythonfmu3"
            dep_folder.mkdir()
            for dep in HERE.glob('*.py'):  # Find all python files at the same level as this one
                shutil.copy2(dep, dep_folder)
            for file_ in project_files:
                if file_ == script_file.parent:
                    new_folder = temp_dir / file_.name
                    new_folder.mkdir()
                    for f in file_.iterdir():
                        if f.is_dir():
                            temp_dest = new_folder / f.name
                            shutil.copytree(f, temp_dest)
                        elif f.name != script_file.name:
                            shutil.copy2(f, new_folder)
                        else:
                            logger.debug(
                                "Skip file with the same name as the script found in project file."
                            )
                else:
                    if file_.is_dir():
                        temp_dest = temp_dir / file_.name
                        shutil.copytree(file_, temp_dest)
                    else:
                        shutil.copy2(file_, temp_dir)

            model_identifier, xml, class_name = get_model_description(
                temp_dir.absolute() / script_file.name, module_name
            )

            dest_file = dest / f"{model_identifier}.fmu"

            type_node = xml.find("CoSimulation")
            option_names = [opt.name for opt in FMI3_MODEL_OPTIONS_COMMON]
            cosim_option_names = option_names.copy()
            cosim_option_names.extend(opt.name for opt in FMI3_MODEL_OPTIONS_COSIM)
            if type_node is not None:
                for option, value in options.items():
                    if option in cosim_option_names:
                        type_node.set(option, str(value).lower())

            type_node = xml.find("ModelExchange")
            mx_option_names = option_names.copy()
            mx_option_names.extend(opt.name for opt in FMI3_MODEL_OPTIONS_MX)
            if type_node is not None:
                for option, value in options.items():
                    if option in mx_option_names:
                        type_node.set(option, str(value).lower())

            with zipfile.ZipFile(dest_file, "w") as zip_fmu:

                resource = Path("resources")

                # Add files copied in temporary directory
                for f in temp_dir.rglob("*"):
                    if f.is_file() and f.parent.name != "__pycache__":
                        relative_f = f.relative_to(temp_dir)
                        zip_fmu.write(f, arcname=(resource / relative_f))

                # Hint for the Linux/macOS shim: where the Python that built this FMU
                # keeps its shared library (used when the importer is not Python itself).
                libpython_hints = _libpython_candidates()
                if libpython_hints:
                    zip_fmu.writestr(
                        str(resource.joinpath("pythonfmu_libpython.txt")),
                        "\n".join(libpython_hints) + "\n",
                    )

                # Add information for the Python loader: line 1 is the module, line 2 the class.
                # Older wrappers only read the first line, so this stays backward compatible.
                zip_fmu.writestr(
                    str(resource.joinpath("slavemodule.txt")), f"{module_name}\n{class_name}\n"
                )

                # Add FMI API wrapping Python class source
                sources = Path("sources")
                src = HERE / "pythonfmu-export"
                for f in itertools.chain(
                    src.rglob("*.hpp"), src.rglob("*.cpp"), src.rglob("CMakeLists.txt")
                ):
                    relative_f = f.relative_to(src)
                    if "build" in relative_f.parts:
                        continue
                    zip_fmu.write(f, arcname=(sources / relative_f))

                # Add FMI API wrapping Python class library
                binaries = Path("binaries")
                src_binaries = HERE / "resources" / "binaries"
                for f in itertools.chain(
                    src_binaries.rglob("*.dll"),
                    src_binaries.rglob("*.so"),
                    src_binaries.rglob("*.dylib"),
                ):
                    relative_f = f.relative_to(src_binaries)
                    # Only the FMI entry-point library takes the model identifier's name;
                    # helper libraries (the Linux/macOS backend) keep their own name.
                    if _is_fmu_entry_library(f):
                        name = f"{model_identifier}{relative_f.suffix}"
                    else:
                        name = relative_f.name
                    zip_fmu.write(f, arcname=(binaries / relative_f.parent / name))

                # Add the documentation folder
                if documentation_folder is not None:
                    documentation = Path("documentation")
                    for f in documentation_folder.rglob("*"):
                        if f.is_file():
                            relative_f = f.relative_to(documentation_folder)
                            zip_fmu.write(f, arcname=(documentation / relative_f))

                if terminals is not None:
                    terminalsFolder = Path("terminalsAndIcons")
                    zip_fmu.write(terminals, arcname=(terminalsFolder / terminals.name))

                # Add the model description
                xml_str = parseString(tostring(xml, "UTF-8"))
                zip_fmu.writestr(
                    "modelDescription.xml", xml_str.toprettyxml(encoding="UTF-8")
                )

            return dest_file

    @staticmethod
    def has_binary() -> bool:
        """Does the binary for this platform exits?"""
        binary_folder = get_platform()
        lib_ext = get_lib_extension() or "*"  # if library extension is unknown, it will look for '*.*' in src_binaries
        src_binaries = HERE / "resources" / "binaries" / binary_folder
        return src_binaries.exists() and len(list(src_binaries.glob(f"*.{lib_ext}"))) >= 1


def create_command_parser(parser: argparse.ArgumentParser):
    parser.add_argument(
        "-f",
        "--file",
        dest="script_file",
        help="Path to the Python script.",
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

    parser.add_argument(
        "--terminals",
        dest="terminals",
        help="Terminals file (terminalsAndIcons.xml) to include in the FMU.",
        default=None
    )

    for option in FMI3_MODEL_OPTIONS_COMMON:
        action = "store_false" if option.value else "store_true"
        parser.add_argument(
            f"--{option.cli}",
            dest=option.name,
            help=f"If given, {option.name}={action[6:]}",
            action=action
        )

    for option in FMI3_MODEL_OPTIONS_COSIM:
        action = "store_false" if option.value else "store_true"
        parser.add_argument(
            f"--{option.cli}",
            dest=option.name,
            help=f"If given, {option.name}={action[6:]}",
            action=action
        )
    
    for option in FMI3_MODEL_OPTIONS_MX:
        action = "store_false" if option.value else "store_true"
        parser.add_argument(
            f"--{option.cli}",
            dest=option.name,
            help=f"If given, {option.name}={action[6:]}",
            action=action
        )

    parser.add_argument(
        "project_files",
        metavar="Project files",
        nargs="*",
        help="Additional project files required by the Python script.",
        default=set()
    )

    parser.set_defaults(execute=FmuBuilder.build_FMU)
