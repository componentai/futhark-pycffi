import json
import re
import sys

from cffi import FFI


def strip_includes(header):
    # Remove preprocessor directives (includes, pragmas, etc.)
    header = re.sub(r"^#include.*\n", "", header, flags=re.M)
    header = re.sub(r"^#pragma.*\n", "", header, flags=re.M)
    
    # Remove C++ extern "C" wrapper blocks that Futhark generates
    # Pattern: #ifdef __cplusplus\nextern "C" {\n#endif
    header = re.sub(r'#ifdef __cplusplus\s*\nextern "C" \{\s*\n#endif\s*\n?', "", header)
    # Pattern: #ifdef __cplusplus\n}\n#endif (closing block)
    header = re.sub(r'#ifdef __cplusplus\s*\n\}\s*\n#endif\s*\n?', "", header)
    
    # Also handle any remaining simple #ifdef __cplusplus blocks
    header = re.sub(r"^#ifdef __cplusplus\n.*\n#endif\n?", "", header, flags=re.M)
    
    # Remove any other preprocessor directives we might have missed
    header = re.sub(r"^#.*\n", "", header, flags=re.M)
    
    return header


def build(input_name, output_name):
    ffibuilder = FFI()

    header_file = input_name + ".h"
    source_file = input_name + ".c"
    manifest_file = input_name + ".json"

    manifest = json.load(open(manifest_file))

    output_name_lst = output_name.split("/")
    output_name_lst[-1] = "_" + output_name_lst[-1]
    output_name = ".".join(output_name_lst)

    backend = manifest["backend"]

    print("Detected platform: " + sys.platform)
    print("Detected backend:  " + backend)

    with open(source_file) as source:
        # Windows doesn't have libm (math is in msvcrt) and doesn't support -std=c99
        if sys.platform == "win32":
            libraries = []
            extra_compile_args = []
        else:
            libraries = ["m"]
            extra_compile_args = ["-std=c99"]
        
        if backend == "opencl":
            if sys.platform == "darwin":
                extra_compile_args += ["-framework", "OpenCL"]
            else:
                libraries += ["OpenCL"]
        elif backend == "cuda":
            libraries += ["cuda", "cudart", "nvrtc"]
        elif backend == "multicore":
            if sys.platform != "win32":
                extra_compile_args += ["-pthread"]
        
        ffibuilder.set_source(
            output_name,
            source.read(),
            libraries=libraries,
            extra_compile_args=extra_compile_args,
        )

    with open(header_file) as header:
        cdef = "typedef void* cl_command_queue;"
        cdef += "\ntypedef void* cl_mem;"
        cdef += "\ntypedef void* CUdeviceptr;"
        cdef += strip_includes(header.read())
        cdef += "\nvoid free(void *ptr);"
        ffibuilder.cdef(cdef)

    return ffibuilder


def main():
    name = sys.argv[1]
    ffi = build(name, name)
    ffi.compile()
