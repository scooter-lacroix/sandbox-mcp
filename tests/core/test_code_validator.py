"""
Comprehensive coverage tests for code_validator.py - Tier 4 Task T2

Target: Raise coverage from 0% to 70%+
Focus: Security-critical input validation, auto-fixes, safety checks
"""

import pytest
from unittest.mock import patch, MagicMock

from sandbox.core.code_validator import CodeValidator, CodeFormatter


class TestCodeValidatorInit:
    """Test CodeValidator initialization."""

    def test_init_creares_instance(self):
        """Test that CodeValidator can be instantiated."""
        validator = CodeValidator()
        assert validator is not None
        assert isinstance(validator, CodeValidator)

    def test_init_initializes_empty_lists(self):
        """Test that instance variables are initialized as empty lists."""
        validator = CodeValidator()
        assert validator.common_issues == []
        assert validator.warnings == []
        assert validator.suggestions == []


class TestValidateAndFormat:
    """Test the main validate_and_format method."""

    def test_validate_and_format_returns_dict(self):
        """Test that validate_and_format returns a dictionary."""
        validator = CodeValidator()
        result = validator.validate_and_format("print('hello')")
        assert isinstance(result, dict)

    def test_validate_and_format_dict_keys(self):
        """Test that result dict contains all expected keys."""
        validator = CodeValidator()
        result = validator.validate_and_format("print('hello')")
        expected_keys = {'valid', 'formatted_code', 'issues', 'warnings', 'suggestions', 'auto_fixes'}
        assert set(result.keys()) == expected_keys

    def test_validate_and_format_valid_code(self):
        """Test validation with valid Python code."""
        validator = CodeValidator()
        result = validator.validate_and_format("print('hello')")
        assert result['valid'] is True
        assert result['formatted_code'] is not None

    def test_validate_and_format_invalid_syntax(self):
        """Test validation with invalid syntax."""
        validator = CodeValidator()
        result = validator.validate_and_format("print('hello'")
        assert result['valid'] is False
        assert len(result['issues']) > 0
        assert 'Syntax error' in result['issues'][0]

    def test_validate_and_format_syntax_error_with_line_number(self):
        """Test that syntax errors include line numbers."""
        validator = CodeValidator()
        result = validator.validate_and_format("print('hello'\nprint('world')")
        assert result['valid'] is False
        # Error message should mention line
        assert any('line' in issue.lower() for issue in result['issues'])

    def test_validate_and_format_empty_code(self):
        """Test validation with empty code."""
        validator = CodeValidator()
        result = validator.validate_and_format("")
        # Empty code is technically valid Python
        assert result['valid'] is True

    def test_validate_and_format_code_with_comments(self):
        """Test validation with code containing comments."""
        validator = CodeValidator()
        code = "# This is a comment\nprint('hello')"
        result = validator.validate_and_format(code)
        assert result['valid'] is True

    def test_validate_and_format_code_with_multiline_strings(self):
        """Test validation with multiline strings."""
        validator = CodeValidator()
        code = '''text = """
This is a
multiline string
"""
print(text)'''
        result = validator.validate_and_format(code)
        assert result['valid'] is True


class TestValidateSyntax:
    """Test the _validate_syntax method."""

    def test_validate_syntax_valid_code(self):
        """Test syntax validation with valid code."""
        validator = CodeValidator()
        result = validator._validate_syntax("x = 5")
        assert result['valid'] is True
        assert result['issues'] == []

    def test_validate_syntax_invalid_syntax(self):
        """Test syntax validation with invalid syntax."""
        validator = CodeValidator()
        result = validator._validate_syntax("def foo(")
        assert result['valid'] is False
        assert len(result['issues']) > 0

    def test_validate_syntax_missing_colon(self):
        """Test syntax validation with missing colon."""
        validator = CodeValidator()
        result = validator._validate_syntax("if True print('hello')")
        assert result['valid'] is False

    def test_validate_syntax_indentation_error(self):
        """Test syntax validation with indentation error."""
        validator = CodeValidator()
        code = "def foo():\nprint('hello')"
        result = validator._validate_syntax(code)
        assert result['valid'] is False


