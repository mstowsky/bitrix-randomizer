# Use PowerShell on Windows
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Python executable from virtual environment
python := if os() == "windows" {
    ".\\.venv\\Scripts\\python.exe"
} else {
    "./.venv/bin/python"
}

# Start application
start:
    {{python}} -m uvicorn app.main:app --reload

# Run all tests
test:
    {{python}} -m pytest

# Check code and formatting
check:
    {{python}} -m ruff check .
    {{python}} -m ruff format --check .

# Fix lint errors and format code
check-fix:
    {{python}} -m ruff check . --fix
    {{python}} -m ruff format .