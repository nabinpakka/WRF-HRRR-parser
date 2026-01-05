from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy

# Define the extension module with the correct include_dirs
bitreader_ext = [
    Extension(
        "bitreader_c",  # The name of the module
        sources = ["bitreader_c.pyx"],  # Replace with your .pyx file
        extra_compile_args=["-O3"],
        extra_link_args=[],
    )
]

utils_ext = [
    Extension(
        "utils",  # The name of the module
        sources = ["utils.pyx"],  # Replace with your .pyx file
        include_dirs=[numpy.get_include()],
        extra_compile_args=["-O3"],
        extra_link_args=[],
    )
]

# Compile the extension using cythonize
setup(
    ext_modules = cythonize(bitreader_ext + utils_ext)
)