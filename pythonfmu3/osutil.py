import sys

import platform

def get_fmu_arch():
    #is_64bits = sys.maxsize > 2 ** 32
    system = platform.system()
    is_x86 = platform.machine() in ["i386", "AMD64", "x86_64"]
    platforms = {"Windows": "windows", "Linux": "linux", "Darwin": "darwin"}
    arch = "x86_64" if is_x86 else "x86"
    return arch + "-" + platforms.get(system, "unknown")

def get_platform() -> str:
    """Get FMU binary platform folder name."""
    return get_fmu_arch()


def get_lib_extension() -> str:
    """Get FMU library platform extension."""
    platforms = {"Darwin": "dylib", "Linux": "so", "Windows": "dll"}
    return platforms.get(platform.system(), "")

