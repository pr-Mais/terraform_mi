# Maintainability Index (MI) for Terraform/HCL

## Overview

The Maintainability Index provides a **0-100 score** representing the overall maintainability of Terraform/HCL code. This is specifically designed for Infrastructure-as-Code, focusing on resource organization, configuration clarity, dependency management, security practices, and operational readiness.

## Score Interpretation

| Score Range | Rating | Description |
|-------------|--------|-------------|
| 85-100 | Exceptional | Excellent IaC practices, highly maintainable |
| 70-84 | Good | Solid practices, production-ready |
| 55-69 | Acceptable | Some technical debt, could improve |
| 40-54 | Needs Work | Multiple issues, refactoring recommended |
| 0-39 | Poor | Significant problems, major refactoring needed |

## Calculation Formula

```
MI = (Resource Composition × 0.25) +
     (Configuration Clarity × 0.25) +
     (Dependency Management × 0.20) +
     (Security & Best Practices × 0.20) +
     (Operational Readiness × 0.10)
```

## Categories

### 1. Resource Composition (25%)

**Module Usage (40% of category)** - Max: 90
- **Optimal**: 20-60% module usage
- **Calculation**: `modules / (resources + modules)`
- **Penalties**: Exponential below 20% or above 60%

**Block Size (35% of category)** - Max: 95
- **Optimal**: 10-60 LOC, peak at 25 LOC
- **Penalties**: Below 10 LOC or above 60 LOC (exponential)

**Variable Parameterization (25% of category)** - Max: 90
- **Optimal**: 0.4-1.5 variables per block
- **Penalties**: Exponential below 0.4, linear above 1.5

### 2. Configuration Clarity (25%)

**Explicitness (40% of category)** - Max: 90
- **Optimal**: ≤25% hard-coded values
- **Calculation**: `hard_coded / num_attrs`
- **Penalties**: Exponential penalty above 25%

**Complexity (35% of category)** - Max: 90
- **Optimal**: ≤12 attributes per block
- **Acceptable**: Up to 25 attributes
- **Penalties**: Linear 12-25, exponential beyond 25

**Nesting (25% of category)** - Max: 90
- **Optimal**: 0-1 nesting depth (90)
- **Acceptable**: 2 levels (70)
- **Penalties**: Heavy penalty at 3+ levels

### 3. Dependency Management (20%)

**Complexity (35% of category)** - Max: 90
- **Optimal**: ≤4 cyclomatic complexity
- **Acceptable**: Up to 8
- **Penalties**: Linear 4-8, exponential beyond 8

**Coupling (35% of category)** - Max: 90
- **Optimal**: ≤3 dependencies
- **Acceptable**: Up to 6
- **Penalties**: Linear 3-6, exponential beyond 6

**Depth (30% of category)** - Max: 90
- **Optimal**: 0-1 dependency depth (90)
- **Acceptable**: 2-3 levels (75-60)
- **Penalties**: Linear decay

### 4. Security & Best Practices (20%)

**Deprecated Functions (40% of category)** - Max: 90
- **Penalty**: 35 points per deprecated function

**Wildcards (30% of category)** - Max: 90
- **Penalty**: 30 points per wildcard usage

**Dynamic Constructs (30% of category)** - Max: 90
- **Optimal**: 0 dynamic blocks/loops (90)
- **Acceptable**: 1-2 (80)
- **Penalties**: Linear 2-4, exponential beyond 4

### 5. Operational Readiness (10%)

**Output Completeness (50% of category)** - Max: 90
- **Optimal**: 25-75% output ratio
- **Calculation**: `outputs / resources`
- **Penalties**: Exponential below 25%, linear above 75%

**Data Source Usage (50% of category)** - Max: 90
- **Optimal**: ≤25% data sources
- **Acceptable**: Up to 40%
- **Calculation**: `data / (resources + data)`
- **Penalties**: Linear 25-40%, exponential beyond 40%

## What Makes Good IaC (70+ score)

✓ 20-60% module usage (balanced modularity)
✓ Blocks sized 10-60 LOC (concise, focused)
✓ ≤25% hard-coded values (use variables/locals)
✓ ≤12 attributes per block (simple configuration)
✓ 0-2 nesting depth (flat structure)
✓ ≤4 cyclomatic complexity (declarative)
✓ ≤3 dependencies (loose coupling)
✓ Zero deprecated/wildcard usage
✓ 0-2 dynamic constructs (predictable)
✓ 25-75% output ratio (good observability)

## Usage

```bash
# Single repository
python build_dataset.py --mode single \
  --input /path/to/repo \
  --output analysis.csv \
  --skip-github

# Multiple repositories
python build_dataset.py --mode list \
  --input repos.txt \
  --output dataset.csv
```

## Output

Each row in the CSV contains:
- `maintainability_index`: MI score (0-100)
- `block_type`: resource, module, variable, etc.
- `tm_*`: TerraMetric metrics
- `gh_*`: GitHub metadata (optional)
- `file_path`, `loc`, `code`: Block context

File-level summaries (type: `FILE_SUMMARY`) show average MI across all blocks in a file.

---

**Version**: 3.0 (Balanced IaC-Specific)
