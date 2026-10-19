from setuptools import setup, find_packages

setup(
    name="zerotrace-orchestrator",
    version="1.0.0",
    description="ZeroTrace Master Orchestrator (Brain Plane & Proof Plane)",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.11",
)
