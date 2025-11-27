# Terraform Code Quality Analysis

Tools for mining Terraform repositories and calculating HCL-specific maintainability metrics.

## Quick Start

```bash
# Interactive CLI
python main.py
```

## Tools

### 1. `main.py` - Interactive CLI
Pretty command-line interface for all operations.

**Commands:**
- `mine` - Mine Terraform repositories from GitHub
- `test` - Test mining on a single repository
- `analyze` - Build quality metrics dataset
- `quick` - Quick analysis of a local repository
- `status` - Show project status
- `clean` - Clean output files

### 2. `mine_repositories.py` - Repository Mining
Finds and filters Terraform repositories from GitHub.

```bash
# Full pipeline (requires GITHUB_TOKEN in .env)
python mine_repositories.py

# Test single repository
python mine_repositories.py --test https://github.com/owner/repo
```

**Output**: `output/iac_repositories_final_filtered.txt`

### 3. `build_dataset.py` - Quality Analysis
Analyzes Terraform code and calculates Maintainability Index (0-100).

```bash
# Single repository
python build_dataset.py --mode single --input /path/to/repo --skip-github

# Multiple repositories
python build_dataset.py --mode list --input repos.txt
```

**Output**: `output/iac_dataset.csv`

## Maintainability Index

HCL-specific score (0-100) based on:
- Resource Composition (25%): Module usage, block size
- Configuration Clarity (25%): Explicitness, nesting
- Dependency Management (20%): Coupling, complexity
- Security & Best Practices (20%): No deprecated code
- Operational Readiness (10%): Outputs, data sources

See [MI_CALCULATION.md](MI_CALCULATION.md) for details.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: GitHub token for metadata
echo "GITHUB_TOKEN=your_token" > .env
```

**Requirements**: Python 3.9+, Java 11+ (for TerraMetric)

## Development

```bash
make format  # Format code with Black
make lint    # Lint with flake8
make check   # Format + lint
```
