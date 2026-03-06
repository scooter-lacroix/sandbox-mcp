# Product Guidelines - Sandbox MCP Server

## Code Philosophy

### Simple and Readable (Pythonic)

- **Explicit over Implicit**: Code should be self-documenting. Avoid clever tricks that sacrifice clarity.
- **PEP 8 Compliance**: Follow Python style guidelines consistently.
- **Meaningful Names**: Variables, functions, and classes should have descriptive names.
- **Keep Functions Focused**: Each function should do one thing well. Aim for under 50 lines.
- **Early Returns**: Return early from functions to reduce nesting.

### Documentation Standards

**Google/PyTorch Style Docstrings** with examples:

```python
def execute_code(self, code: str, validate: bool = True) -> Dict[str, Any]:
    """Execute Python code with validation and artifact tracking.

    This method compiles and executes the provided Python code in a
    persistent context, capturing output and tracking generated artifacts.

    Args:
        code: The Python code to execute as a string.
        validate: Whether to validate code syntax before execution.
            Defaults to True.

    Returns:
        A dictionary containing:
            - success (bool): Whether execution succeeded
            - stdout (str): Captured standard output
            - stderr (str): Captured standard error
            - artifacts (List[str]): List of generated artifact files

    Raises:
        SandboxExecutionError: If code validation fails or execution
            encounters a critical error.

    Example:
        >>> sandbox = LocalSandbox.create(name="test")
        >>> result = sandbox.execute_code("print('hello')")
        >>> print(result['success'])
        True
    """
```

## Testing Approach

### Test-Driven Development (TDD)

1. **Write Tests First**: Create failing tests before implementing features
2. **Red-Green-Refactor**: Follow the TDD cycle
3. **High Coverage Goal**: Aim for 90%+ code coverage
4. **Test Categories**:
   - Unit tests for individual functions/classes
   - Integration tests for MCP tool interactions
   - Security tests for sandbox boundaries

### Test Structure

```python
class TestLocalSandbox:
    def test_execute_code_returns_success(self):
        """Test that valid code execution returns success=True."""
        sandbox = LocalSandbox.create(name="test")
        result = sandbox.run("x = 1 + 1")
        assert result["success"] is True

    def test_artifacts_are_captured(self):
        """Test that matplotlib plots are captured as artifacts."""
        # Write test, then implement
```

## Security Guidelines

- **Directory Boundaries**: Never allow access outside user's home directory
- **Command Filtering**: Block dangerous shell commands (rm -rf, etc.)
- **Resource Limits**: Enforce memory and execution time limits
- **Input Validation**: Always validate and sanitize user input

## Error Handling

- **Specific Exceptions**: Use specific exception types, not bare `except:`
- **Contextual Messages**: Include relevant context in error messages
- **Recovery Paths**: Provide clear paths for recovery when possible
- **Log Errors**: Always log errors with sufficient detail for debugging