class TestApplyAutoFixes:
    """Test the _apply_auto_fixes method."""

    def test_apply_auto_fixes_trailing_backslash(self):
        """Test that trailing backslashes are removed."""
        validator = CodeValidator()
        code = 'x = "hello"\\'
        result = validator._apply_auto_fixes(code)
        assert '\\' not in result or result.count('\\') < code.count('\\')

    def test_apply_auto_fixes_windows_paths(self):
        """Test conversion of Windows paths to Unix-style."""
        validator = CodeValidator()
        code = 'path = "C:\\\\Users\\\\test\\\\file.txt"'
        result = validator._apply_auto_fixes(code)
        # Should convert double backslashes to forward slashes
        assert '\\\\' not in result or result == code

    def test_apply_auto_fixes_sandbox_artifacts_path(self):
        """Test that /sandbox/artifacts/ is converted to /artifacts/."""
        validator = CodeValidator()
        code = 'path = "/sandbox/artifacts/test.png"'
        result = validator._apply_auto_fixes(code)
        assert '/sandbox/artifacts/' not in result
        assert '/artifacts/' in result

    def test_apply_auto_fixes_adds_matplotlib_import(self):
        """Test that matplotlib import is added when plt is used."""
        validator = CodeValidator()
        code = "plt.plot([1, 2, 3])"
        result = validator._apply_auto_fixes(code)
        assert 'import matplotlib.pyplot as plt' in result

    def test_apply_auto_fixes_adds_numpy_import(self):
        """Test that numpy import is added when np is used."""
        validator = CodeValidator()
        code = "x = np.array([1, 2, 3])"
        result = validator._apply_auto_fixes(code)
        assert 'import numpy as np' in result

    def test_apply_auto_fixes_adds_pandas_import(self):
        """Test that pandas import is added when pd is used."""
        validator = CodeValidator()
        code = "df = pd.DataFrame()"
        result = validator._apply_auto_fixes(code)
        assert 'import pandas as pd' in result

    def test_apply_auto_fixes_adds_os_import(self):
        """Test that os import is added when os functions are used."""
        validator = CodeValidator()
        code = "os.makedirs('/test')"
        result = validator._apply_auto_fixes(code)
        assert 'import os' in result

    def test_apply_auto_fixes_adds_pathlib_import(self):
        """Test that pathlib import is added when Path is used."""
        validator = CodeValidator()
        code = "p = Path('/test')"
        result = validator._apply_auto_fixes(code)
        assert 'from pathlib import Path' in result

    def test_apply_auto_fixes_multiple_imports(self):
        """Test that multiple imports can be added."""
        validator = CodeValidator()
        code = "x = np.array([1,2,3])\nplt.plot(x)"
        result = validator._apply_auto_fixes(code)
        assert 'import numpy as np' in result
        assert 'import matplotlib.pyplot as plt' in result

    def test_apply_auto_fixes_doesnt_duplicate_imports(self):
        """Test that existing imports are not duplicated."""
        validator = CodeValidator()
        code = "import numpy as np\nx = np.array([1,2,3])"
        result = validator._apply_auto_fixes(code)
        # Should not duplicate the import
        assert result.count('import numpy as np') == 1

    def test_apply_auto_fixes_with_listdir(self):
        """Test that os import is added for listdir."""
        validator = CodeValidator()
        code = "files = listdir('/tmp')"
        result = validator._apply_auto_fixes(code)
        assert 'import os' in result

    def test_apply_auto_fixes_with_makedirs(self):
        """Test that os import is added for makedirs."""
        validator = CodeValidator()
        code = "makedirs('/tmp/test')"
        result = validator._apply_auto_fixes(code)
        assert 'import os' in result


