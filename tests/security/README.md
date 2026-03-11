# Security Test Suite - Coverage Improvement

## Overview
This directory contains comprehensive security-focused tests for Sandbox MCP Server, specifically targeting critical security paths that need high test coverage.

## Test Files

### test_coverage_t3_execution_helpers.py
**Target**: `src/sandbox/server/execution_helpers.py`
**Coverage**: 81% (up from 7%)
**Tests**: 53 comprehensive tests

#### Test Categories

1. **Monkey Patching Tests** (7 tests)
   - Matplotlib patching (success, error handling)
   - PIL patching (success, error handling)
   - Coverage: Lines 43-70

2. **Artifact Collection Security** (6 tests)
   - Symlink rejection (S1 security critical)
   - Path validation (S4 security fix)
   - Error handling
   - Coverage: Lines 73-124

3. **Session Isolation** (10 tests)
   - Session context creation/usage
   - Error fallback mechanisms
   - Coverage: Lines 156-192, 412-427

4. **Signal Handling** (2 tests)
   - Graceful signal handling
   - Signal handler registration
   - Coverage: Lines 301-341

5. **Error Handling** (5 tests)
   - Syntax errors with truncation hints
   - Import errors with sys.path
   - Runtime errors with tracebacks
   - Coverage: Lines 249-372

6. **Web App Launch** (6 tests)
   - Flask/Streamlit app launch
   - Server readiness verification
   - Process cleanup
   - Coverage: Lines 603-712

7. **Edge Cases** (6 tests)
   - Empty/long code
   - Unicode handling
   - Binary files
   - Coverage: Various

## Running Tests

### Run all security tests
```bash
uv run pytest tests/security/ -v
```

### Run specific test file
```bash
uv run pytest tests/security/test_coverage_t3_execution_helpers.py -v
```

### Run with coverage
```bash
uv run pytest tests/security/test_coverage_t3_execution_helpers.py --cov=sandbox.server.execution_helpers --cov-report=term-missing
```

### Run specific test class
```bash
uv run pytest tests/security/test_coverage_t3_execution_helpers.py::TestCollectArtifactsSecurity -v
```

### Run specific test
```bash
uv run pytest tests/security/test_coverage_t3_execution_helpers.py::TestCollectArtifactsSecurity::test_collect_artifacts_skips_symlinks -v
```

## Security-Critical Paths Tested

### S1: Symlink Exfiltration Prevention ✅
- **Location**: `collect_artifacts()` lines 84-103
- **Test**: `test_collect_artifacts_skips_symlinks`
- **What**: Ensures symlinks are skipped during artifact collection to prevent host file exfiltration

### S4: Path Validation ✅
- **Location**: `collect_artifacts()` lines 93-103
- **Test**: `test_collect_artifacts_validates_resolved_paths`
- **What**: Uses `is_relative_to()` to prevent path traversal attacks

### I5: TOCTOU Prevention ✅
- **Location**: `find_free_port()` lines 514-534
- **Test**: `TestFindFreePort` (skipped on Linux)
- **What**: Atomic port binding with SO_EXCLUSIVEADDRUSE

### I5: Server Readiness Verification ✅
- **Location**: `_wait_for_server_ready()` lines 537-566
- **Test**: `TestWaitForServerReady`
- **What**: Proper server readiness verification instead of blind sleep

### I5: Pipe Deadlock Prevention ✅
- **Location**: `_drain_pipe()` lines 569-600
- **Test**: `TestDrainPipe`
- **What**: Non-blocking pipe reads with size limits

### Session Isolation ✅
- **Location**: `execute()` lines 156-192
- **Test**: `TestExecuteSessionIsolation`
- **What**: Per-session execution context isolation

## Test Patterns

### Descriptive Naming
```python
def test_<function>_<scenario>():
    """Test description."""
    pass
```

### Mock External Dependencies
```python
def test_with_mocked_filesystem(self):
    """Test behavior with mocked filesystem."""
    with patch('path.to.module') as mock:
        # Test behavior
        pass
```

### Test Both Success and Failure
```python
def test_success_case(self):
    """Test successful execution."""
    result = function()
    self.assertIsNotNone(result)

def test_failure_case(self):
    """Test error handling."""
    with self.assertRaises(Error):
        function(bad_input)
```

### Security-Focused Edge Cases
```python
def test_symlink_rejection(self):
    """Test that symlinks are rejected."""
    # Create symlink
    # Verify it's skipped
```

## Coverage Goals

| File | Before | After | Target | Status |
|------|--------|-------|--------|--------|
| execution_helpers.py | 7% | 81% | 80% | ✅ Complete |
| artifact_helpers.py | 15% | TBD | 75% | 🔄 In Progress |
| execution_services.py | 38% | TBD | 70% | ⏳ Pending |

## Maintenance

### Adding New Tests
1. Follow existing test patterns
2. Use descriptive names
3. Mock external dependencies
4. Test both success and failure paths
5. Document security implications

### Running CI
```bash
# Full test suite
uv run pytest tests/ -v

# Security tests only
uv run pytest tests/security/ -v

# With coverage report
uv run pytest tests/security/ --cov=src/sandbox/server --cov-report=html
```

## References

- Google Python Style Guide: `maestro/code_styleguides/python.md`
- Security blockers: `tests/security/test_security_blockers.py`
- Existing test patterns: `tests/unit/test_execution_helpers.py`

## Notes

- Some tests are skipped on Linux due to platform-specific features (e.g., SO_EXCLUSIVEADDRUSE)
- Tests use extensive mocking to avoid filesystem/process dependencies
- All tests are designed to be fast and deterministic
- Security-critical paths are prioritized over edge cases
