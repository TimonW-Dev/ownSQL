from pathlib import Path

from setuptools import setup

setup_dir = Path(__file__).resolve().parent
root_dir = setup_dir if (setup_dir / "ownSQL.py").is_file() else setup_dir.parent

with (root_dir / "README.md").open("r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ownSQL",
    version="0.0.0",  # Replaced automatically from the release tag by the publish workflow
    author="TimonW-Dev",
    author_email="timon.github@outlook.com",
    description=(
        "A MySQL database driver for MicroPython, supporting MySQL Server 8.x and 9.x."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/TimonW-Dev/ownSQL",
    package_dir={"": "." if root_dir == setup_dir else ".."},
    py_modules=["ownSQL"],
    classifiers=[
        "Programming Language :: Python :: Implementation :: MicroPython",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Other OS",
        "Topic :: Software Development :: Embedded Systems",
        "Topic :: Database",
    ],
    python_requires=">=3.4",
    keywords="micropython mysql esp8266 esp32 database driver",
    project_urls={
        "Bug Tracker": "https://github.com/TimonW-Dev/ownSQL/issues",
        "Source Code": "https://github.com/TimonW-Dev/ownSQL",
    },
)
