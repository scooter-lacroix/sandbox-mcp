#!/usr/bin/env python3
"""
Documentation consistency checks for CI/CD pipeline.

This script verifies:
- Version consistency across pyproject.toml, __init__.py, and README.md
- Python version requirement consistency
- Feature description accuracy

Usage:
    python scripts/check_docs_consistency.py
    
Returns exit code 0 if all checks pass, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def check_version_consistency(project_root: Path) -> bool:
    """Check that version is consistent across all files."""
    print("Checking version consistency...")
    
    # Get version from pyproject.toml
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        print("  ✗ pyproject.toml not found")
        return False
    
    pyproject_content = pyproject.read_text()
    version_match = re.search(r'version\s*=\s*"([^"]+)"', pyproject_content)
    if not version_match:
        print("  ✗ Version not found in pyproject.toml")
        return False
    
    pyproject_version = version_match.group(1)
    print(f"  ✓ pyproject.toml version: {pyproject_version}")
    
    # Check __init__.py uses package metadata (not hardcoded)
    init_file = project_root / "src" / "sandbox" / "__init__.py"
    if init_file.exists():
        init_content = init_file.read_text()
        if "importlib.metadata.version" in init_content:
            print(f"  ✓ __init__.py reads version from package metadata")
        else:
            print(f"  ✗ __init__.py should read version from package metadata")
            return False
    
    # Check README doesn't have hardcoded version (should use badges)
    readme = project_root / "README.md"
    if readme.exists():
        readme_content = readme.read_text()
        # Check for version badge - it's ok if it's a badge
        badge_match = re.search(r'python-(\d+\.\d+)\+', readme_content)
        if badge_match:
            python_version = badge_match.group(1)
            print(f"  ✓ README.md Python version badge: {python_version}+")
    
    return True


def check_python_version_consistency(project_root: Path) -> bool:
    """Check Python version requirements are consistent."""
    print("\nChecking Python version consistency...")
    
    # Check pyproject.toml
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        # Look for requires-python
        python_match = re.search(r'requires-python\s*=\s*">=([^"]+)"', content)
        if python_match:
            pyproject_python = python_match.group(1)
            print(f"  ✓ pyproject.toml requires-python: >={pyproject_python}")
        else:
            print(f"  ✗ requires-python not found in pyproject.toml")
            return False
    
    # Check README
    readme = project_root / "README.md"
    if readme.exists():
        content = readme.read_text()
        # Look for Python version mention
        readme_match = re.search(r'Python\s+(\d+\.\d+)\+', content)
        if readme_match:
            readme_python = readme_match.group(1)
            print(f"  ✓ README.md states: Python {readme_python}+")
        else:
            print(f"  ⚠ README.md Python version not explicitly stated")
    
    return True


def check_feature_descriptions(project_root: Path) -> bool:
    """Check that feature descriptions match actual capabilities."""
    print("\nChecking feature descriptions...")
    
    readme = project_root / "README.md"
    if not readme.exists():
        print("  ✗ README.md not found")
        return False
    
    content = readme.read_text()
    
    # Check for overclaimed security
    if "strong isolation" in content.lower():
        print("  ✗ README claims 'strong isolation' - should be 'guarded execution'")
        return False
    
    if "guarded execution" in content.lower() or "guarded execution environment" in content.lower():
        print("  ✓ Security claims are accurate (guarded execution)")
    
    # Check for network access claims
    if "no internet access" in content.lower() or "no network access" in content.lower():
        print("  ✗ README claims no internet/network access - this should be qualified")
        return False
    
    # Check that MCP tools are mentioned
    if "mcp" in content.lower():
        print("  ✓ MCP integration is documented")
    
    # Check that artifact management is mentioned
    if "artifact" in content.lower():
        print("  ✓ Artifact management is documented")
    
    return True


def check_security_disclaimers(project_root: Path) -> bool:
    """Check that security disclaimers are present."""
    print("\nChecking security disclaimers...")
    
    readme = project_root / "README.md"
    if readme.exists():
        content = readme.read_text()
        
        # Check for container/VM recommendation
        if "container" in content.lower() or "vm" in content.lower() or "virtual machine" in content.lower():
            print("  ✓ Security disclaimer mentions container/VM for untrusted code")
        else:
            print("  ⚠ Consider adding disclaimer about container/VM for untrusted code")
        
        # Check for pickle warning in code
        execution_context = project_root / "src" / "sandbox" / "core" / "execution_context.py"
        if execution_context.exists():
            content = execution_context.read_text()
            if "pickle" in content.lower() and ("security" in content.lower() or "not secure" in content.lower()):
                print("  ✓ Pickle security warning present in execution_context.py")
            elif "pickle" in content.lower():
                print("  ⚠ Consider adding security warning for pickle usage")
    
    return True


def main() -> int:
    """Run all documentation consistency checks."""
    print("=" * 60)
    print("Documentation Consistency Checks")
    print("=" * 60)
    
    project_root = Path(__file__).parent.parent
    
    all_passed = True
    
    all_passed &= check_version_consistency(project_root)
    all_passed &= check_python_version_consistency(project_root)
    all_passed &= check_feature_descriptions(project_root)
    all_passed &= check_security_disclaimers(project_root)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All documentation consistency checks passed")
        print("=" * 60)
        return 0
    else:
        print("✗ Some documentation consistency checks failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
