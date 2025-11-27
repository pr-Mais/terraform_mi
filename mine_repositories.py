import collections
import concurrent.futures
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

# Try to import GitPython and dateutil.parser, which are essential
try:
    import dateutil.parser
    from git import Repo
    from git.exc import InvalidGitRepositoryError, GitCommandError, NoSuchPathError
except ImportError as e:
    print("-" * 50)
    print(f"ERROR: Missing essential library: {e.name}")
    print(
        "Please install prerequisites: pip install requests python-dateutil GitPython python-dotenv"
    )
    print("-" * 50)
    sys.exit(1)

# --- CONFIGURATION & CONSTANTS ---
load_dotenv()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# File paths
OUTPUT_DIR = "output"
REPO_LIST_FILE_C3_FILTERED = os.path.join(OUTPUT_DIR, "iac_repositories_c3_filtered.txt")
FINAL_REPO_LIST_FILE = os.path.join(OUTPUT_DIR, "iac_repositories_final_filtered.txt")
CLONE_DIRECTORY = "iac_corpus"
TARGET_FILE_EXTENSION = ".tf"

# GitHub API & Search Settings
# Following the paper's methodology: Code Search API with extension:tf
SEARCH_QUERY = "extension:tf"
GITHUB_API_URL_SEARCH = "https://api.github.com/search/code"
GITHUB_API_URL_REPOS = "https://api.github.com/repos"
MAX_WORKERS = 10  # For concurrent API calls
SEARCH_ITERATIONS = 20  # Number of times to search with different sort orders

# --- CRITERIA THRESHOLDS ---
C1_MIN_MONTHLY_COMMITS = 7.0
C2_CORE_CONTRIBUTOR_THRESHOLD = 0.80  # 80%
C3_RECENT_PUSH_DAYS = 180  # 6 months
C4_MIN_IAC_RATIO = 0.11  # 11%

# Exclusion keywords for non-research projects (templates, examples, etc.)
EXCLUSION_KEYWORDS = [
    "template",
    "boilerplate",
    "starter",
    "demo",
    "example",
    "tutorial",
    "learning",
    "test",
    "dummy",
    "poc",
    "proof-of-concept",
    "workshop",
    "docs",
    "examples",
    "template-repo",
    "iac-demo",
    "sample",
]

# =========================================================================
# PHASE 1: GITHUB MINING AND INITIAL FILTERING (C3, Templates)
# =========================================================================


def check_rate_limit(headers):
    """Checks the current GitHub API search rate limit status."""
    try:
        rate_limit_url = "https://api.github.com/rate_limit"
        response = requests.get(rate_limit_url, headers=headers, timeout=10)
        response.raise_for_status()
        search_limit = response.json()["resources"]["search"]
        remaining = search_limit["remaining"]
        reset_timestamp = search_limit["reset"]
        wait_time = max(0, reset_timestamp - int(time.time()))

        return remaining, wait_time
    except requests.exceptions.RequestException:
        return 0, 60


def get_repo_details_and_filter(repo_full_name, headers):
    """
    Fetches repository details and applies filtering following paper methodology:
    - Excludes archived repositories
    - Excludes non-starred repositories (0 stars)
    - Excludes non-licensed repositories
    - Applies non-research/template filtering
    - Applies C3 filtering (recent push within 180 days)

    Returns: The repo_full_name if valid, None otherwise.
    """

    # 1. IMMEDIATE FILTERING ON REPO NAME (Non-research)
    repo_name_lower = repo_full_name.lower()
    if any(keyword in repo_name_lower for keyword in EXCLUSION_KEYWORDS):
        return None

    repo_url = f"{GITHUB_API_URL_REPOS}/{repo_full_name}"

    try:
        response = requests.get(repo_url, headers=headers, timeout=10)
        if response.status_code == 403 and "rate limit exceeded" in response.text:
            return None

        response.raise_for_status()
        details = response.json()

        # 2. PAPER FILTERS: Archived, Non-starred, Non-licensed
        if details.get("archived", False):
            return None

        if details.get("stargazers_count", 0) == 0:
            return None

        if not details.get("license"):
            return None

        # 3. FILTERING ON DESCRIPTION/FLAGS (Non-research)
        if details.get("is_template", False):
            return None
        description = details.get("description")
        if description and any(keyword in description.lower() for keyword in EXCLUSION_KEYWORDS):
            return None

        # 4. RESEARCH CRITERIA CHECK (C3: Recent Push Event)
        pushed_at_str = details.get("pushed_at")
        if pushed_at_str:
            pushed_at = dateutil.parser.isoparse(pushed_at_str)
            time_diff = datetime.now(timezone.utc) - pushed_at
            if time_diff.days > C3_RECENT_PUSH_DAYS:
                return None
        else:
            return None

        return repo_full_name

    except requests.exceptions.RequestException:
        return None


