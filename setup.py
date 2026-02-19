from setuptools import setup, find_packages

setup(
    name="Pymodoro",
    version="0.1.0",
    description="A terminal-based Pomodoro timer using Python.",
    long_description=open("README.md").read() if __name__ == "__main__" else "",
    long_description_content_type="text/markdown",
    author="Basanta Bhandari",
    author_email="bhandari.basanta.47@gmail.com",
    url="https://github.com/basanta-bhandari/pymodoro",
    py_modules=["main", "utils"],
    python_requires=">=3.7",
    install_requires=[
        "pygame>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "pymodoro=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Utilities",
    ],
)