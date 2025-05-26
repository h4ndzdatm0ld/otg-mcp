from setuptools import find_packages, setup

setup(
    name="otg_mcp",
    version="1.0",
    description="Open Traffic Generator - Model Context Protocol",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11,<3.13",
    extras_require={
        "dev": [
            "openapi-python-client>=0.14.0",
            "black>=25.1.0",
            "ruff>=0.11.7",
            "mypy>=1.0.0",
            "types-PyYAML",
            "pip>=25.1.1",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
)
