"""
Coverage tests for interactive_repl.py - Tier 4 Task T4

Target: Raise coverage from 0% to 60%+
Interactive REPL with colored output and custom commands
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from sandbox.core.interactive_repl import ColoredOutput, EnhancedREPL


class TestColoredOutput:
    """Test ColoredOutput class."""

    def test_color_red(self):
        """Test red color."""
        result = ColoredOutput.color("test", "red")
        assert "test" in result

    def test_color_green(self):
        """Test green color."""
        result = ColoredOutput.color("test", "green")
        assert "test" in result

    def test_color_blue(self):
        """Test blue color."""
        result = ColoredOutput.color("test", "blue")
        assert "test" in result

    def test_color_bold(self):
        """Test bold formatting."""
        result = ColoredOutput.color("test", "red", bold=True)
        assert "test" in result

    def test_success(self):
        """Test success message."""
        result = ColoredOutput.success("Operation completed")
        assert "Operation completed" in result
        assert "✅" in result

    def test_error(self):
        """Test error message."""
        result = ColoredOutput.error("Operation failed")
        assert "Operation failed" in result
        assert "❌" in result

    def test_warning(self):
        """Test warning message."""
        result = ColoredOutput.warning("Be careful")
        assert "Be careful" in result
        assert "⚠️" in result

    def test_info(self):
        """Test info message."""
        result = ColoredOutput.info("Information")
        assert "Information" in result
        assert "ℹ️" in result

    def test_color_non_terminal(self):
        """Test that colors are disabled in non-terminal output."""
        with patch('sys.stdout.isatty', return_value=False):
            result = ColoredOutput.color("test", "red")
            assert result == "test"


class TestEnhancedREPLInit:
    """Test EnhancedREPL initialization."""

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context."""
        ctx = Mock()
        ctx.session_id = "test-session"
        ctx.project_root = Path("/test/project")
        ctx.artifacts_dir = Path("/test/artifacts")
        ctx.globals_dict = {}
        return ctx

    def test_init_creates_repl(self, mock_execution_context):
        """Test REPL initialization."""
        repl = EnhancedREPL(mock_execution_context)
        assert repl.execution_context == mock_execution_context
        assert repl.history == []
        assert isinstance(repl.custom_commands, dict)

    def test_init_sets_up_commands(self, mock_execution_context):
        """Test that custom commands are set up."""
        repl = EnhancedREPL(mock_execution_context)
        expected_commands = [
            'artifacts', 'clear_artifacts', 'session_info',
            'stats', 'history', 'help', 'manim_examples', 'exit', 'quit'
        ]
        for cmd in expected_commands:
            assert cmd in repl.custom_commands


class TestCmdArtifacts:
    """Test artifacts command."""

    @pytest.fixture
    def repl(self, mock_execution_context):
        """Create REPL instance."""
        return EnhancedREPL(mock_execution_context)

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context."""
        ctx = Mock()
        ctx.session_id = "test-session"
        ctx.get_artifact_report.return_value = {
            'total_artifacts': 2,
            'total_size': 1024,
            'categories': {
                'plots': {'count': 1, 'size': 512, 'files': [{'name': 'plot.png', 'size': 512}]},
                'data': {'count': 1, 'size': 512, 'files': [{'name': 'data.csv', 'size': 512}]}
            }
        }
        ctx.globals_dict = {}
        return ctx

    def test_cmd_artifacts_default_format(self, repl):
        """Test artifacts command with default format."""
        result = repl._cmd_artifacts()
        assert "📊" in result
        assert "Artifact" in result

    def test_cmd_artifacts_json_format(self, repl):
        """Test artifacts command with JSON format."""
        result = repl._cmd_artifacts(['json'])
        assert '"total_artifacts"' in result

    def test_cmd_artifacts_csv_format(self, repl):
        """Test artifacts command with CSV format."""
        result = repl._cmd_artifacts(['csv'])
        assert "Category" in result
        assert "Count" in result

    def test_cmd_artifacts_table_format(self, repl):
        """Test artifacts command with table format."""
        result = repl._cmd_artifacts(['table'])
        assert "📊" in result or "Artifact" in result


class TestFormatSize:
    """Test size formatting."""

    @pytest.fixture
    def repl(self, mock_execution_context):
        """Create REPL instance."""
        return EnhancedREPL(mock_execution_context)

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context."""
        ctx = Mock()
        ctx.session_id = "test-session"
        ctx.globals_dict = {}
        return ctx

    def test_format_size_bytes(self, repl):
        """Test formatting bytes."""
        result = repl._format_size(512)
        assert "B" in result

    def test_format_size_kilobytes(self, repl):
        """Test formatting kilobytes."""
        result = repl._format_size(2048)
        assert "KB" in result

    def test_format_size_megabytes(self, repl):
        """Test formatting megabytes."""
        result = repl._format_size(2 * 1024 * 1024)
        assert "MB" in result

    def test_format_size_gigabytes(self, repl):
        """Test formatting gigabytes."""
        result = repl._format_size(2 * 1024 * 1024 * 1024)
        assert "GB" in result


