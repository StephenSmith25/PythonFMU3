import platform
import sys

# FMI 3.0 platform tuples are "<arch>-<sys>" (FMI 3.0 standard, section 2.5.1.4),
# e.g. x86_64-linux, aarch64-darwin, x86-windows.
_SYSTEMS = {"Windows": "windows", "Linux": "linux", "Darwin": "darwin"}

_ARCHITECTURES_64 = {
    "x86_64": "x86_64", "amd64": "x86_64", "x64": "x86_64",
    "i386": "x86_64", "i686": "x86_64", "x86": "x86_64",  # 64-bit Python on x86 hardware
    "aarch64": "aarch64", "arm64": "aarch64", "armv8l": "aarch64",
    "ppc64": "ppc64", "ppc64le": "ppc64",
    "riscv64": "riscv64",
}

_ARCHITECTURES_32 = {
    "x86_64": "x86", "amd64": "x86", "x64": "x86", "i386": "x86", "i686": "x86", "x86": "x86",
    "aarch64": "aarch32", "arm64": "aarch32", "armv7l": "aarch32", "armv8l": "aarch32", "arm": "aarch32",
    "ppc": "ppc32",
    "riscv32": "riscv32",
}


def _is_64bit() -> bool:
    # Bitness of the running interpreter, which is what the FMU binary must match
    # (e.g. a 32-bit Python on 64-bit Windows needs x86-windows).
    return sys.maxsize > 2 ** 32


def get_fmu_arch() -> str:
    """FMI 3.0 platform tuple of the running interpreter, e.g. 'aarch64-darwin'."""
    machine = platform.machine().lower()
    table = _ARCHITECTURES_64 if _is_64bit() else _ARCHITECTURES_32
    arch = table.get(machine, machine or "unknown")
    system = _SYSTEMS.get(platform.system(), platform.system().lower() or "unknown")
    return f"{arch}-{system}"


def get_platform() -> str:
    """Get FMU binary platform folder name."""
    return get_fmu_arch()


def get_lib_extension() -> str:
    """Get FMU library platform extension."""
    platforms = {"Darwin": "dylib", "Linux": "so", "Windows": "dll"}
    return platforms.get(platform.system(), "")
