set(headers
        cppfmu/cppfmu_cs.hpp
        cppfmu/cppfmu_common.hpp

        fmi/fmi3Functions.h
        fmi/fmi3FunctionTypes.h
        fmi/fmi3PlatformTypes.h

        pythonfmu/PySlaveInstance.hpp
        pythonfmu/PyState.hpp
        )

set(sources
        cppfmu/cppfmu_cs.cpp
        cppfmu/fmi_functions.cpp
        pythonfmu/PySlaveInstance.cpp
        )

set(BINARY_OUTPUT_DIR "${CMAKE_SOURCE_DIR}/../resources/binaries/${TARGET_PLATFORM}")

if (WIN32)
  # Windows: a single library, linked against the version-independent python3.dll.
  set(PYTHONFMU_IMPL_TARGET pythonfmu-export)
else ()
  # Linux/macOS: the Python-dependent implementation lives in a "backend" library
  # (FMI functions renamed with a prefix). The FMU library itself (pythonfmu-export,
  # renamed to <modelIdentifier> by the builder) is a small shim with no link-time
  # dependency on libpython, so non-Python importers can load it. See shim/shim_loader.cpp.
  set(PYTHONFMU_IMPL_TARGET pythonfmu-backend)
endif ()

add_library(${PYTHONFMU_IMPL_TARGET} ${sources} ${headers})
target_compile_features(${PYTHONFMU_IMPL_TARGET} PUBLIC "cxx_std_17")
target_include_directories(${PYTHONFMU_IMPL_TARGET}
        PRIVATE
        "${Python3_INCLUDE_DIRS}"
        "${CMAKE_CURRENT_SOURCE_DIR}"
        )

if (WIN32)
  target_link_libraries(${PYTHONFMU_IMPL_TARGET} PRIVATE ${Python3_LIBRARIES})
  set_target_properties(${PYTHONFMU_IMPL_TARGET}
          PROPERTIES
          RUNTIME_OUTPUT_DIRECTORY_RELEASE "${BINARY_OUTPUT_DIR}"
          )
else ()
  # Python symbols are resolved at load time against the process (the host Python, or
  # the libpython the shim opened with RTLD_GLOBAL).
  target_compile_definitions(${PYTHONFMU_IMPL_TARGET} PRIVATE FMI3_FUNCTION_PREFIX=pythonfmu_backend_)
  if (APPLE)
    set_target_properties(${PYTHONFMU_IMPL_TARGET} PROPERTIES LINK_FLAGS "-undefined dynamic_lookup")
  endif ()
  set_target_properties(${PYTHONFMU_IMPL_TARGET}
          PROPERTIES
          LIBRARY_OUTPUT_DIRECTORY "${BINARY_OUTPUT_DIR}"
          )

  add_library(pythonfmu-export
          shim/shim_loader.cpp
          shim/shim_loader.hpp
          shim/fmi3_forwarders.cpp
          )
  target_compile_features(pythonfmu-export PUBLIC "cxx_std_17")
  target_include_directories(pythonfmu-export PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  target_link_libraries(pythonfmu-export PRIVATE ${CMAKE_DL_LIBS})
  set_target_properties(pythonfmu-export
          PROPERTIES
          LIBRARY_OUTPUT_DIRECTORY "${BINARY_OUTPUT_DIR}"
          # Only the FMI functions (marked FMI3_Export) are exported
          CXX_VISIBILITY_PRESET hidden
          VISIBILITY_INLINES_HIDDEN ON
          )
endif ()