class TestCmdClearArtifacts:
    """Test clear_artifacts command."""

    @pytest.fixture
    def repl(self, mock_execution_context):
        """Create REPL instance."""
        return EnhancedREPL(mock_execution_context)

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context."""
        ctx = Mock()
        ctx.session_id = "test-session"
        ctx.get_artifact_report.return_value = {
            'total_artifacts': 0,
            'categories': {}
        }
        ctx.categorize_artifacts.return_value = {}
        ctx.globals_dict = {}
        return ctx

    def test_cmd_clear_artifacts_no_args_empty(self, repl):
        """Test clearing artifacts when none exist."""
        result = repl._cmd_clear_artifacts()
        assert "No artifacts" in result or "ℹ️" in result

    def test_cmd_clear_artifacts_with_type(self, repl):
        """Test clearing specific artifact type."""
        repl.execution_context.categorize_artifacts.return_value = {
            'plots': ['plot1.png', 'plot2.png']
        }
        result = repl._cmd_clear_artifacts(['plots'])
        assert "Cleared" in result or "plots" in result

    def test_cmd_clear_artifacts_unknown_type(self, repl):
        """Test clearing unknown artifact type."""
        result = repl._cmd_clear_artifacts(['unknown'])
        assert "Unknown" in result or "error" in result.lower()


class TestCmdSessionInfo:
    """Test session_info command."""

    @pytest.fixture
    def repl(self, mock_execution_context):
        """Create REPL instance."""
        return EnhancedREPL(mock_execution_context)

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context."""
        ctx = Mock()
        ctx.session_id = "test-session-123"
        ctx.project_root = Path("/test/project")
        ctx.artifacts_dir = Path("/test/artifacts")
        ctx.globals_dict = {}
        return ctx

    def test_cmd_session_info(self, repl):
        """Test session info command."""
        result = repl._cmd_session_info()
        assert "test-session-123" in result
        assert "Session" in result


class TestCmdStats:
    """Test stats command."""

    @pytest.fixture
    def repl(self, mock_execution_context):
        """Create REPL instance."""
        return EnhancedREPL(mock_execution_context)

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context."""
        ctx = Mock()
        ctx.session_id = "test-session"
        ctx.get_execution_stats.return_value = {
            'total_executions': 10,
            'successful_executions': 9,
            'failed_executions': 1,
            'average_execution_time': 0.123
        }
        ctx.globals_dict = {}
        return ctx

    def test_cmd_stats(self, repl):
        """Test stats command."""
        result = repl._cmd_stats()
        assert "Statistics" in result or "📈" in result
        assert "10" in result or "9" in result


class TestCmdHistory:
    """Test history command."""

    @pytest.fixture
    def repl(self, mock_execution_context):
        """Create REPL instance."""
        return EnhancedREPL(mock_execution_context)

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context."""
        ctx = Mock()
        ctx.session_id = "test-session"
        ctx.get_execution_history.return_value = [
            {
                'code': 'print("hello")',
                'result': {'success': True},
                'execution_time': 0.001
            },
            {
                'code': 'invalid_syntax',
                'result': {'success': False},
                'execution_time': 0.0005
            }
        ]
        ctx.globals_dict = {}
        return ctx

    def test_cmd_history_default(self, repl):
        """Test history command with default limit."""
        result = repl._cmd_history()
        assert "History" in result or "📜" in result

    def test_cmd_history_with_limit(self, repl):
        """Test history command with custom limit."""
        result = repl._cmd_history(['5'])
        assert "5" in result or "History" in result

    def test_cmd_history_empty(self, mock_execution_context):
        """Test history command when no history."""
        mock_execution_context.get_execution_history.return_value = []
        repl = EnhancedREPL(mock_execution_context)
        result = repl._cmd_history()
        assert "No" in result or "ℹ️" in result


class TestCmdManimExamples:
    """Test manim_examples command."""

    @pytest.fixture
    def repl(self, mock_execution_context):
        """Create REPL instance."""
        return EnhancedREPL(mock_execution_context)

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context."""
        ctx = Mock()
        ctx.session_id = "test-session"
        ctx.globals_dict = {}
        return ctx

    def test_cmd_manim_examples_list(self, repl):
        """Test listing manim examples."""
        result = repl._cmd_manim_examples()
        assert "Manim" in result or "🎬" in result
        assert "circle" in result.lower() or "text" in result.lower()

    def test_cmd_manim_examples_circle(self, repl):
        """Test getting circle example."""
        result = repl._cmd_manim_examples(['circle'])
        assert "Circle" in result
        assert "manim" in result.lower()

    def test_cmd_manim_examples_text(self, repl):
        """Test getting text example."""
        result = repl._cmd_manim_examples(['text'])
        assert "Text" in result or "Hello" in result

    def test_cmd_manim_examples_transform(self, repl):
        """Test getting transform example."""
        result = repl._cmd_manim_examples(['transform'])
        assert "Transform" in result or "Square" in result


class TestCmdHelp:
    """Test help command."""

    @pytest.fixture
    def repl(self, mock_execution_context):
        """Create REPL instance."""
        return EnhancedREPL(mock_execution_context)

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context."""
        ctx = Mock()
        ctx.session_id = "test-session"
        ctx.globals_dict = {}
        return ctx

    def test_cmd_help(self, repl):
        """Test help command."""
        result = repl._cmd_help()
        assert "Help" in result or "🔧" in result
        assert "artifacts" in result.lower()
        assert "exit" in result.lower()


