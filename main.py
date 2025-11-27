#!/usr/bin/env python3
"""
Terraform Code Quality Analysis CLI
Simple interface for mining repositories and building quality datasets
"""

import sys
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box
import questionary

console = Console()


def show_header():
    """Show CLI header"""
    console.print(
        Panel.fit(
            "[bold cyan]Terraform Code Quality Analysis[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )


def show_menu():
    """Show interactive menu and return choice"""
    choices = [
        questionary.Choice("🔍 Mine Terraform repositories from GitHub", value="mine"),
        questionary.Choice("🧪 Test mining on a single repository", value="test"),
        questionary.Choice("📊 Analyze repositories and build dataset", value="analyze"),
        questionary.Choice("⚡ Quick analysis of a local repository", value="quick"),
        questionary.Choice("📈 Show project status", value="status"),
        questionary.Choice("🧹 Clean output files", value="clean"),
        questionary.Separator(),
        questionary.Choice("👋 Exit", value="exit"),
    ]

    return questionary.select(
        "Select a command:",
        choices=choices,
        style=questionary.Style(
            [
                ("qmark", "fg:cyan bold"),
                ("question", "bold"),
                ("pointer", "fg:cyan bold"),
                ("highlighted", "fg:cyan bold"),
                ("selected", "fg:green"),
            ]
        ),
    ).ask()


def check_setup():
    """Check if environment is properly set up"""
    issues = []

    if not Path(".env").exists():
        issues.append("Missing .env file (run: echo 'GITHUB_TOKEN=your_token' > .env)")

    if not Path("venv").exists():
        issues.append("Missing virtual environment (run: python3 -m venv venv)")

    return issues


def run_command(cmd, description):
    """Run a shell command and show output"""
    console.rule(f"[bold]{description}[/bold]", style="blue")
    result = subprocess.run(cmd, shell=True, check=False)
    console.rule(style="blue")
    return result.returncode == 0


def mine_repositories():
    """Mine repositories from GitHub"""
    console.clear()
    show_header()

    console.print("\n[bold]Mining Terraform repositories from GitHub[/bold]\n")

    steps = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    steps.add_column(style="dim")
    steps.add_row("1. Search GitHub for Terraform repositories")
    steps.add_row("2. Filter by quality criteria (C3)")
    steps.add_row("3. Clone repositories")
    steps.add_row("4. Apply deep analysis (C4, C1, C2)")

    console.print(steps)
    console.print("\n[yellow]Note: Requires GITHUB_TOKEN in .env file[/yellow]\n")

    if not Confirm.ask("Continue?", default=False):
        return

    run_command("python mine_repositories.py", "Running repository mining pipeline")


def test_single_repo():
    """Test mining on a single repository"""
    console.clear()
    show_header()

    console.print("\n[bold]Test Mining on Single Repository[/bold]\n")
    repo_url = Prompt.ask("Enter GitHub repository URL").strip()

    if not repo_url:
        console.print("[red]Error: URL cannot be empty[/red]")
        return

    run_command(
        f'python mine_repositories.py --test "{repo_url}"',
        f"Testing repository: {repo_url}",
    )


def analyze_repositories():
    """Analyze repositories and build dataset"""
    console.clear()
    show_header()

    console.print("\n[bold]Build Quality Metrics Dataset[/bold]\n")

    repo_list = Path("output/iac_repositories_final_filtered.txt")
    if not repo_list.exists():
        console.print(f"[red]Error: Repository list not found at {repo_list}[/red]")
        console.print("[yellow]Run 'mine' command first to generate repository list[/yellow]")
        return

    with open(repo_list, encoding="utf-8") as f:
        repo_count = len([line for line in f if line.strip()])

    console.print(f"[green]Found {repo_count} repositories to analyze[/green]\n")

    steps = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    steps.add_column(style="dim")
    steps.add_row("1. Extract Terraform code blocks")
    steps.add_row("2. Run TerraMetric analysis")
    steps.add_row("3. Calculate Maintainability Index")
    steps.add_row("4. Collect GitHub metadata")
    steps.add_row("5. Generate CSV dataset")

    console.print(steps)
    console.print()

    if not Confirm.ask("Continue?", default=False):
        return

    output_file = Prompt.ask("Output CSV file", default="output/iac_dataset.csv").strip()

    run_command(
        f'python build_dataset.py --mode list --input "{repo_list}" --output "{output_file}"',
        "Building dataset",
    )

    if Path(output_file).exists():
        console.print(f"\n[green]✓ Dataset saved to: {output_file}[/green]")


def quick_analysis():
    """Quick analysis of a local repository"""
    console.clear()
    show_header()

    console.print("\n[bold]Quick Repository Analysis[/bold]\n")

    repo_path = questionary.path(
        "Enter local repository path:",
        only_directories=True,
        style=questionary.Style(
            [
                ("qmark", "fg:cyan bold"),
                ("question", "bold"),
                ("pointer", "fg:cyan bold"),
                ("text", ""),
            ]
        ),
    ).ask()

    if not repo_path:
        console.print("[yellow]Cancelled[/yellow]")
        return

    # Expand ~ and resolve to absolute path
    repo_path = Path(repo_path).expanduser().resolve()

    if not repo_path.exists():
        console.print(f"[red]Error: Path does not exist: {repo_path}[/red]")
        return

    if not repo_path.is_dir():
        console.print(f"[red]Error: Path is not a directory: {repo_path}[/red]")
        return

    repo_name = repo_path.name
    output_file = f"output/{repo_name}_analysis.csv"

    run_command(
        f'python build_dataset.py --mode single --input "{repo_path}" '
        f'--output "{output_file}" --skip-github',
        f"Analyzing {repo_name}",
    )

    if Path(output_file).exists():
        console.print(f"\n[green]✓ Analysis saved to: {output_file}[/green]")


def show_status():
    """Show project status"""
    console.clear()
    show_header()

    console.print("\n[bold]Project Status[/bold]\n")

    # Check setup
    issues = check_setup()
    if issues:
        console.print("[yellow]Setup Issues:[/yellow]")
        for issue in issues:
            console.print(f"  [red]⚠[/red] {issue}")
        console.print()
    else:
        console.print("[green]✓ Environment configured[/green]\n")

    # Check output files
    output_dir = Path("output")
    if output_dir.exists():
        files_table = Table(title="Output Files", box=box.ROUNDED)
        files_table.add_column("File", style="cyan")
        files_table.add_column("Size", justify="right", style="magenta")

        for file in sorted(output_dir.glob("*")):
            if file.is_file():
                size = file.stat().st_size
                size_str = f"{size:,} B" if size < 1024 else f"{size/1024:.1f} KB"
                files_table.add_row(file.name, size_str)

        console.print(files_table)
        console.print()
    else:
        console.print("[dim]No output files yet[/dim]\n")

    # Check cloned repositories
    corpus_dir = Path("iac_corpus")
    if corpus_dir.exists():
        repo_count = len([d for d in corpus_dir.iterdir() if d.is_dir()])
        console.print(f"[cyan]Cloned Repositories:[/cyan] {repo_count}")
    else:
        console.print("[dim]No cloned repositories yet[/dim]")


def clean_outputs():
    """Clean output files"""
    console.clear()
    show_header()

    console.print("\n[bold]Clean Output Files[/bold]\n")

    items = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    items.add_column(style="dim")
    items.add_row("CSV files in output/")
    items.add_row("Temporary analysis files")
    items.add_row("Python cache files")

    console.print("[yellow]This will remove:[/yellow]")
    console.print(items)
    console.print()

    if not Confirm.ask("Continue?", default=False):
        return

    run_command("make clean", "Cleaning output files")


def main():
    """Main CLI loop"""
    while True:
        console.clear()
        show_header()
        console.print()

        choice = show_menu()

        if not choice or choice == "exit":
            console.print("\n[cyan]Goodbye![/cyan]\n")
            sys.exit(0)

        console.print()

        if choice == "mine":
            mine_repositories()
        elif choice == "test":
            test_single_repo()
        elif choice == "analyze":
            analyze_repositories()
        elif choice == "quick":
            quick_analysis()
        elif choice == "status":
            show_status()
        elif choice == "clean":
            clean_outputs()

        console.print()
        Prompt.ask("Press Enter to continue")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user. Goodbye![/yellow]\n")
        sys.exit(0)
