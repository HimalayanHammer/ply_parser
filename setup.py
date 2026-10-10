from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='ply_parser',
    version='3.0.0',
    author='Krishna Bhattarai',
    author_email='krishna@kbhattarai.com',
    description='A python module that parses ascii and binary PLY (.ply) (Polygon File Format) files. It includes a class PLYObject for storing PLY file data and a function parse_ply_file() for reading PLY files and creating PLYObject instances and can easily be customized. ',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Qrishna/ply_parser",
    project_urls={
      "Bug Tracker": "https://github.com/Qrishna/ply_parser/issues"
    },
    package_dir={'': "src"},
    packages=find_packages("src"),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.11.4',
)