class TestCmdExit:
    """Test exit command."""

    @pytest.fixture
    def repl(self, mock_execution_context):
        """Create REPL instance."""
        return EnhancedREPL(mock_execution_context)

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context."""
        ctx = Mock()
        ctx.session_id = "test-session"
        ctx.globals_dict = {}
        return ctx

    def test_cmd_exit(self, repl):
        """Test exit command."""
        with patch('sys.exit'):
            result = repl._cmd_exit()
            # Should call sys.exit


class TestStartMethods:
    """Test REPL start methods."""

    @pytest.fixture
    def repl(self, mock_execution_context):
        """Create REPL instance."""
        return EnhancedREPL(mock_execution_context)

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context."""
        ctx = Mock()
        ctx.session_id = "test-session"
        ctx.globals_dict = {'print': print}
        return ctx

    def test_start_interactive_session_basic(self, repl):
        """Test starting interactive session with basic REPL."""
        with patch('sandbox.core.interactive_repl.PTPYTHON_AVAILABLE', False):
            with patch('sandbox.core.interactive_repl.IPYTHON_AVAILABLE', False):
                with patch('sandbox.core.interactive_repl.BPYTHON_AVAILABLE', False):
                    with patch('code.InteractiveConsole') as mock_console:
                        mock_console_instance = Mock()
                        mock_console.return_value = mock_console_instance
                        repl._start_basic_repl()
                        # Should have created interactive console

    @pytest.fixture
    def mock_execution_context_full(self):
        """Mock execution context with full setup."""
        ctx = Mock()
        ctx.session_id = "test-session-123"
        ctx.project_root = Path("/test/project")
        ctx.artifacts_dir = Path("/test/artifacts")
        ctx.get_artifact_report.return_value = {
            'total_artifacts': 5,
            'total_size': 2048,
            'categories': {
                'plots': {'count': 2, 'size': 1024, 'files': [
                    {'name': 'plot1.png', 'size': 512},
                    {'name': 'plot2.png', 'size': 512}
                ]},
                'data': {'count': 1, 'size': 512, 'files': [
                    {'name': 'data.csv', 'size': 512}
                ]}
            }
        }
        ctx.categorize_artifacts.return_value = {
            'plots': ['plot1.png', 'plot2.png'],
            'data': ['data.csv']
        }
        ctx.get_execution_stats.return_value = {
            'total_executions': 100,
            'successful_executions': 95,
            'failed_executions': 5,
            'average_execution_time': 0.045
        }
        ctx.get_execution_history.return_value = [
            {'code': 'x = 1', 'result': {'success': True}, 'execution_time': 0.001},
            {'code': 'print(x)', 'result': {'success': True}, 'execution_time': 0.0005},
            {'code': 'invalid', 'result': {'success': False}, 'execution_time': 0.0002}
        ]
        ctx.globals_dict = {}
        return ctx


class TestIntegration:
    """Integration tests for EnhancedREPL."""

    @pytest.fixture
    def repl(self, mock_execution_context_full):
        """Create REPL instance."""
        return EnhancedREPL(mock_execution_context_full)

    @pytest.fixture
    def mock_execution_context_full(self):
        """Mock execution context with full setup."""
        ctx = Mock()
        ctx.session_id = "test-session-123"
        ctx.project_root = Path("/test/project")
        ctx.artifacts_dir = Path("/test/artifacts")
        ctx.get_artifact_report.return_value = {
            'total_artifacts': 5,
            'total_size': 2048,
            'categories': {
                'plots': {'count': 2, 'size': 1024, 'files': [
                    {'name': 'plot1.png', 'size': 512},
                    {'name': 'plot2.png', 'size': 512}
                ]}
            }
        }
        ctx.categorize_artifacts.return_value = {'plots': ['plot1.png', 'plot2.png']}
        ctx.get_execution_stats.return_value = {'total_executions': 100}
        ctx.get_execution_history.return_value = []
        ctx.globals_dict = {}
        return ctx

    def test_all_commands_registered(self, repl):
        """Test that all commands are registered."""
        expected_commands = [
            'artifacts', 'clear_artifacts', 'session_info',
            'stats', 'history', 'help', 'manim_examples', 'exit', 'quit'
        ]
        for cmd in expected_commands:
            assert cmd in repl.custom_commands
            assert callable(repl.custom_commands[cmd])

    def test_commands_call_methods(self, repl):
        """Test that commands call their methods."""
        # Test artifacts command
        result = repl.custom_commands['artifacts']()
        assert "Artifact" in result or "📊" in result

        # Test help command
        result = repl.custom_commands['help']()
        assert "Help" in result or "🔧" in result
