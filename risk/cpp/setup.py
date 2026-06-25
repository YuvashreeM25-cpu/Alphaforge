"""
Build script for the C++ VaR engine.

Build it with:
    pip install pybind11
    pip install ./risk/cpp        # or:  python risk/cpp/setup.py build_ext --inplace

This is OPTIONAL. The pure-Python engine (risk/montecarlo_var.py) runs without
any of this. The C++ build only adds speed, demonstrated in risk/benchmark.py.
"""
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

ext_modules = [
    Pybind11Extension(
        "var_engine",
        ["var_engine.cpp"],
        cxx_std=17,
    ),
]

setup(
    name="var_engine",
    version="0.1.0",
    description="C++ Monte-Carlo VaR core for AlphaForge",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)
