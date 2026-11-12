/* Minimal non-Python FMI 3 importer used by test_non_python_host.py.
   usage: fmi3_host <fmu library> <resources dir>  (runs pythonslave.py for 3 steps) */
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include "fmi3Functions.h"

static void logger(fmi3InstanceEnvironment env, fmi3Status s, fmi3String cat, fmi3String msg) {
    printf("[log %d %s] %s\n", s, cat ? cat : "", msg);
}
#define LOAD(name) name##TYPE* name = (name##TYPE*)dlsym(h, #name); if (!name) { printf("missing %s\n", #name); return 1; }

int main(int argc, char** argv) {
    void* h = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!h) { printf("dlopen failed: %s\n", dlerror()); return 1; }
    LOAD(fmi3GetVersion) LOAD(fmi3InstantiateCoSimulation) LOAD(fmi3EnterInitializationMode)
    LOAD(fmi3ExitInitializationMode) LOAD(fmi3DoStep) LOAD(fmi3GetFloat64) LOAD(fmi3FreeInstance)
    printf("version %s\n", fmi3GetVersion());
    fmi3Instance c = fmi3InstantiateCoSimulation("inst", "", argv[2], fmi3False, fmi3True, fmi3False, fmi3False,
                                                 NULL, 0, NULL, logger, NULL);
    if (!c) { printf("instantiate failed\n"); return 2; }
    fmi3EnterInitializationMode(c, fmi3False, 0, 0, fmi3False, 0);
    fmi3ExitInitializationMode(c);
    fmi3Boolean ehn, term, early; fmi3Float64 last;
    for (int i = 0; i < 3; i++) fmi3DoStep(c, i * 0.5, 0.5, fmi3True, &ehn, &term, &early, &last);
    fmi3ValueReference vr = 6; fmi3Float64 out = -1;
    fmi3Status st = fmi3GetFloat64(c, &vr, 1, &out, 1);
    printf("status %d realOut %g\n", st, out);
    fmi3FreeInstance(c);
    return (st == fmi3OK && out == 1.5) ? 0 : 3;
}
