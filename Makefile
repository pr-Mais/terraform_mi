.PHONY: format lint check test clean help

help:
	@echo "Available commands:"
	@echo "  make format  - Format code with Black"
	@echo "  make lint    - Check code with flake8"
	@echo "  make check   - Run both format and lint"
	@echo "  make test    - Test the script on sample repo"
	@echo "  make clean   - Remove output and cache files"

format:
	@echo "Formatting code with Black..."
	@black build_dataset.py mine_repositories.py main.py --line-length 100

lint:
	@echo "Linting code with flake8..."
	@flake8 build_dataset.py mine_repositories.py main.py --max-line-length=100 --ignore=E501,W503,W504,E203

check: format lint
	@echo "✓ Code is formatted and linted"

test:
	@echo "Testing script on sample repository..."
	@python build_dataset.py --mode single --input iac_corpus/00arpit00_terraform \
		--output output/test.csv --skip-github

clean:
	@echo "Cleaning output and cache files..."
	@rm -rf output/*.csv
	@rm -rf output/terrametric_temp/*
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "✓ Cleanup complete"
