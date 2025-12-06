# Terraform Code Quality Analysis

Tools for mining Terraform repositories and calculating HCL-specific maintainability metrics.

## Quick Start

```bash
# Interactive CLI
python main.py
```

## Workflows

### Option 1: Analyze from Repository List

```bash
# 1. Create a text file with repository names (one per line)
cat > repos.txt <<EOF
terraform-aws-modules/terraform-aws-vpc
hashicorp/terraform-provider-aws
EOF

# 2. Run analysis (automatically clones missing repos)
python main.py  # Select: Analyze repositories → Use repos.txt
```

### Option 2: Mine from GitHub (Requires GITHUB_TOKEN)

```bash
# 1. Set GitHub token
echo "GITHUB_TOKEN=your_token" > .env

# 2. Run mining and analysis
python main.py  # Select: Mine Terraform repositories
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

## Modeling

### Train Classification Models

Predict code quality (Good vs Needs Work) from metrics:

```bash
# Train both Logistic Regression and Random Forest
python train_classifier.py --input output/iac_dataset.csv

# Custom threshold (default: 70)
python train_classifier.py --threshold 75

# Adjust train/test split (default: 80/20)
python train_classifier.py --test-size 0.3
```

**Output**: Model comparison, feature importance, and performance metrics

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