def search_code_with_sort(headers, query, sort_by="indexed", order="desc"):
    """
    Searches GitHub code API with specific sorting.
    Returns set of unique repository names from search results.
    """
    repos = set()
    page = 1

    while page <= 10:  # GitHub's API limit
        remaining_search, wait_time = check_rate_limit(headers)

        if remaining_search < 1:
            print(f"  [WAIT] Rate limit. Waiting {wait_time + 5}s...")
            time.sleep(wait_time + 5)
            continue

        params = {
            "q": query,
            "sort": sort_by,
            "order": order,
            "per_page": 100,
            "page": page,
        }

        try:
            response = requests.get(
                GITHUB_API_URL_SEARCH, headers=headers, params=params, timeout=10
            )

            if response.status_code == 403:
                print("  [RATE LIMIT] Waiting 60s...")
                time.sleep(60)
                continue

            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])

            if page == 1:
                total = data.get("total_count", 0)
                print(f"  Sort={sort_by}, Order={order}: {total} total results available")

            if not items:
                break

            # Extract unique repository names from code search results
            for item in items:
                repo_full_name = item["repository"]["full_name"]
                repos.add(repo_full_name)

            page += 1
            time.sleep(2)  # Delay to avoid rate limits

        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] {e}")
            break

    return repos


def batch_filter_repositories(repo_names, headers, lock, found_repositories):
    """Filter a batch of repositories in parallel."""
    valid_count = 0
    for repo_name in repo_names:
        result = get_repo_details_and_filter(repo_name, headers)
        if result:
            with lock:
                if result not in found_repositories:
                    found_repositories.add(result)
                    valid_count += 1
    return valid_count


