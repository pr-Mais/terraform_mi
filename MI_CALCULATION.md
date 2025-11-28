# Maintainability Index (MI) for HCL

## Overview

The HCL Maintainability Index (MI) provides a **0-100 score** representing the overall maintainability of HCL code. It is a **Domain-Specific Index (DSI)** engineered to assess the unique quality attributes of Infrastructure-as-Code (IaC), focusing on structural integrity, configuration precision, and operational stability.

## Interpreting the Score

| Score Range | Rating | Description |
| :--- | :--- | :--- |
| **85-100** | Exceptional | Excellent practices, highly maintainable code. |
| **70-84** | Good | Solid practices, ready for production use and scaling. |
| **55-69** | Acceptable | Some technical debt present; refactoring recommended. |
| **40-54** | Needs Work | Multiple systemic issues; major refactoring is required. |
| **0-39** | Poor | High maintenance risk. |

---

## The Index Formula

The final MI is a weighted composite score, reflecting the empirical impact of each category on long-term IaC maintenance effort:

$$MI = (MQ \times 0.25) + (CF \times 0.25) + (GC \times 0.20) + (QC \times 0.20) + (IR \times 0.10)$$

Where:
* **MQ**: Module Quality (Structural Modularity)
* **CF**: Configuration Fidelity (Clarity and Precision)
* **GC**: Graph Complexity (Resource Coupling and Logic)
* **QC**: Quality & Compliance (Policy and Anti-Patterns)
* **IR**: Integration Readiness (Operational Stability)

---

## I. Module Quality (MQ) - 25%

Measures the architectural integrity, reuse, and structural focus of the code.

| Sub-Metric | Raw Metric ($X$) | Optimal Range | Weight |
| :--- | :--- | :--- | :--- |
| **Module Ratio** | $M = \frac{\text{Modules}}{\text{Resources} + \text{Modules}}$ | $20\% \le M \le 60\%$ | 40% |
| **Block Conciseness (LOC)** | $L = \text{Lines of Code in Block}$ | Peak at 25 LOC ($10$ - $60$ range) | 35% |
| **Input Parameterization** | $V = \frac{\text{Variables used in Block}}{\text{Attributes in Block}}$ | $0.4 \le V \le 1.5$ | 25% |

---

## II. Configuration Fidelity (CF) - 25%

Evaluates the precision, clarity, and adaptability of resource settings.

| Sub-Metric | Raw Metric ($X$) | Optimal Range/Target | Weight |
| :--- | :--- | :--- | :--- |
| **Hard-Code Explicitness** | $H = \frac{\text{Hard-Coded Values}}{\text{Total Attributes}}$ | $H \le 25\%$ | 40% |
| **Attribute Density** | $A = \text{Attributes in Block}$ | $A \le 12$ (Acceptable up to 25) | 35% |
| **Structure Nesting Depth** | $D = \text{Max Nested Depth}$ | $D \le 1$ (Acceptable up to 2) | 25% |

---

## III. Graph Complexity (GC) - 20%

Analyzes the structural complexity and coupling of the resource dependency graph.

| Sub-Metric | Raw Metric ($X$) | Optimal Range/Target | Weight |
| :--- | :--- | :--- | :--- |
| **Procedural Complexity** | $C = \text{Cyclomatic Complexity}$ | $C \le 4$ (Acceptable up to 8) | 35% |
| **Resource Coupling** | $D = \text{Dependencies Referenced}$ | $D \le 3$ (Acceptable up to 6) | 35% |
| **Graph Depth** | $G = \text{Max Resource Depth}$ | $G \le 1$ (Acceptable up to 3) | 30% |

---

## IV. Quality & Compliance (QC) - 20%

A penalty-based system targeting critical violations and technical debt.

| Sub-Metric | Raw Metric ($P$) | Penalty/Optimal | Weight |
| :--- | :--- | :--- | :--- |
| **Deprecated Function Use** | $P_D = \text{Count of Deprecated}$ | $\mathbf{35}$ points penalty per instance | 40% |
| **Overly Permissive Constructs** | $P_W = \text{Count of Wildcard Usage}$ | $\mathbf{30}$ points penalty per instance | 30% |
| **Dynamic Generation Count** | $P_{Dyn} = \text{Count of Dynamic Blocks}$ | $P_{Dyn} \le 2$ (Acceptable up to 4) | 30% |

---

## V. Integration Readiness (IR) - 10%

Assesses the module's suitability for production deployment and its stability within a larger ecosystem.

| Sub-Metric | Raw Metric ($X$) | Optimal Range/Target | Weight |
| :--- | :--- | :--- | :--- |
| **Module Output Ratio** | $O = \frac{\text{Outputs}}{\text{Resources}}$ | $25\% \le O \le 75\%$ | 50% |
| **External State Dependence** | $D = \frac{\text{Data Blocks}}{\text{Resources} + \text{Data Blocks}}$ | $D \le 25\%$ (Acceptable up to 40%) | 50% |

---

## Best Practice Summary (MI $\ge 70$)

A production-ready HCL module (MI $\ge 70$) typically adheres to these standards:

* **Modularity:** Uses modules for $\mathbf{20\% \text{ to } 60\%}$ of total resources.
* **Clarity:** $\mathbf{\le 25\%}$ of attributes are hard-coded literals.
* **Structure:** Blocks are concise (peak at $\mathbf{25}$ LOC) and nesting is kept to $\mathbf{0 \text{ or } 1}$ level deep.
* **Coupling:** Resources rely on $\mathbf{\le 3}$ other resources on average.
* **Compliance:** Contains $\mathbf{zero}$ deprecated functions or security wildcards.
* **Usability:** Outputs cover $\mathbf{25\% \text{ to } 75\%}$ of resources created, and external data reliance is $\mathbf{\le 25\%}$.