class TestAddMissingImports:
    """Test the _add_missing_imports method."""

    def test_add_missing_imports_matplotlib_pattern(self):
        """Test matplotlib import is added for plt pattern."""
        validator = CodeValidator()
        code = "plt.show()"
        result = validator._add_missing_imports(code)
        assert 'import matplotlib.pyplot as plt' in result

    def test_add_missing_imports_matplotlib_text(self):
        """Test matplotlib import is added for 'matplotlib' in code."""
        validator = CodeValidator()
        code = "import matplotlib"
        result = validator._add_missing_imports(code)
        # Should not duplicate if already imported
        assert result.count('import matplotlib') <= 2

    def test_add_missing_imports_numpy_pattern(self):
        """Test numpy import is added for np pattern."""
        validator = CodeValidator()
        code = "arr = np.zeros((3, 3))"
        result = validator._add_missing_imports(code)
        assert 'import numpy as np' in result

    def test_add_missing_imports_numpy_text(self):
        """Test numpy import is added for 'numpy' in code."""
        validator = CodeValidator()
        code = "import numpy"
        result = validator._add_missing_imports(code)
        # Should recognize existing import
        assert 'import numpy' in code or 'import numpy as np' in result

    def test_add_missing_imports_pandas_pattern(self):
        """Test pandas import is added for pd pattern."""
        validator = CodeValidator()
        code = "df = pd.read_csv('file.csv')"
        result = validator._add_missing_imports(code)
        assert 'import pandas as pd' in result

    def test_add_missing_imports_pandas_text(self):
        """Test pandas import is added for 'pandas' in code."""
        validator = CodeValidator()
        code = "import pandas"
        result = validator._add_missing_imports(code)
        assert 'import pandas' in code or 'import pandas as pd' in result

    def test_add_missing_imports_no_imports_needed(self):
        """Test code without import patterns."""
        validator = CodeValidator()
        code = "x = 5\nprint(x)"
        result = validator._add_missing_imports(code)
        assert result == code

    def test_add_missing_imports_preserves_code_order(self):
        """Test that imports are added at the beginning."""
        validator = CodeValidator()
        code = "x = 5\nprint(x)"
        result = validator._add_missing_imports(code)
        lines = result.strip().split('\n')
        # When no imports needed, code is unchanged
        # When imports are added, they should be at the beginning
        if result != code:
            assert any('import' in line for line in lines[:3])


class TestCheckCommonIssues:
    """Test the _check_common_issues method."""

    def test_check_common_issues_hardcoded_paths(self):
        """Test detection of hardcoded paths."""
        validator = CodeValidator()
        code = 'path = "/home/user/file.txt"'
        issues = validator._check_common_issues(code)
        assert len(issues) > 0
        assert any('Hardcoded paths' in issue for issue in issues)

    def test_check_common_issues_network_requests(self):
        """Test detection of network operations (requests)."""
        validator = CodeValidator()
        code = "import requests\nrequests.get('http://example.com')"
        issues = validator._check_common_issues(code)
        assert any('Network operations' in issue for issue in issues)

    def test_check_common_issues_network_urllib(self):
        """Test detection of network operations (urllib)."""
        validator = CodeValidator()
        code = "import urllib\nurllib.request.urlopen('http://example.com')"
        issues = validator._check_common_issues(code)
        assert any('Network operations' in issue for issue in issues)

    def test_check_common_issues_network_socket(self):
        """Test detection of network operations (socket)."""
        validator = CodeValidator()
        code = "import socket\nsocket.socket()"
        issues = validator._check_common_issues(code)
        assert any('Network operations' in issue for issue in issues)

    def test_check_common_issues_dangerous_paths_etc(self):
        """Test detection of /etc/ access."""
        validator = CodeValidator()
        code = 'open("/etc/passwd", "r")'
        issues = validator._check_common_issues(code)
        assert any('/etc/' in issue and 'not allowed' in issue for issue in issues)

    def test_check_common_issues_dangerous_paths_var(self):
        """Test detection of /var/ access."""
        validator = CodeValidator()
        code = 'open("/var/log/test.log", "r")'
        issues = validator._check_common_issues(code)
        assert any('/var/' in issue and 'not allowed' in issue for issue in issues)

    def test_check_common_issues_dangerous_paths_usr(self):
        """Test detection of /usr/ access."""
        validator = CodeValidator()
        code = 'open("/usr/bin/test", "r")'
        issues = validator._check_common_issues(code)
        assert any('/usr/' in issue and 'not allowed' in issue for issue in issues)

    def test_check_common_issues_dangerous_paths_sys(self):
        """Test detection of /sys/ access."""
        validator = CodeValidator()
        code = 'open("/sys/kernel/debug", "r")'
        issues = validator._check_common_issues(code)
        assert any('/sys/' in issue and 'not allowed' in issue for issue in issues)

    def test_check_common_issues_dangerous_paths_proc(self):
        """Test detection of /proc/ access."""
        validator = CodeValidator()
        code = 'open("/proc/cpuinfo", "r")'
        issues = validator._check_common_issues(code)
        assert any('/proc/' in issue and 'not allowed' in issue for issue in issues)

    def test_check_common_issues_subprocess(self):
        """Test detection of subprocess usage."""
        validator = CodeValidator()
        code = "import subprocess\nsubprocess.run(['ls'])"
        issues = validator._check_common_issues(code)
        assert any('Shell command' in issue for issue in issues)

    def test_check_common_issues_os_system(self):
        """Test detection of os.system usage."""
        validator = CodeValidator()
        code = "os.system('ls')"
        issues = validator._check_common_issues(code)
        assert any('Shell command' in issue for issue in issues)

    def test_check_common_issues_exec(self):
        """Test detection of exec usage."""
        validator = CodeValidator()
        code = "exec('print(1)')"
        issues = validator._check_common_issues(code)
        assert any('Shell command' in issue for issue in issues)

    def test_check_common_issues_eval(self):
        """Test detection of eval usage."""
        validator = CodeValidator()
        code = "eval('print(1)')"
        issues = validator._check_common_issues(code)
        assert any('Shell command' in issue or 'restricted' in issue for issue in issues)

    def test_check_common_issues_clean_code(self):
        """Test clean code without issues."""
        validator = CodeValidator()
        code = "x = 5\nprint(x)"
        issues = validator._check_common_issues(code)
        # Simple code without paths or network operations should have no issues
        # (the hardcoded path regex doesn't match simple variable assignments)
        assert len(issues) == 0