def phase_1_github_mining():
    """
    Following the paper's methodology: Search Code API with extension:tf
    using multiple sort strategies to maximize unique repository discovery.
    """
    if not GITHUB_TOKEN:
        print("[CRITICAL] GITHUB_TOKEN not found. Cannot proceed with mining.")
        return 0

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    print("--- PHASE 1: GitHub Code Mining (Following Paper Methodology) ---")
    print("Searching for .tf files using Code Search API with multiple sort strategies\n")

    all_raw_repos = set()

    # Strategy from paper: Use different sorting methods to get diverse results
    sort_strategies = [
        ("indexed", "desc"),  # Recently indexed (paper's main strategy)
        ("indexed", "asc"),  # Oldest indexed
        ("", "desc"),  # Best match/relevance
    ]

    print(
        f"Running {len(sort_strategies)} search strategies, {SEARCH_ITERATIONS} iterations each...\n"
    )

    for iteration in range(SEARCH_ITERATIONS):
        print(f"\n=== Iteration {iteration + 1}/{SEARCH_ITERATIONS} ===")

        for sort_by, order in sort_strategies:
            repos = search_code_with_sort(headers, SEARCH_QUERY, sort_by, order)
            new_repos = repos - all_raw_repos
            all_raw_repos.update(repos)

            sort_label = f"{sort_by}:{order}" if sort_by else "relevance"
            print(f"  {sort_label}: +{len(new_repos)} new repos " f"(Total: {len(all_raw_repos)})")

        # Sleep between iterations to avoid hitting rate limits
        if iteration < SEARCH_ITERATIONS - 1:
            print("  Waiting 10s before next iteration...")
            time.sleep(10)

    print(f"\n{'='*80}")
    print(f"[COLLECTED] {len(all_raw_repos)} unique repositories from code search")
    print(f"{'='*80}\n")

    if len(all_raw_repos) == 0:
        print("[WARNING] No repositories collected. Check your GitHub token.")
        return 0

    print("[FILTERING] Applying C3 and non-research filters in parallel...\n")

    # Step 2: Filter repos in parallel batches
    found_repositories = set()
    repo_list = list(all_raw_repos)
    batch_size = 50
    lock = threading.Lock()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for i in range(0, len(repo_list), batch_size):
            batch = repo_list[i : i + batch_size]
            futures.append(
                executor.submit(batch_filter_repositories, batch, headers, lock, found_repositories)
            )

        completed = 0
        for _ in concurrent.futures.as_completed(futures):
            completed += 1
            progress = (completed / len(futures)) * 100
            print(f"[FILTERING] {progress:.1f}% | Valid: {len(found_repositories)}", end="\r")

    print(f"\n\n{'='*80}")
    print(f"[SUMMARY] {len(found_repositories)} repositories after filtering")
    print(f"{'='*80}\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(REPO_LIST_FILE_C3_FILTERED, "w", encoding="utf-8") as f:
        for repo in sorted(list(found_repositories)):
            f.write(repo + "\n")

    print(f"Repository list saved to {REPO_LIST_FILE_C3_FILTERED}")
    return len(found_repositories)


# =========================================================================
# PHASE 2: CLONING REPOSITORIES
# =========================================================================


def phase_2_clone_repos():
    """Reads the C3-filtered list and clones them locally."""
    print("\n--- PHASE 2: Cloning Repositories ---")

    if not os.path.exists(CLONE_DIRECTORY):
        os.makedirs(CLONE_DIRECTORY)

    try:
        with open(REPO_LIST_FILE_C3_FILTERED, "r", encoding="utf-8") as f:
            repositories = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[ERROR] Cannot find list file '{REPO_LIST_FILE_C3_FILTERED}'. Run Phase 1 first.")
        return 0

    print(f"Starting to clone {len(repositories)} repositories...")

    successful_clones = 0
    skipped_clones = 0
    failed_clones = 0

    for repo_full_name in repositories:
        repo_dir_name = repo_full_name.replace("/", "_")
        clone_url = f"https://github.com/{repo_full_name}.git"
        target_path = os.path.join(CLONE_DIRECTORY, repo_dir_name)

        if os.path.exists(target_path):
            print(f"[SKIP] Already cloned: {repo_full_name}")
            successful_clones += 1
            skipped_clones += 1
            continue

        print(f"[CLONE] Cloning: {repo_full_name}")
        try:
            subprocess.run(
                ["git", "clone", clone_url, target_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=300,
            )
            successful_clones += 1
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print(f"[FAIL] Failed to clone: {repo_full_name}")
            failed_clones += 1

        time.sleep(0.5)

    print(
        f"\nCloning complete. Total: {len(repositories)} | "
        f"Successful: {successful_clones} | "
        f"Skipped (already cloned): {skipped_clones} | "
        f"Failed: {failed_clones}"
    )
    return successful_clones


# =========================================================================
# PHASE 3: DEEP ANALYSIS AND REPORTING (C4, C1, C2)
# =========================================================================


def analyze_repository(repo_path):
    """Analyzes a single repository against C4, C1, and C2 criteria."""
    results = {
        "C1_Pass": False,
        "C2_Pass": False,
        "C4_Pass": False,
        "C4_Fail": False,
        "C1_Fail": False,
        "C2_Fail": False,
    }

    # --- C4: Ratio of IaC scripts ---
    total_files = 0
    iac_files = 0
    for _, _, files in os.walk(repo_path):
        for file in files:
            total_files += 1
            if file.endswith(TARGET_FILE_EXTENSION):
                iac_files += 1

    iac_ratio = iac_files / total_files if total_files else 0
    if iac_ratio < C4_MIN_IAC_RATIO:
        results["C4_Fail"] = True
        return results
    results["C4_Pass"] = True

    # --- Start Git History Analysis (C1, C2) ---
    try:
        repo = Repo(repo_path)
    except (InvalidGitRepositoryError, GitCommandError, NoSuchPathError):
        return results  # Fails implicit internal checks

    all_commits = list(repo.iter_commits())
    if len(all_commits) < 2:
        return results  # Fails implicit internal checks

    try:
        first_commit_date = all_commits[-1].committed_datetime.replace(tzinfo=timezone.utc)
        last_commit_date = all_commits[0].committed_datetime.replace(tzinfo=timezone.utc)
    except AttributeError:
        return results

    time_span_months = (last_commit_date - first_commit_date).days / 30.44

    # --- C1: Commit frequency ---
    total_commits = len(all_commits)
    avg_monthly_commits = total_commits / time_span_months if time_span_months > 0 else 0

    if avg_monthly_commits < C1_MIN_MONTHLY_COMMITS:
        results["C1_Fail"] = True
        return results
    results["C1_Pass"] = True

    # --- C2: Core Contributors ---
    contributor_commits = collections.Counter(c.author.email for c in all_commits)
    total_contributor_commits = sum(contributor_commits.values())

    if len(contributor_commits) < 2:
        results["C2_Fail"] = True
        return results

    sorted_contributors = contributor_commits.most_common()
    if total_contributor_commits == 0:
        results["C2_Fail"] = True
        return results

    top_two_commits = sorted_contributors[0][1] + sorted_contributors[1][1]
    top_two_ratio = top_two_commits / total_contributor_commits

    if top_two_ratio < C2_CORE_CONTRIBUTOR_THRESHOLD:
        results["C2_Fail"] = True
        return results
    results["C2_Pass"] = True

    return results


def phase_3_deep_analysis():
    """Performs deep analysis and generates the final exclusion report."""
    print("\n--- PHASE 3: Deep Analysis and Final Filtering (C4, C1, C2) ---")

    try:
        with open(REPO_LIST_FILE_C3_FILTERED, "r", encoding="utf-8") as f:
            initial_repositories = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[ERROR] Cannot find list file '{REPO_LIST_FILE_C3_FILTERED}'. Run Phase 1 first.")
        return

    initial_count = len(initial_repositories)

    # List to hold repos passing all three criteria
    valid_repos = []

    # Track passes at each sequential stage
    repos_after_c4 = []
    repos_after_c1 = []

    print(f"Analyzing {initial_count} projects for C4, C1, C2 maturity criteria...")

    for repo_full_name in initial_repositories:
        repo_dir_name = repo_full_name.replace("/", "_")
        repo_path = os.path.join(CLONE_DIRECTORY, repo_dir_name)

        # Skip if cloning failed in Phase 2
        if not os.path.isdir(repo_path):
            continue

        results = analyze_repository(repo_path)

        # Sequential check for reporting purposes
        if results["C4_Pass"]:
            repos_after_c4.append(repo_full_name)
            if results["C1_Pass"]:
                repos_after_c1.append(repo_full_name)
                if results["C2_Pass"]:
                    valid_repos.append(repo_full_name)

    # --- Calculation of Exclusions ---

    # Note: Initial list (initial_count) implicitly passed C3 and non-research filters.

    # 1. Projects Excluded by C4 (Must have passed C3)
    c4_pass_count = len(repos_after_c4)
    excluded_by_c4 = initial_count - c4_pass_count

    # 2. Projects Excluded by C1 (Must have passed C4)
    c1_pass_count = len(repos_after_c1)
    excluded_by_c1 = c4_pass_count - c1_pass_count

    # 3. Projects Excluded by C2 (Must have passed C1)
    c2_pass_count = len(valid_repos)
    excluded_by_c2 = c1_pass_count - c2_pass_count

    # --- FINAL FILE & REPORT ---
    with open(FINAL_REPO_LIST_FILE, "w", encoding="utf-8") as f:
        for repo in sorted(valid_repos):
            f.write(repo + "\n")

    print("\n\n" + "=" * 80)
    print("                 FINAL DATA CURATION REPORT FOR IaC STUDY")
    print("=" * 80)

    print(f"Date of Analysis: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Initial Candidate Repositories (Passing C3 & Initial Filters): {initial_count}")
    print(f"Final projects selected: {c2_pass_count}")

    print("\n## I. Project Filtering Results (C4, C1, C2)")
    print(
        "The table below details the number of projects excluded at each sequential maturity step:"
    )

    print("\n| Criterion | Description | Threshold | Projects Remaining | Excluded by Criterion |")
    print("| :--- | :--- | :--- | :--- | :--- |")
    print(f"| C4 | IaC scripts ratio | $\\geq$ 11.0% | {c4_pass_count} | {excluded_by_c4} |")
    print(f"| C1 | Average monthly commits | $\\geq$ 7.0 | {c1_pass_count} | {excluded_by_c1} |")
    print(
        f"| C2 | Core contributors commit ratio | $\\geq$ 80.0% | {c2_pass_count} | {excluded_by_c2} |"
    )

    print("\n## II. Summary of Next Steps")
    print("The final list of selected projects is saved to: **{FINAL_REPO_LIST_FILE}**")

    print("\nThese projects now require two PENDING post-analysis steps:")

    print(
        "1. **Metric Extraction:** Run a tool (like TerraMetrics) on the cloned projects to generate the fine-grained metrics for every IaC block."
    )
    print(
        "2. **Defect Labeling:** Analyze the Git history to label blocks as defective, and then apply the final filters:"
    )
    print("| Criterion | Description | Status |")
    print("| :--- | :--- | :--- |")
    print(
        "| C5 | Sufficient number of changed blocks ($\\geq$ 300 modified blocks) | **PENDING** |"
    )
    print("| C6 | Ratio of defects in changed blocks ($\\geq$ 5.0%) | **PENDING** |")
    print(
        "| C7 | Number of defective blocks in the last six months ($\\geq$ 3 defective blocks) | **PENDING** |"
    )
    print("=" * 80)


# =========================================================================
# PIPELINE EXECUTION
# =========================================================================


def test_single_repo(repo_url: str):
    """
    Test the pipeline on a single repository without requiring GitHub token.
    Useful for dry-run testing.

    Args:
        repo_url: GitHub repository URL (e.g., 'https://github.com/owner/repo')
    """
    import re

    # Extract owner/repo from URL
    match = re.search(r"github\.com/([^/]+/[^/]+)", repo_url)
    if not match:
        print(f"[ERROR] Invalid GitHub URL: {repo_url}")
        return

    repo_full_name = match.group(1).rstrip("/").rstrip(".git")
    print(f"Testing single repository: {repo_full_name}")
    print("=" * 80)

    # Clone the repository
    repo_dir_name = repo_full_name.replace("/", "_")
    repo_path = os.path.join(CLONE_DIRECTORY, repo_dir_name)

    if not os.path.isdir(repo_path):
        print(f"Cloning {repo_full_name}...")
        os.makedirs(CLONE_DIRECTORY, exist_ok=True)
        clone_cmd = ["git", "clone", f"https://github.com/{repo_full_name}.git", repo_path]
        result = subprocess.run(clone_cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            print(f"[ERROR] Failed to clone repository: {result.stderr}")
            return

    # Analyze the repository
    print("\nAnalyzing repository against C4, C1, C2 criteria...")
    results = analyze_repository(repo_path)

    # Print results
    print("\n" + "=" * 80)
    print("TEST RESULTS")
    print("=" * 80)
    print(f"Repository: {repo_full_name}")
    print(f"Path: {repo_path}")
    print("\nCriteria Results:")
    print(f"  C4 (IaC Ratio):      {'✓ PASS' if results['C4_Pass'] else '✗ FAIL'}")
    print(f"  C1 (Bug Fixing):     {'✓ PASS' if results['C1_Pass'] else '✗ FAIL'}")
    print(f"  C2 (Active Recent):  {'✓ PASS' if results['C2_Pass'] else '✗ FAIL'}")
    print("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="IaC Data Curation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline (requires GITHUB_TOKEN)
  python iac_pipeline.py

  # Test on a single repository (dry-run, no token needed)
  python iac_pipeline.py --test https://github.com/owner/repo
        """,
    )
    parser.add_argument(
        "--test",
        metavar="REPO_URL",
        help="Test pipeline on a single repository (e.g., https://github.com/owner/repo)",
    )

    args = parser.parse_args()

    # Test mode - single repository
    if args.test:
        test_single_repo(args.test)
        sys.exit(0)

    # Full pipeline mode
    if not GITHUB_TOKEN:
        print("[CRITICAL] GITHUB_TOKEN not set. Please check your .env file.")
        sys.exit(1)

    print("Starting IaC Data Curation Pipeline...")

    # 1. GitHub Mining and Initial Filtering (C3)
    if phase_1_github_mining() == 0:
        print("[PIPELINE HALTED] No repositories found or rate limit hit during Phase 1.")
    else:
        # 2. Cloning Repositories
        if phase_2_clone_repos() == 0:
            print("[PIPELINE HALTED] Cloning failed or no files to clone.")
        else:
            # 3. Deep Analysis and Reporting (C4, C1, C2)
            phase_3_deep_analysis()

    print("\nPipeline finished.")
