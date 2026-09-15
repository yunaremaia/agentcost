# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Python 3.10 compatibility: `tomllib` fallback via `tomli` for `src/agentcost/budget.py` (#26)

### Fixed
- CI failure on Python 3.10 due to missing `tomllib` stdlib module (#26)
