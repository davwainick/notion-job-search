"""
setup.py — makes the package pip-installable and registers the
``notion-job-search`` console script entry point.
"""

from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="notion-job-search",
    version="1.0.0",
    author="Your Name",
    description="Scaffold a job-search CRM workspace in Notion automatically.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/notion-job-search",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.10",
    install_requires=[
        "notion-client>=2.2.1",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": ["pytest>=7.4.0"],
    },
    entry_points={
        "console_scripts": [
            "notion-job-search=notion_job_search.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