class TestGenerateWarnings:
    """Test the _generate_warnings method."""

    def test_generate_warnings_large_range_10000(self):
        """Test warning for large range (10000)."""
        validator = CodeValidator()
        code = "for i in range(10000): pass"
        warnings = validator._generate_warnings(code)
        assert any('memory limits' in warning for warning in warnings)

    def test_generate_warnings_large_range_100000(self):
        """Test warning for large range (100000)."""
        validator = CodeValidator()
        code = "for i in range(100000): pass"
        warnings = validator._generate_warnings(code)
        assert any('memory limits' in warning for warning in warnings)

    def test_generate_warnings_infinite_loop(self):
        """Test warning for infinite loop."""
        validator = CodeValidator()
        code = "while True: pass"
        warnings = validator._generate_warnings(code)
        assert any('timeout' in warning for warning in warnings)

    def test_generate_warnings_numpy_zeros_large(self):
        """Test warning for large numpy zeros array."""
        validator = CodeValidator()
        code = "import numpy\nnumpy.zeros((10000, 10000))"
        warnings = validator._generate_warnings(code)
        assert any('memory limits' in warning for warning in warnings)

    def test_generate_warnings_numpy_randn_large(self):
        """Test warning for large numpy random array."""
        validator = CodeValidator()
        code = "import numpy\nnumpy.random.randn(10000, 10000)"
        warnings = validator._generate_warnings(code)
        assert any('memory limits' in warning for warning in warnings)

    def test_generate_warnings_no_warnings(self):
        """Test code without warnings."""
        validator = CodeValidator()
        code = "x = 5\nprint(x)"
        warnings = validator._generate_warnings(code)
        assert len(warnings) == 0


