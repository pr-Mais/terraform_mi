# Dataset Construction

We constructed our Infrastructure-as-Code (IaC) dataset through a systematic three-phase repository mining and filtering pipeline designed to identify high-quality, actively maintained Terraform projects suitable for empirical maintainability analysis.

## Phase 1: Repository Discovery via Time-Based Segmentation

To systematically explore the space of Terraform repositories while circumventing GitHub's API pagination limit of 1,000 results per query, we employed a time-based segmentation strategy. We partitioned the temporal search space into monthly windows spanning from January 1, 2024, to November 29, 2025, yielding **23 distinct time windows**.

For each monthly window $W_i = [t_{start}, t_{end}]$, we issued queries to GitHub's Repository Search API with the following constraints:

$$Q_i = \text{language:HCL} \land \text{stars} \geq 5 \land \text{pushed} \in [t_{start}, t_{end}]$$

Where:
- `language:HCL` identifies repositories containing Terraform (`.tf`) files
- `stars ≥ 5` establishes a minimum community validation threshold
- `pushed ∈ [t_start, t_end]` restricts results to the temporal window

For each query $Q_i$, we retrieved up to 1,000 repositories across 10 paginated API calls (100 results per page), sorted by star count in descending order. This time-based partitioning strategy yielded **1,345 unique candidate repositories** across all temporal windows, effectively bypassing the per-query result ceiling.

## Phase 2: Multi-Stage Quality Filtering

Candidate repositories underwent sequential filtering to ensure research validity and eliminate non-production codebases. We applied the following quality gates:

### 2.1 Initial Quality Filters

1. **Archived Status**: Repositories marked as archived (inactive) were excluded
2. **Non-Research Project Exclusion**: Repositories containing template/demonstration keywords in their name or description were filtered. Excluded keywords: {`template`, `boilerplate`, `starter`, `demo`, `example`, `tutorial`, `learning`, `test`, `dummy`, `poc`, `workshop`, `sample`}
3. **License Validation**: Only repositories with declared open-source licenses were retained
4. **Community Engagement**: Repositories with zero stars or fewer than one fork were excluded

### 2.2 Research Maturity Criteria

We applied a set of criteria to ensure repositories represent non-trivial, actively maintained projects:

**C3 (Recent Activity)**: Projects must exhibit push events within 180 days (6 months) of data collection, ensuring active development and maintenance.

**Collaborative Development**: Repositories must have at least one fork, serving as a proxy for collaborative interest and community engagement. Detailed contributor analysis is deferred to Phase 3.

Following Phase 2 filtering, **1,344 repositories** remained for deep repository analysis.

## Phase 3: Git History Analysis and Maturity Assessment

Qualifying repositories were cloned locally to enable comprehensive Git history mining and application of fine-grained maturity criteria:

**C4 (IaC Ratio)**: We computed the ratio of Infrastructure-as-Code files to total repository files:

$$\text{IaC Ratio} = \frac{|\{f : f \in R \land \text{ext}(f) = \text{.tf}\}|}{|R|}$$

where $R$ denotes the set of all files in the repository. We retained repositories where IaC Ratio $\geq$ 11%, ensuring substantial infrastructure code content.

**C1 (Development Frequency)**: We analyzed commit history to compute average monthly commit frequency:

$$\text{Avg Monthly Commits} = \frac{|C|}{\Delta_{\text{months}}}$$

where $|C|$ is the total commit count and $\Delta_{\text{months}}$ represents the project lifespan in months (from first to last commit). We applied a threshold of $\geq$ 5 commits per month to identify actively developed projects.

**C2 (Core Contributor Involvement)**: To ensure collaborative, non-solo projects while avoiding extreme fragmentation, we computed the contribution ratio of the top two contributors:

$$\text{Core Ratio} = \frac{C_1 + C_2}{\sum_{i=1}^{n} C_i}$$

where $C_i$ denotes the commit count of contributor $i$ ranked by contribution volume. We retained projects where Core Ratio $\geq$ 65%, indicating sustained involvement by a core development team while allowing for broader community participation.

### Sequential Filtering Results

| Criterion | Description | Threshold | Repos Remaining | Excluded |
|-----------|-------------|-----------|-----------------|----------|
| **Initial (Post-Phase 2)** | Passed C3 + quality filters | - | 1,344 | - |
| **C4** | IaC scripts ratio | ≥ 11.0% | 1,137 | 207 |
| **C1** | Average monthly commits | ≥ 5.0 | 390 | 747 |
| **C2** | Core contributors commit ratio | ≥ 65.0% | 190 | 200 |

**Final Dataset**: **190 repositories** satisfying all quality and maturity criteria.

## Metrics Extraction and Maintainability Index Computation

For each qualifying repository, we performed static analysis on individual Terraform code blocks (resources, modules, data sources) to extract fine-grained quality metrics. We developed a domain-specific Maintainability Index (MI) ranging from 0 to 100, defined as a weighted composite of five maintainability dimensions:

$$\text{MI} = 0.25 \cdot \text{MQ} + 0.25 \cdot \text{CF} + 0.20 \cdot \text{GC} + 0.20 \cdot \text{QC} + 0.10 \cdot \text{IR}$$

Where:
- **MQ (Module Quality)**: Structural modularity, block conciseness, input parameterization
- **CF (Configuration Fidelity)**: Hard-coding prevalence, attribute density, nesting depth
- **GC (Graph Complexity)**: Cyclomatic complexity, resource coupling, dependency depth
- **QC (Quality & Compliance)**: Deprecated function usage, security anti-patterns, dynamic block prevalence
- **IR (Integration Readiness)**: Output coverage, external state dependencies

Each dimension aggregates multiple sub-metrics (17 total) through normalized scoring functions and empirically derived weights. The MI provides a holistic assessment of IaC maintainability aligned with established software engineering quality models adapted for declarative infrastructure code.

## Dataset Characteristics

Our final curated dataset comprises:
- **190 repositories** passing all quality and maturity filters
- **To be determined** individual Terraform code blocks analyzed across resources, modules, and data sources (pending metrics extraction phase)
- **Temporal coverage**: Projects with demonstrated activity from January 2024 onwards (23 monthly time windows)
- **Collaboration threshold**: Core team involvement (top-two contributors ≥65% of commits)
- **Quality baseline**: Minimum 5 GitHub stars, non-archived, licensed repositories
- **IaC content requirement**: At least 11% of repository files are Terraform scripts
- **Development activity**: Minimum 5 commits per month average across project lifespan
- **Recent activity**: Push events within 180 days (6 months) of data collection

This rigorous multi-stage methodology ensures our dataset consists exclusively of production-quality, actively maintained IaC projects representative of real-world infrastructure management practices, thereby enhancing the external validity and practical relevance of subsequent empirical analyses.
