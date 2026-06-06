from setuptools import find_packages, setup

setup(
    name="olist_orchestration",
    packages=find_packages(exclude=["olist_orchestration_tests"]),
    install_requires=[
        "dagster",
        "dagster-cloud"
    ],
    extras_require={"dev": ["dagster-webserver", "pytest"]},
)
