"""
Dataset Builder for IaC Analysis
Combines Terraform code blocks, TerraMetric quality metrics, and GitHub attributes
"""

import os
import csv
import json
import subprocess
import time
import re
from typing import Dict, List, Any

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Configuration
CLONE_DIRECTORY = "iac_corpus"
FINAL_REPO_LIST_FILE = "iac_repositories_final_filtered.txt"
OUTPUT_DIR = "output"
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "iac_dataset.csv")
TERRAMETRIC_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "terrametric_temp")
GITHUB_API_URL = "https://api.github.com/repos"

# Ensure output directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TERRAMETRIC_OUTPUT_DIR, exist_ok=True)


class TerraformCodeExtractor:
    """Extracts Terraform code blocks from .tf files"""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def extract_blocks(self) -> List[Dict[str, Any]]:
        """
        Extract all Terraform resource blocks, modules, data sources, etc.
        Returns a list of code blocks with metadata
        """
        blocks = []

        for root, dirs, files in os.walk(self.repo_path):
            # Skip .terraform directories
            dirs[:] = [d for d in dirs if not d.startswith(".terraform")]

            for file in files:
                if file.endswith(".tf"):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.repo_path)

                    try:
                        blocks.extend(self._parse_tf_file(file_path, relative_path))
                    except (OSError, UnicodeDecodeError, ValueError) as e:
                        print(f"Error parsing {file_path}: {e}")
                        continue

        return blocks

    def _parse_tf_file(self, file_path: str, relative_path: str) -> List[Dict[str, Any]]:
        """Parse a single .tf file and extract blocks"""
        blocks = []

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.split("\n")

        # Regex patterns for different block types
        patterns = {
            "resource": r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{',
            "module": r'module\s+"([^"]+)"\s*\{',
            "data": r'data\s+"([^"]+)"\s+"([^"]+)"\s*\{',
            "variable": r'variable\s+"([^"]+)"\s*\{',
            "output": r'output\s+"([^"]+)"\s*\{',
            "locals": r"locals\s*\{",
            "provider": r'provider\s+"([^"]+)"\s*\{',
            "terraform": r"terraform\s*\{",
        }

        for block_type, pattern in patterns.items():
            for match in re.finditer(pattern, content):
                start_pos = match.start()
                start_line = content[:start_pos].count("\n") + 1

                # Find the corresponding closing brace
                end_line, block_content = self._extract_block(lines, start_line - 1)

                if end_line > 0:
                    # Extract block name
                    if block_type in ["resource", "data"]:
                        block_name = f"{match.group(1)}.{match.group(2)}"
                    elif block_type in ["module", "variable", "output", "provider"]:
                        block_name = match.group(1)
                    else:
                        block_name = block_type

                    blocks.append(
                        {
                            "file_path": relative_path,
                            "block_type": block_type,
                            "block_name": block_name,
                            "start_line": start_line,
                            "end_line": end_line,
                            "code": block_content,
                            "loc": len(block_content.split("\n")),
                        }
                    )

        return blocks

    def _extract_block(self, lines: List[str], start_idx: int) -> tuple:
        """Extract a block by matching braces"""
        brace_count = 0
        in_block = False
        block_lines = []

        for i in range(start_idx, len(lines)):
            line = lines[i]
            block_lines.append(line)

            # Count braces (simple approach - doesn't handle strings perfectly)
            for char in line:
                if char == "{":
                    brace_count += 1
                    in_block = True
                elif char == "}":
                    brace_count -= 1

                if in_block and brace_count == 0:
                    return i + 1, "\n".join(block_lines)

        return -1, ""


class TerraMetricRunner:
    """Runs TerraMetric on Terraform code blocks"""

    def __init__(self):
        # Try to find Java in common locations
        java_candidates = [
            os.environ.get("JAVA_HOME", "") + "/bin/java",
            "/opt/homebrew/Cellar/openjdk@11/11.0.29/bin/java",
            "/usr/bin/java",
            "java",  # Rely on PATH
        ]
        self.java_path = None
        for java in java_candidates:
            if java and (os.path.exists(java) or java == "java"):
                self.java_path = java
                break

        if not self.java_path:
            self.java_path = "java"  # Fallback to PATH

        # Use relative path for TerraMetric JAR
        project_root = os.path.dirname(os.path.abspath(__file__))
        self.terrametric_jar = os.path.join(
            project_root,
            "terametrics/target/terraform_metrics-1.0-SNAPSHOT-jar-with-dependencies.jar",
        )

    def check_installation(self) -> bool:
        """Check if TerraMetric is installed"""
        try:
            if not os.path.exists(self.java_path):
                return False
            if not os.path.exists(self.terrametric_jar):
                return False
            result = subprocess.run(
                [self.java_path, "-jar", self.terrametric_jar, "-h"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def analyze_code(self, code: str, temp_file: str = "temp_analysis.tf") -> Dict[str, Any]:
        """
        Analyze a Terraform code block using TerraMetric
        Returns quality metrics
        """
        # Write code to temporary file
        temp_path = os.path.join(TERRAMETRIC_OUTPUT_DIR, temp_file)
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Output JSON path
        output_json = os.path.join(TERRAMETRIC_OUTPUT_DIR, f"{temp_file}.json")

        try:
            # Run TerraMetric
            result = subprocess.run(
                [
                    self.java_path,
                    "-jar",
                    self.terrametric_jar,
                    "-b",
                    "--file",
                    temp_path,
                    "--target",
                    output_json,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode == 0 and os.path.exists(output_json):
                with open(output_json, "r", encoding="utf-8") as f:
                    metrics = json.load(f)
                return self._parse_metrics(metrics)
            return self._empty_metrics()

        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as e:
            print(f"Error running TerraMetric: {e}")
            return self._empty_metrics()
        finally:
            # Clean up temp files
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(output_json):
                os.remove(output_json)

    def _parse_metrics(self, raw_metrics: Dict) -> Dict[str, Any]:
        """Parse TerraMetric output into standardized format"""
        # TerraMetric returns {'head': {...}, 'data': [{block_metrics}, ...]}
        head = raw_metrics.get("head", {})
        data = raw_metrics.get("data", [])

        # For single-block files, extract first block's detailed metrics
        block_data = data[0] if data else {}

        # Aggregate metrics from all blocks in the file
        total_complexity = sum(block.get("sumMccabeCC", 0) for block in data)
        max_depth = max((block.get("maxDepthNestedBlocks", 0) for block in data), default=0)
        total_tokens = sum(block.get("numTokens", 0) for block in data)
        total_dependencies = sum(
            (
                block.get("numImplicitDependentResources", 0)
                + block.get("numExplicitResourceDependency", 0)
            )
            for block in data
        )

        # Extract additional detailed metrics from block
        num_string_values = block_data.get("numStringValues", 0)
        num_hard_coded_values = block_data.get("numLiteralExpression", 0)
        num_loops = block_data.get("numLoops", 0)
        num_conditions = block_data.get("numConditions", 0)
        num_function_calls = block_data.get("numFunctionCall", 0)
        num_deprecated = block_data.get("numDeprecatedFunctions", 0)
        num_wildcards = block_data.get("numWildCardSuffixString", 0) + block_data.get(
            "numStarString", 0
        )
        graph_depth = block_data.get("depthOfBlock", 0)
        num_attrs = block_data.get("numAttrs", 0)
        num_vars_in_block = block_data.get("numVars", 0)

        return {
            "tm_loc": head.get("num_lines_of_code", 0),
            "tm_num_variables": head.get("num_variables", 0),
            "tm_num_outputs": head.get("num_outputs", 0),
            "tm_complexity": total_complexity,
            "tm_nesting_depth": max_depth,
            "tm_num_dependencies": total_dependencies,
            "tm_num_resources": head.get("num_resources", 0),
            "tm_num_modules": head.get("num_modules", 0),
            "tm_num_blocks": head.get("num_blocks", 0),
            "tm_num_data": head.get("num_data", 0),
            "tm_num_providers": head.get("num_providers", 0),
            "tm_num_tokens": total_tokens,
            # Additional block-level metrics for MI calculation
            "tm_num_string_values": num_string_values,
            "tm_num_hard_coded": num_hard_coded_values,
            "tm_num_loops": num_loops,
            "tm_num_conditions": num_conditions,
            "tm_num_function_calls": num_function_calls,
            "tm_num_deprecated": num_deprecated,
            "tm_num_wildcards": num_wildcards,
            "tm_graph_depth": graph_depth,
            "tm_num_attrs": num_attrs,
            "tm_num_vars_in_block": num_vars_in_block,
        }

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics if analysis fails"""
        return {
            "tm_loc": 0,
            "tm_num_variables": 0,
            "tm_num_outputs": 0,
            "tm_complexity": 0,
            "tm_nesting_depth": 0,
            "tm_num_dependencies": 0,
            "tm_num_resources": 0,
            "tm_num_modules": 0,
            "tm_num_blocks": 0,
            "tm_num_data": 0,
            "tm_num_providers": 0,
            "tm_num_tokens": 0,
            "tm_num_string_values": 0,
            "tm_num_hard_coded": 0,
            "tm_num_loops": 0,
            "tm_num_conditions": 0,
            "tm_num_function_calls": 0,
            "tm_num_deprecated": 0,
            "tm_num_wildcards": 0,
            "tm_graph_depth": 0,
            "tm_num_attrs": 0,
            "tm_num_vars_in_block": 0,
        }


class GitHubAttributesFetcher:
    """Fetches GitHub repository attributes via API"""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.cache = {}  # Cache to avoid repeated API calls

    def get_repo_attributes(self, repo_full_name: str) -> Dict[str, Any]:
        """Fetch comprehensive GitHub repository attributes"""

        # Check cache first
        if repo_full_name in self.cache:
            return self.cache[repo_full_name]

        try:
            # Get repository details
            repo_url = f"{GITHUB_API_URL}/{repo_full_name}"
            response = requests.get(repo_url, headers=self.headers, timeout=30)

            if response.status_code == 403:
                time.sleep(60)  # Rate limit wait
                response = requests.get(repo_url, headers=self.headers, timeout=30)

            response.raise_for_status()
            repo_data = response.json()

            # Get contributors count
            contributors_url = f"{GITHUB_API_URL}/{repo_full_name}/contributors"
            contributors_response = requests.get(
                contributors_url,
                headers=self.headers,
                params={"per_page": 1, "anon": "true"},
                timeout=30,
            )

            contributors_count = 0
            if contributors_response.status_code == 200:
                # Get count from Link header
                link_header = contributors_response.headers.get("Link", "")
                if "last" in link_header:
                    # Parse last page number
                    match = re.search(r'page=(\d+)>; rel="last"', link_header)
                    if match:
                        contributors_count = int(match.group(1))
                else:
                    contributors_count = len(contributors_response.json())

            # Get commit count
            commits_url = f"{GITHUB_API_URL}/{repo_full_name}/commits"
            commits_response = requests.get(
                commits_url, headers=self.headers, params={"per_page": 1}, timeout=30
            )

            commit_count = 0
            if commits_response.status_code == 200:
                link_header = commits_response.headers.get("Link", "")
                if "last" in link_header:
                    match = re.search(r'page=(\d+)>; rel="last"', link_header)
                    if match:
                        commit_count = int(match.group(1))
                else:
                    commit_count = len(commits_response.json()) if commits_response.json() else 0

            attributes = {
                "gh_stars": repo_data.get("stargazers_count", 0),
                "gh_forks": repo_data.get("forks_count", 0),
                "gh_watchers": repo_data.get("watchers_count", 0),
                "gh_open_issues": repo_data.get("open_issues_count", 0),
                "gh_license": (
                    repo_data.get("license", {}).get("spdx_id", "None")
                    if repo_data.get("license")
                    else "None"
                ),
                "gh_created_at": repo_data.get("created_at", ""),
                "gh_updated_at": repo_data.get("updated_at", ""),
                "gh_pushed_at": repo_data.get("pushed_at", ""),
                "gh_language": repo_data.get("language", "Unknown"),
                "gh_size_kb": repo_data.get("size", 0),
                "gh_contributors": contributors_count,
                "gh_commits": commit_count,
                "gh_description": (repo_data.get("description", "") or "")
                .replace("\n", " ")
                .replace(",", ";"),
                "gh_topics": ",".join(repo_data.get("topics", [])),
                "gh_has_wiki": repo_data.get("has_wiki", False),
                "gh_has_issues": repo_data.get("has_issues", False),
                "gh_has_projects": repo_data.get("has_projects", False),
                "gh_default_branch": repo_data.get("default_branch", "main"),
            }

            # Cache the result
            self.cache[repo_full_name] = attributes

            # Rate limit handling
            time.sleep(0.5)

            return attributes

        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"Error fetching GitHub attributes for {repo_full_name}: {e}")
            return self._empty_attributes()

    def _empty_attributes(self) -> Dict[str, Any]:
        """Return empty attributes if fetch fails"""
        return {
            "gh_stars": 0,
            "gh_forks": 0,
            "gh_watchers": 0,
            "gh_open_issues": 0,
            "gh_license": "None",
            "gh_created_at": "",
            "gh_updated_at": "",
            "gh_pushed_at": "",
            "gh_language": "Unknown",
            "gh_size_kb": 0,
            "gh_contributors": 0,
            "gh_commits": 0,
            "gh_description": "",
            "gh_topics": "",
            "gh_has_wiki": False,
            "gh_has_issues": False,
            "gh_has_projects": False,
            "gh_default_branch": "main",
        }


class MaintainabilityIndexCalculator:
    """
    Calculates Maintainability Index for Terraform/HCL code blocks.

    This implementation is tailored for Infrastructure-as-Code with focus on:
    - Resource organization and composition
    - Configuration clarity and explicitness
    - Dependency management
    - Security and best practices
    - Operational maintainability
    """

    @staticmethod
    def calculate_mi(tm_metrics: Dict[str, Any], block: Dict[str, Any]) -> float:
        """
        Calculate HCL-specific Maintainability Index (0-100).

        Weighted Categories:
        1. Resource Composition (25%) - How well resources are organized
        2. Configuration Clarity (25%) - Readability and explicitness
        3. Dependency Management (20%) - Complexity of resource relationships
        4. Security & Best Practices (20%) - Safe coding patterns
        5. Operational Readiness (10%) - Ease of operations and changes

        Args:
            tm_metrics: TerraMetric analysis results
            block: Code block metadata

        Returns:
            Maintainability score (0-100), higher is better
        """
        calc = MaintainabilityIndexCalculator

        # Extract metrics with safe defaults
        metrics = calc._extract_metrics(tm_metrics, block)

        # Calculate category scores
        composition_score = calc._calculate_composition_score(metrics)
        clarity_score = calc._calculate_clarity_score(metrics)
        dependency_score = calc._calculate_dependency_score(metrics)
        security_score = calc._calculate_security_score(metrics)
        operational_score = calc._calculate_operational_score(metrics)

        # Weighted final score
        mi = (
            composition_score * 0.25
            + clarity_score * 0.25
            + dependency_score * 0.20
            + security_score * 0.20
            + operational_score * 0.10
        )

        return round(mi, 2)

    @staticmethod
    def _extract_metrics(tm_metrics: Dict[str, Any], block: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize all metrics needed for MI calculation."""
        return {
            # File-level metrics
            "loc": tm_metrics.get("tm_loc", 0),
            "num_variables": tm_metrics.get("tm_num_variables", 0),
            "num_outputs": tm_metrics.get("tm_num_outputs", 0),
            "num_resources": tm_metrics.get("tm_num_resources", 0),
            "num_modules": tm_metrics.get("tm_num_modules", 0),
            "num_data": tm_metrics.get("tm_num_data", 0),
            "num_providers": tm_metrics.get("tm_num_providers", 0),
            "num_blocks": tm_metrics.get("tm_num_blocks", 0),
            # Block-level metrics
            "block_loc": block.get("loc", 0),
            "block_type": block.get("block_type", ""),
            "complexity": tm_metrics.get("tm_complexity", 0),
            "nesting_depth": tm_metrics.get("tm_nesting_depth", 0),
            "graph_depth": tm_metrics.get("tm_graph_depth", 0),
            # Quality metrics
            "num_attrs": tm_metrics.get("tm_num_attrs", 0),
            "num_hard_coded": tm_metrics.get("tm_num_hard_coded", 0),
            "num_vars_in_block": tm_metrics.get("tm_num_vars_in_block", 0),
            "num_dependencies": tm_metrics.get("tm_num_dependencies", 0),
            # Control flow
            "num_loops": tm_metrics.get("tm_num_loops", 0),
            "num_conditions": tm_metrics.get("tm_num_conditions", 0),
            "num_function_calls": tm_metrics.get("tm_num_function_calls", 0),
            # Anti-patterns
            "num_deprecated": tm_metrics.get("tm_num_deprecated", 0),
            "num_wildcards": tm_metrics.get("tm_num_wildcards", 0),
        }

    @staticmethod
    def _calculate_composition_score(m: Dict[str, Any]) -> float:
        """
        Resource Composition (25%): Evaluates how well resources are organized.

        - Module usage ratio: Prefer module composition over direct resources
        - Resource block size: Smaller, focused blocks are better
        - Variable parameterization: Appropriate use of variables
        """
        # 1. Module composition ratio (40% of category)
        # Modules promote reusability
        total_infra = m["num_resources"] + m["num_modules"]
        if total_infra > 0:
            module_ratio = m["num_modules"] / total_infra
            # Optimal: 20-60% modules (balanced range)
            if 0.2 <= module_ratio <= 0.6:
                module_score = 90
            elif module_ratio < 0.2:
                # Gradual penalty for low modularity
                module_score = max(40, 90 * ((module_ratio / 0.2) ** 1.2))
            else:
                # Gradual penalty for over-modularization
                module_score = max(30, 90 - ((module_ratio - 0.6) * 150))
        else:
            module_score = 60  # Neutral for non-infra blocks

        # 2. Block size appropriateness (35% of category)
        # Concise blocks are better (10-60 LOC)
        block_loc = m["block_loc"]
        if block_loc == 0:
            size_score = 70
        elif 10 <= block_loc <= 60:
            # Peak at 25 LOC
            if block_loc <= 25:
                size_score = 70 + ((block_loc - 10) / 15) * 25  # 70-95
            else:
                size_score = 95 - ((block_loc - 25) / 35) * 15  # 95-80
        elif block_loc < 10:
            size_score = 50 + (block_loc / 10) * 20
        else:
            # Penalty for large blocks
            size_score = max(20, 80 - ((block_loc - 60) ** 1.1) / 5)

        # 3. Variable usage (25% of category)
        # Good parameterization
        var_ratio = m["num_variables"] / max(m["num_blocks"], 1)
        if 0.4 <= var_ratio <= 1.5:  # Reasonable range
            var_score = 90
        elif var_ratio < 0.4:
            var_score = max(50, 90 * ((var_ratio / 0.4) ** 1.1))
        else:
            var_score = max(40, 90 - ((var_ratio - 1.5) * 20))

        return module_score * 0.40 + size_score * 0.35 + var_score * 0.25

    @staticmethod
    def _calculate_clarity_score(m: Dict[str, Any]) -> float:
        """
        Configuration Clarity (25%): Readability and explicitness of the code.

        - Hard-coded values: Penalize magic numbers/strings
        - Attribute density: Reasonable configuration complexity
        - Nesting depth: Avoid deep nesting
        """
        # 1. Explicitness (40% of category)
        # Prefer variables/locals over hard-coded values
        if m["num_attrs"] > 0:
            hard_coded_ratio = m["num_hard_coded"] / m["num_attrs"]
            # Allow up to 25% hard-coding (some is acceptable for names/tags)
            if hard_coded_ratio <= 0.25:
                explicit_score = 90
            else:
                # Gradual penalty for excessive hard-coding
                explicit_score = max(30, 90 * ((0.25 / hard_coded_ratio) ** 1.2))
        else:
            explicit_score = 90

        # 2. Configuration complexity (35% of category)
        # Reasonable attribute count
        num_attrs = m["num_attrs"]
        if num_attrs <= 12:
            attr_score = 90
        elif num_attrs <= 25:
            # Gradual penalty 12-25 attrs
            attr_score = 90 - ((num_attrs - 12) * 3)
        else:
            # Steeper penalty beyond 25
            attr_score = max(20, 51 - (((num_attrs - 25) ** 1.2) / 3))

        # 3. Structural clarity (25% of category)
        # Prefer flat structure but allow some nesting
        nesting = m["nesting_depth"]
        if nesting <= 1:
            nesting_score = 90
        elif nesting <= 2:
            nesting_score = 70  # Acceptable level of nesting
        elif nesting <= 3:
            nesting_score = 45  # Penalty at nesting=3
        else:
            # Heavy penalty for deep nesting
            nesting_score = max(15, 45 - ((nesting - 3) * 12))

        return explicit_score * 0.40 + attr_score * 0.35 + nesting_score * 0.25

    @staticmethod
    def _calculate_dependency_score(m: Dict[str, Any]) -> float:
        """
        Dependency Management (20%): Complexity of resource relationships.

        - Cyclomatic complexity: Control flow complexity
        - Dependency count: Number of resource dependencies
        - Graph depth: Depth of dependency chains
        """
        # 1. Cyclomatic complexity (35% of category)
        # Declarative IaC should have low control flow complexity
        complexity = m["complexity"]
        if complexity <= 4:
            complexity_score = 90
        elif complexity <= 8:
            # Gradual penalty 4-8
            complexity_score = 90 - ((complexity - 4) * 8)
        else:
            # Steeper penalty beyond 8
            complexity_score = max(20, 58 - (((complexity - 8) ** 1.2) / 2))

        # 2. Dependency coupling (35% of category)
        # Moderate coupling is acceptable
        deps = m["num_dependencies"]
        if deps <= 3:
            dep_score = 90
        elif deps <= 6:
            # Gradual penalty 3-6
            dep_score = 90 - ((deps - 3) * 10)
        else:
            # Steeper penalty for tight coupling
            dep_score = max(20, 60 - (((deps - 6) ** 1.2) / 2))

        # 3. Dependency depth (30% of category)
        # Shallow dependency chains preferred
        graph_depth = m["graph_depth"]
        if graph_depth <= 1:
            depth_score = 90
        elif graph_depth <= 3:
            depth_score = 90 - ((graph_depth - 1) * 15)  # 90, 75, 60
        else:
            # Penalty for deep chains
            depth_score = max(20, 60 - ((graph_depth - 3) * 10))

        return complexity_score * 0.35 + dep_score * 0.35 + depth_score * 0.30

    @staticmethod
    def _calculate_security_score(m: Dict[str, Any]) -> float:
        """
        Security & Best Practices (20%): Safe coding patterns.

        - No deprecated functions
        - No wildcard usage in security contexts
        - Controlled use of dynamic blocks/loops
        """
        # 1. No deprecated usage (40% of category)
        # Deprecated functions are security risks
        deprecated_score = max(20, 90 - (m["num_deprecated"] * 35))

        # 2. No wildcard/star usage (30% of category)
        # Wildcards in security contexts are risky
        wildcard_score = max(20, 90 - (m["num_wildcards"] * 30))

        # 3. Controlled dynamism (30% of category)
        # Some dynamism is acceptable for flexibility
        dynamic_count = m["num_loops"] + m["num_conditions"]
        if dynamic_count == 0:
            dynamic_score = 90
        elif dynamic_count <= 2:
            dynamic_score = 80  # Acceptable level
        elif dynamic_count <= 4:
            dynamic_score = 80 - ((dynamic_count - 2) * 15)  # 80, 65, 50
        else:
            # Penalty for excessive dynamic behavior
            dynamic_score = max(20, 50 - ((dynamic_count - 4) * 10))

        return deprecated_score * 0.40 + wildcard_score * 0.30 + dynamic_score * 0.30

    @staticmethod
    def _calculate_operational_score(m: Dict[str, Any]) -> float:
        """
        Operational Readiness (10%): Ease of operations and changes.

        - Output definitions: Proper outputs for observability
        - Data source usage: Appropriate external data usage
        """
        # 1. Output completeness (50% of category)
        # Resources should expose useful outputs
        if m["num_resources"] > 0:
            output_ratio = m["num_outputs"] / m["num_resources"]
            # Reasonable output ratio: 25-75%
            if 0.25 <= output_ratio <= 0.75:
                output_score = 90
            elif output_ratio < 0.25:
                # Gradual penalty for insufficient outputs
                output_score = max(30, 90 * ((output_ratio / 0.25) ** 1.2))
            else:
                # Gradual penalty for excessive outputs
                output_score = max(40, 90 - ((output_ratio - 0.75) * 60))
        else:
            output_score = 70  # Neutral for non-resource blocks

        # 2. Data source usage (50% of category)
        # Moderate use of data sources is fine
        data_ratio = m["num_data"] / max(m["num_resources"] + m["num_data"], 1)
        if data_ratio <= 0.25:
            data_score = 90
        elif data_ratio <= 0.4:
            # Gradual penalty 25-40%
            data_score = 90 - ((data_ratio - 0.25) * 100)
        else:
            # Steeper penalty for data-heavy configs
            data_score = max(30, 75 - (((data_ratio - 0.4) ** 1.2) * 80))

        return output_score * 0.50 + data_score * 0.50


class DatasetBuilder:
    """
    Orchestrates IaC dataset building from Terraform repositories.

    Supports analyzing single repositories or multiple repositories from a list.
    """

    # CSV column headers
    CSV_HEADERS = [
        # Repository info
        "repository",
        "file_path",
        # Code block info
        "block_type",
        "block_name",
        "start_line",
        "end_line",
        "loc",
        "code",
        # TerraMetric metrics
        "tm_loc",
        "tm_num_variables",
        "tm_num_outputs",
        "tm_complexity",
        "tm_nesting_depth",
        "tm_num_dependencies",
        "tm_num_resources",
        "tm_num_modules",
        "tm_num_blocks",
        "tm_num_data",
        "tm_num_providers",
        "tm_num_tokens",
        "tm_num_string_values",
        "tm_num_hard_coded",
        "tm_num_loops",
        "tm_num_conditions",
        "tm_num_function_calls",
        "tm_num_deprecated",
        "tm_num_wildcards",
        "tm_graph_depth",
        "tm_num_attrs",
        "tm_num_vars_in_block",
        # Maintainability Index
        "maintainability_index",
        # GitHub attributes
        "gh_stars",
        "gh_forks",
        "gh_watchers",
        "gh_open_issues",
        "gh_license",
        "gh_created_at",
        "gh_updated_at",
        "gh_pushed_at",
        "gh_language",
        "gh_size_kb",
        "gh_contributors",
        "gh_commits",
        "gh_description",
        "gh_topics",
        "gh_has_wiki",
        "gh_has_issues",
        "gh_has_projects",
        "gh_default_branch",
    ]

    def __init__(self, github_token: str = None, skip_github: bool = False):
        """
        Initialize the dataset builder.

        Args:
            github_token: GitHub API token (optional, for fetching repo attributes)
            skip_github: Skip GitHub API calls (useful for local analysis)
        """
        self.terrametric_runner = TerraMetricRunner()
        self.github_fetcher = GitHubAttributesFetcher(github_token) if github_token else None
        self.mi_calculator = MaintainabilityIndexCalculator()
        self.skip_github = skip_github or not github_token

        # Check TerraMetric installation
        if not self.terrametric_runner.check_installation():
            print("[WARNING] TerraMetric not found. Metrics will be empty.")
            print("Install TerraMetric or provide the correct path.")
            self.use_terrametric = False
        else:
            self.use_terrametric = True
            print("[INFO] TerraMetric found and ready.")

    def build_dataset_from_list(self, repo_list_file: str, output_csv: str):
        """
        Build dataset from a list of repositories.

        Args:
            repo_list_file: Path to file containing repository names (one per line)
            output_csv: Output CSV file path
        """
        try:
            with open(repo_list_file, "r", encoding="utf-8") as f:
                repositories = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"[ERROR] Repository list file not found: {repo_list_file}")
            return

        print(f"Building dataset from {len(repositories)} repositories...")
        self._process_repositories(repositories, output_csv)

    def build_dataset_from_repo(self, repo_path: str, output_csv: str, repo_name: str = None):
        """
        Build dataset from a single repository.

        Args:
            repo_path: Local path to the repository
            output_csv: Output CSV file path
            repo_name: Repository name for identification (default: directory name)
        """
        if not os.path.isdir(repo_path):
            print(f"[ERROR] Repository path not found: {repo_path}")
            return

        repo_name = repo_name or os.path.basename(repo_path)
        print(f"Building dataset from single repository: {repo_name}")

        # Process as a single repository
        with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.CSV_HEADERS)
            writer.writeheader()

            total_blocks = self._process_single_repository(
                repo_name, repo_path, writer, idx=1, total=1
            )

        print("\n" + "=" * 80)
        print("Dataset building complete!")
        print(f"Total code blocks extracted: {total_blocks}")
        print(f"Dataset saved to: {output_csv}")
        print("=" * 80)

    def _process_repositories(self, repositories: List[str], output_csv: str):
        """Process multiple repositories and write to CSV."""
        with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.CSV_HEADERS)
            writer.writeheader()

            total_blocks = 0

            for idx, repo_full_name in enumerate(repositories, 1):
                repo_dir_name = repo_full_name.replace("/", "_")
                repo_path = os.path.join(CLONE_DIRECTORY, repo_dir_name)

                if not os.path.isdir(repo_path):
                    print(
                        f"\n[{idx}/{len(repositories)}] [SKIP] {repo_full_name} - not found locally"
                    )
                    continue

                blocks = self._process_single_repository(
                    repo_full_name, repo_path, writer, idx, len(repositories)
                )
                total_blocks += blocks

                if (idx % 10) == 0:
                    print(f"  Progress: {total_blocks} total blocks so far")

        print("\n" + "=" * 80)
        print("Dataset building complete!")
        print(f"Total repositories processed: {len(repositories)}")
        print(f"Total code blocks extracted: {total_blocks}")
        print(f"Dataset saved to: {output_csv}")
        print("=" * 80)

    def _process_single_repository(
        self, repo_name: str, repo_path: str, writer: csv.DictWriter, idx: int, total: int
    ) -> int:
        """
        Process a single repository and write blocks to CSV.

        Args:
            repo_name: Repository name/identifier
            repo_path: Local path to repository
            writer: CSV writer
            idx: Current repository index
            total: Total number of repositories

        Returns:
            Number of blocks processed
        """
        print(f"\n[{idx}/{total}] Processing: {repo_name}")

        # Get GitHub attributes if available
        gh_attrs = {}
        if not self.skip_github and self.github_fetcher:
            gh_attrs = self.github_fetcher.get_repo_attributes(repo_name)
        else:
            gh_attrs = self.github_fetcher._empty_attributes() if self.github_fetcher else {}

        # Extract Terraform code blocks
        extractor = TerraformCodeExtractor(repo_path)
        blocks = extractor.extract_blocks()
        print(f"  Extracted {len(blocks)} code blocks")

        # Group blocks by file and calculate MI for each
        file_mi_scores = {}
        file_blocks = {}

        for block_idx, block in enumerate(blocks):
            file_path = block["file_path"]

            # Analyze block
            tm_metrics = self._analyze_block(block, repo_name, block_idx)
            mi = self.mi_calculator.calculate_mi(tm_metrics, block)

            # Write block-level row
            row = self._create_csv_row(repo_name, block, tm_metrics, mi, gh_attrs)
            writer.writerow(row)

            # Store for file-level average
            if file_path not in file_mi_scores:
                file_mi_scores[file_path] = []
                file_blocks[file_path] = []
            file_mi_scores[file_path].append(mi)
            file_blocks[file_path].append(block)

        # Write file-level summary rows
        for file_path, mi_scores in file_mi_scores.items():
            avg_mi = sum(mi_scores) / len(mi_scores)
            file_row = self._create_file_summary_row(
                repo_name, file_path, file_blocks[file_path], avg_mi, gh_attrs
            )
            writer.writerow(file_row)

        return len(blocks)

    def _analyze_block(
        self, block: Dict[str, Any], repo_name: str, block_idx: int
    ) -> Dict[str, Any]:
        """Analyze a code block with TerraMetric."""
        if self.use_terrametric:
            safe_repo_name = repo_name.replace("/", "_")
            temp_file = f"temp_{safe_repo_name}_{block_idx}.tf"
            return self.terrametric_runner.analyze_code(block["code"], temp_file)
        return self.terrametric_runner._empty_metrics()

    def _create_csv_row(
        self,
        repo_name: str,
        block: Dict[str, Any],
        tm_metrics: Dict[str, Any],
        mi: float,
        gh_attrs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a CSV row from block data."""
        return {
            "repository": repo_name,
            "file_path": block["file_path"],
            "block_type": block["block_type"],
            "block_name": block["block_name"],
            "start_line": block["start_line"],
            "end_line": block["end_line"],
            "loc": block["loc"],
            "code": block["code"].replace("\n", "\\n"),
            **tm_metrics,
            "maintainability_index": mi,
            **gh_attrs,
        }

    def _create_file_summary_row(
        self,
        repo_name: str,
        file_path: str,
        blocks: List[Dict[str, Any]],
        avg_mi: float,
        gh_attrs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a file-level summary row with average MI."""
        total_loc = sum(block["loc"] for block in blocks)
        empty_metrics = self.terrametric_runner._empty_metrics()

        return {
            "repository": repo_name,
            "file_path": file_path,
            "block_type": "FILE_SUMMARY",
            "block_name": f"{len(blocks)} blocks",
            "start_line": min(block["start_line"] for block in blocks),
            "end_line": max(block["end_line"] for block in blocks),
            "loc": total_loc,
            "code": "",
            **empty_metrics,
            "maintainability_index": round(avg_mi, 2),
            **gh_attrs,
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build IaC dataset from Terraform repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze multiple repos from a list (output: output/dataset.csv)
  python build_dataset.py --mode list --input repos.txt --output output/dataset.csv

  # Analyze a single repository (output: output/my_analysis.csv)
  python build_dataset.py --mode single --input /path/to/repo --output output/my_analysis.csv

  # Use default output location (output/iac_dataset.csv)
  python build_dataset.py --mode list --input repos.txt

  # Skip GitHub API calls for faster local-only analysis
  python build_dataset.py --mode single --input ./my-repo --output output/local.csv --skip-github
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["list", "single"],
        default="list",
        help='Processing mode: "list" for multiple repos, "single" for one repo (default: list)',
    )
    parser.add_argument(
        "--input",
        default=FINAL_REPO_LIST_FILE,
        help='Input: file list for "list" mode, or repo path for "single" mode',
    )
    parser.add_argument(
        "--output", default=OUTPUT_CSV, help=f"Output CSV file (default: {OUTPUT_CSV})"
    )
    parser.add_argument(
        "--repo-name", help="Repository name for single mode (default: directory name)"
    )
    parser.add_argument(
        "--skip-github",
        action="store_true",
        help="Skip GitHub API calls (useful for local analysis)",
    )

    args = parser.parse_args()

    # Initialize builder
    if args.skip_github:
        print("[INFO] Skipping GitHub API calls")
        builder = DatasetBuilder(skip_github=True)
    elif GITHUB_TOKEN:
        builder = DatasetBuilder(github_token=GITHUB_TOKEN)
    else:
        print("[WARNING] GITHUB_TOKEN not found. GitHub attributes will be empty.")
        print("Set GITHUB_TOKEN in .env file to include repository metadata.")
        builder = DatasetBuilder(skip_github=True)

    # Execute based on mode
    if args.mode == "list":
        builder.build_dataset_from_list(args.input, args.output)
    else:  # single
        builder.build_dataset_from_repo(args.input, args.output, args.repo_name)