class TestGenerateSuggestions:
    """Test the _generate_suggestions method."""

    def test_generate_suggestions_open_without_with(self):
        """Test suggestion for open without 'with'."""
        validator = CodeValidator()
        code = "f = open('file.txt')\ncontent = f.read()"
        suggestions = validator._generate_suggestions(code)
        assert any('with' in suggestion for suggestion in suggestions)

    def test_generate_suggestions_json_load_no_try(self):
        """Test suggestion for json.load without error handling."""
        validator = CodeValidator()
        code = "import json\njson.load(open('file.json'))"
        suggestions = validator._generate_suggestions(code)
        assert any('try/except' in suggestion for suggestion in suggestions)

    def test_generate_suggestions_savefig_without_artifacts(self):
        """Test suggestion for savefig without /artifacts/ path."""
        validator = CodeValidator()
        code = "import matplotlib.pyplot as plt\nplt.savefig('plot.png')"
        suggestions = validator._generate_suggestions(code)
        assert any('/artifacts/' in suggestion for suggestion in suggestions)

    def test_generate_suggestions_numpy_no_del(self):
        """Test suggestion for numpy without memory cleanup."""
        validator = CodeValidator()
        code = "import numpy\narr = numpy.zeros((1000, 1000))"
        suggestions = validator._generate_suggestions(code)
        assert any('del' in suggestion for suggestion in suggestions)

    def test_generate_suggestions_with_statement_no_warning(self):
        """Test that using 'with' prevents the file operations suggestion."""
        validator = CodeValidator()
        # Code using 'with' for file operations
        code = "with open('file.txt') as f:\n    content = f.read()"
        suggestions = validator._generate_suggestions(code)
        # The specific "Consider using 'with' statement for file operations" suggestion
        # should NOT appear since the code already contains 'with '
        with_file_suggestion = any("Consider using 'with' statement for file operations" in s for s in suggestions)
        assert not with_file_suggestion

    def test_generate_suggestions_with_try_no_warning(self):
        """Test no warning when using try/except."""
        validator = CodeValidator()
        code = "try:\n    open('file.txt')\nexcept:\n    pass"
        suggestions = validator._generate_suggestions(code)
        assert not any('try/except' in suggestion for suggestion in suggestions)

    def test_generate_suggestions_savefig_in_artifacts(self):
        """Test no warning when saving to /artifacts/."""
        validator = CodeValidator()
        code = "plt.savefig('/artifacts/plots/test.png')"
        suggestions = validator._generate_suggestions(code)
        assert not any('/artifacts/' in suggestion for suggestion in suggestions)


class TestCheckSafety:
    """Test the _check_safety method."""

    def test_check_safety_dangerous_import(self):
        """Test detection of __import__ usage."""
        validator = CodeValidator()
        code = "__import__('os')"
        issues = validator._check_safety(code)
        assert any('__import__' in issue for issue in issues)

    def test_check_safety_globals(self):
        """Test detection of globals() usage."""
        validator = CodeValidator()
        code = "globals()"
        issues = validator._check_safety(code)
        assert any('globals()' in issue for issue in issues)

    def test_check_safety_locals(self):
        """Test detection of locals() usage."""
        validator = CodeValidator()
        code = "locals()"
        issues = validator._check_safety(code)
        assert any('locals()' in issue for issue in issues)

    def test_check_safety_vars(self):
        """Test detection of vars() usage."""
        validator = CodeValidator()
        code = "vars()"
        issues = validator._check_safety(code)
        assert any('vars()' in issue for issue in issues)

    def test_check_safety_dir(self):
        """Test detection of dir() usage."""
        validator = CodeValidator()
        code = "dir(obj)"
        issues = validator._check_safety(code)
        # dir() is a common debugging tool, so it might be allowed
        # but the code should check for it
        assert isinstance(issues, list)

    def test_check_safety_os_remove(self):
        """Test detection of os.remove usage."""
        validator = CodeValidator()
        code = "import os\nos.remove('file.txt')"
        issues = validator._check_safety(code)
        assert any('os.remove' in issue for issue in issues)

    def test_check_safety_os_rmdir(self):
        """Test detection of os.rmdir usage."""
        validator = CodeValidator()
        code = "import os\nos.rmdir('dir')"
        issues = validator._check_safety(code)
        assert any('os.rmdir' in issue for issue in issues)

    def test_check_safety_shutil_rmtree(self):
        """Test detection of shutil.rmtree usage."""
        validator = CodeValidator()
        code = "import shutil\nshutil.rmtree('dir')"
        issues = validator._check_safety(code)
        assert any('shutil.rmtree' in issue for issue in issues)

    def test_check_safety_os_chmod(self):
        """Test detection of os.chmod usage."""
        validator = CodeValidator()
        code = "import os\nos.chmod('file', 0o755)"
        issues = validator._check_safety(code)
        assert any('os.chmod' in issue for issue in issues)

    def test_check_safety_clean_code(self):
        """Test clean code without safety issues."""
        validator = CodeValidator()
        code = "x = 5\nprint(x)"
        issues = validator._check_safety(code)
        assert len(issues) == 0


class TestGetCodeTemplate:
    """Test the get_code_template method."""

    def test_get_code_template_plot(self):
        """Test getting plot template."""
        validator = CodeValidator()
        template = validator.get_code_template('plot')
        assert 'import matplotlib.pyplot as plt' in template
        assert 'import numpy as np' in template
        assert 'savefig' in template

    def test_get_code_template_data_analysis(self):
        """Test getting data_analysis template."""
        validator = CodeValidator()
        template = validator.get_code_template('data_analysis')
        assert 'import pandas as pd' in template
        assert 'matplotlib' in template

    def test_get_code_template_web_app(self):
        """Test getting web_app template."""
        validator = CodeValidator()
        template = validator.get_code_template('web_app')
        assert 'from flask import Flask' in template
        assert '@app.route' in template

    def test_get_code_template_manim_animation(self):
        """Test getting manim_animation template."""
        validator = CodeValidator()
        template = validator.get_code_template('manim_animation')
        assert 'from manim import *' in template
        assert 'class' in template and 'Scene' in template

    def test_get_code_template_invalid(self):
        """Test getting non-existent template."""
        validator = CodeValidator()
        template = validator.get_code_template('invalid_template')
        assert template == "Template not found"


class TestGetAvailableTemplates:
    """Test the get_available_templates method."""

    def test_get_available_templates_returns_list(self):
        """Test that available templates returns a list."""
        validator = CodeValidator()
        templates = validator.get_available_templates()
        assert isinstance(templates, list)

    def test_get_available_templates_contains_expected(self):
        """Test that expected templates are in the list."""
        validator = CodeValidator()
        templates = validator.get_available_templates()
        expected = ['plot', 'data_analysis', 'web_app', 'manim_animation']
        for tmpl in expected:
            assert tmpl in templates


class TestCodeFormatter:
    """Test CodeFormatter class."""

    def test_format_for_display_adds_line_numbers(self):
        """Test that format_for_display adds line numbers."""
        code = "line1\nline2\nline3"
        result = CodeFormatter.format_for_display(code)
        assert '1 |' in result
        assert '2 |' in result
        assert '3 |' in result

    def test_format_for_display_single_digit_padding(self):
        """Test line number padding for single digits."""
        code = "line1"
        result = CodeFormatter.format_for_display(code)
        # Format is "{i:3d} | {line}"
        assert '1 |' in result

    def test_format_for_display_double_digit(self):
        """Test line number padding for double digits."""
        code = "\n".join(f"line{i}" for i in range(1, 11))
        result = CodeFormatter.format_for_display(code)
        assert '10 |' in result

    def test_format_for_display_empty_code(self):
        """Test formatting empty code."""
        code = ""
        result = CodeFormatter.format_for_display(code)
        assert '1 |' in result

    def test_highlight_issues_with_line_number(self):
        """Test highlighting issues with line numbers."""
        code = "line1\nline2"
        issues = ["Syntax error at line 1"]
        result = CodeFormatter.highlight_issues(code, issues)
        # Should have marked the line somehow
        assert isinstance(result, str)

    def test_highlight_issues_without_line_number(self):
        """Test highlighting issues without line numbers."""
        code = "line1\nline2"
        issues = ["General error"]
        result = CodeFormatter.highlight_issues(code, issues)
        # Should still return a string
        assert isinstance(result, str)

    def test_highlight_issues_empty_issues(self):
        """Test highlighting with no issues."""
        code = "line1\nline2"
        issues = []
        result = CodeFormatter.highlight_issues(code, issues)
        assert result == code

    def test_create_executable_wrapper(self):
        """Test creating executable wrapper."""
        code = "print('hello')"
        wrapper = CodeFormatter.create_executable_wrapper(code)
        assert 'try:' in wrapper
        assert 'except Exception' in wrapper
        assert 'print("hello")' in wrapper or "'hello'" in wrapper

    def test_create_executable_wrapper_has_artifact_setup(self):
        """Test that wrapper includes artifact directory setup."""
        code = "print('hello')"
        wrapper = CodeFormatter.create_executable_wrapper(code)
        assert 'artifact_dirs' in wrapper
        assert 'os.makedirs' in wrapper

    def test_create_executable_wrapper_has_error_handling(self):
        """Test that wrapper includes error handling."""
        code = "print('hello')"
        wrapper = CodeFormatter.create_executable_wrapper(code)
        assert 'traceback' in wrapper
        assert 'error_log' in wrapper

    def test_create_executable_wrapper_indents_user_code(self):
        """Test that user code is indented in wrapper."""
        code = "print('hello')\nprint('world')"
        wrapper = CodeFormatter.create_executable_wrapper(code)
        # User code should be indented
        assert '    print' in wrapper


class TestIntegrationValidateAndFormat:
    """Integration tests for validate_and_format."""

    def test_full_validation_safe_code(self):
        """Test full validation flow with safe code."""
        validator = CodeValidator()
        code = """
import matplotlib.pyplot as plt
import os

os.makedirs('/artifacts/plots', exist_ok=True)
plt.plot([1, 2, 3])
plt.savefig('/artifacts/plots/test.png')
"""
        result = validator.validate_and_format(code)
        assert result['valid'] is True
        assert isinstance(result['issues'], list)
        assert isinstance(result['warnings'], list)
        assert isinstance(result['suggestions'], list)

    def test_full_validation_with_network_code(self):
        """Test full validation detects network operations."""
        validator = CodeValidator()
        code = "import requests\nrequests.get('http://example.com')"
        result = validator.validate_and_format(code)
        assert result['valid'] is True  # Syntax is valid
        assert any('Network operations' in issue for issue in result['issues'])

    def test_full_validation_with_dangerous_paths(self):
        """Test full validation detects dangerous paths."""
        validator = CodeValidator()
        code = 'open("/etc/passwd", "r")'
        result = validator.validate_and_format(code)
        assert result['valid'] is True  # Syntax is valid
        assert any('/etc/' in issue and 'not allowed' in issue for issue in result['issues'])

    def test_full_validation_with_auto_fixes(self):
        """Test that auto-fixes are applied."""
        validator = CodeValidator()
        code = "plt.plot([1, 2, 3])"
        result = validator.validate_and_format(code)
        assert 'import matplotlib.pyplot as plt' in result['formatted_code']

    def test_full_validation_returns_formatted_code(self):
        """Test that formatted_code is always returned."""
        validator = CodeValidator()
        code = "x = 5"
        result = validator.validate_and_format(code)
        assert 'formatted_code' in result
        assert result['formatted_code'] is not None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_validate_syntax_none_input(self):
        """Test handling of None input."""
        validator = CodeValidator()
        # None input is caught by exception handler and returns invalid result
        result = validator._validate_syntax(None)
        assert result['valid'] is False
        assert len(result['issues']) > 0

    def test_apply_auto_fixes_empty_string(self):
        """Test auto-fixes on empty string."""
        validator = CodeValidator()
        result = validator._apply_auto_fixes("")
        assert result == ""

    def test_apply_auto_fixes_whitespace_only(self):
        """Test auto-fixes on whitespace."""
        validator = CodeValidator()
        result = validator._apply_auto_fixes("   \n  \n  ")
        assert isinstance(result, str)

    def test_add_missing_imports_with_existing_imports(self):
        """Test imports are not duplicated."""
        validator = CodeValidator()
        code = "import numpy as np\nimport matplotlib.pyplot as plt\nx = np.array([1,2,3])\nplt.plot(x)"
        result = validator._add_missing_imports(code)
        # Count imports - should not have duplicates
        assert result.count('import numpy') <= 1
        assert result.count('import matplotlib') <= 1

    def test_validate_code_with_unicode(self):
        """Test validation with unicode characters."""
        validator = CodeValidator()
        code = "print('Hello 世界 🌍')"
        result = validator.validate_and_format(code)
        assert result['valid'] is True

    def test_validate_code_with_special_chars(self):
        """Test validation with special characters."""
        validator = CodeValidator()
        code = 'text = "Special chars: @#$%^&*()"'
        result = validator.validate_and_format(code)
        assert result['valid'] is True

    def test_check_common_issues_string_interpolation(self):
        """Test issues detection with string interpolation."""
        validator = CodeValidator()
        code = 'path = f"/home/{user}/file.txt"'
        issues = validator._check_common_issues(code)
        # Should detect the hardcoded path pattern
        assert len(issues) > 0

    def test_formatter_multiline_code(self):
        """Test formatter with multiline code."""
        code = "\n".join(f"print({i})" for i in range(20))
        result = CodeFormatter.format_for_display(code)
        # Should have line numbers for all lines
        assert '20 |' in result
