# Changelog

## Version History

### [0.4.0] - 2026-03-12

#### Major Release: Security Hardening & Comprehensive Isolation

This release completes the Quality Remediation Track with hardened security, comprehensive isolation features, and extensive documentation.

#### Security Fixes (TZAR Review)

All critical security vulnerabilities identified in the TZAR review have been remediated with TDD tests:

##### Critical Vulnerabilities Fixed
- **CRIT-1**: Session ID path traversal - Added `PathValidator.sanitize_path_component()` with comprehensive validation
- **CRIT-2**: Backup path traversal - Hardened validation in `ArtifactBackupService` with null byte checks, path separator rejection, and length limits
- **CRIT-3**: Symlink exfiltration - Symlinks now skipped in artifact scanning to prevent host file enumeration
- **CRIT-4**: Cross-session artifact leakage - Implemented thread-local storage for session-specific `artifacts_dir`
- **CRIT-5**: Path validation bypass - Replaced `startswith()` with `is_relative_to()` for proper path boundary checks
- **CRIT-6**: HTTP transport session service - Session service now properly injected into HTTP server for transport parity
- **CRIT-7**: Duplicate ExecutionContext - Verified as false positive (intentional architecture: `ExecutionContext` vs `PersistentExecutionContext`)

##### Security Test Coverage
- 658 tests passing (exceeds 602+ requirement by 56 tests)
- All security fixes have dedicated TDD tests
- Security-critical paths at 100% coverage (`code_validator.py`, SDK modules)
- Overall coverage increased from 29% to 61%

#### Isolation Features

##### Process Pool Isolation (NEW)
- **IsolationLevel.PROCESS_POOL**: True process-level isolation prevents module pollution
- Resource-efficient process pool with configurable `max_workers`
- Memory limits per process (platform-dependent via `resource` module)
- Worker recycling for low overhead (~0.023s per execution)
- Timeout handling and automatic cleanup
- 36 comprehensive tests covering isolation, performance, and edge cases

##### Worktree Isolation (NEW)
- **IsolationLevel.WORKTREE**: Git worktree-based filesystem isolation
- Independent git state per session
- Optional auto-merge on sandbox close
- Automatic worktree cleanup
- Support for custom base branches
- 29 comprehensive tests covering git operations and isolation

##### In-Process Isolation (Enhanced)
- **IsolationLevel.IN_PROCESS**: Default behavior with isolated execution globals
- Thread-safe session management with RLock
- Session-specific artifacts directories
- Isolated execution_globals per session

#### Architecture Improvements

##### Core Services Created
- `SessionExecutionContextManager` - Per-session execution context management
- `ExecutionContextService` - Unified context creation and management
- `PatchManager` - Centralized monkey patch management
- `PathValidator` - Centralized path validation with security focus
- `SandboxProcessPool` - Resource-efficient process pool for isolation
- `WorktreeManager` - Git worktree management for filesystem isolation

##### Server Services Enhanced
- `SessionService` - Enhanced with thread safety and execute_in_session()
- `ToolRegistry` - Shared tool registry across transports
- `EnhancedREPL` - Improved REPL with better error handling
- Helper modules split for maintainability:
  - `execution_helpers.py` - Execution utilities
  - `artifact_helpers.py` - Artifact management
  - `manim_helpers.py` - Manim integration
  - `package_helpers.py` - Package management
  - `shell_helpers.py` - Shell execution
  - `info_helpers.py` - System information

##### Module Splitting (Maintainability)
- `execution_context.py`: 1,212 → 640 lines (47% reduction)
  - `execution_context_db.py` - Database transaction management
  - `execution_context_monitor.py` - Directory change monitoring
  - `execution_context_artifacts.py` - Artifact collection/categorization
  - `execution_context_files.py` - File operations
  - `execution_context_state.py` - State persistence/HMAC
- `web_export_service.py`: 1,069 → 675 lines (37% reduction)
  - `web_export_docker.py` - Docker management
  - `web_export_templates.py` - Template generation
  - `web_export_validation.py` - Validation logic
  - `web_export_validators.py` - Validators

##### Server Refactoring
- `mcp_sandbox_server_stdio.py`: 2,727 → 302 lines (89% reduction)
- `mcp_sandbox_server.py`: 539 → 58 lines (89% reduction)
- Both transports now use shared `tool_registry` and `ExecutionContext`

#### Documentation

##### New Documentation
- **SECURITY.md** - Comprehensive threat model documentation
  - Single-user vs multi-tenant scenarios
  - Multi-LLM scenario analysis
  - Isolation level comparison table
  - Resource management guidelines
  - Security properties (what we protect against and limitations)

##### Updated Documentation
- **README.md** - Added Security Model section with clear warnings
- **CLAUDE.md** - Updated with LeIndex MCP requirements
- **docs/FAQ_AND_LIMITATIONS.md** - Process-wide state limitations documented

#### Configuration Enhancements

##### New SandboxConfig Options
```python
# Isolation levels
isolation_level: IsolationLevel = IsolationLevel.IN_PROCESS

# Process pool settings
max_workers: Optional[int] = None
memory_limit_mb: Optional[int] = 256

# Worktree settings
use_worktree: bool = False
worktree_base_branch: str = "main"
auto_merge_on_close: bool = False
auto_delete_worktree: bool = True
```

##### Builder Pattern
```python
config = SandboxOptions.builder() \
    .isolation_level(IsolationLevel.PROCESS_POOL) \
    .max_workers(4) \
    .memory_limit_mb(256) \
    .worktree(base_branch="main", auto_merge=True) \
    .build()
```

#### Testing

##### Test Coverage Improvements
- Total tests: 658 passing (from 231)
- Test files added: 29 new files
- Coverage: 29% → 61% (32 point increase)
- Security-critical paths: 100% coverage

##### New Test Files
- `tests/core/test_code_validator.py` - 56 tests
- `tests/core/test_execution_context_artifacts.py` - 9 tests
- `tests/core/test_patching.py` - 10 tests
- `tests/core/test_session_execution_manager.py` - 17 tests
- `tests/core/test_process_pool.py` - 36 tests
- `tests/core/test_worktree_isolation.py` - 29 tests
- `tests/sdk/test_sdk_coverage.py` - SDK coverage tests
- `tests/server/test_transport_parity.py` - 10 tests

#### Performance

##### Benchmarks
- Process pool: ~0.023s per execution (excellent)
- Worker recycling: Keeps resource overhead low
- Memory limits: Prevent runaway processes
- Max workers cap: Prevents resource exhaustion

#### Bug Fixes

- Fixed critical syntax error in `code_validator.py`
- Fixed version inconsistency (now reads from package metadata)
- Fixed unsafe exception handling with specific error types
- Fixed 3 bugs from code review (get_execution_info, web app launches, context tracking)
- Fixed asyncio.run conflicts with run_coroutine_threadsafe

#### Dependencies

##### Added
- `aiohttp>=3.9.0` - HTTP client support

#### Breaking Changes

None. All changes are backward compatible with existing code.

#### Migration Guide

##### Using New Isolation Features

```python
# Process Pool Isolation (recommended for multi-LLM scenarios)
from sandbox.sdk import LocalSandbox, SandboxConfig, IsolationLevel

config = SandboxConfig(
    isolation_level=IsolationLevel.PROCESS_POOL,
    max_workers=4,
    memory_limit_mb=256
)

async with LocalSandbox.create(name="my-session", config=config) as sandbox:
    result = await sandbox.run("import sys; sys.my_data = 'secret'")
    # Process isolation prevents module pollution

# Worktree Isolation (for parallel development workflows)
config = SandboxConfig(
    isolation_level=IsolationLevel.WORKTREE,
    worktree_base_branch="main",
    auto_merge_on_close=True
)

async with LocalSandbox.create(name="dev-session", config=config) as sandbox:
    result = await sandbox.run("# Code that modifies git repo")
    # Changes automatically committed and merged on close
```

#### Acknowledgments

Security review conducted using TZAR (Zero-Tolerance Autonomous Review) methodology with codex-reviewer agent.

---

### [0.3.0] - 2025-07-14
#### Added
- Complete integration with microsandbox functionality
- Unified API for local and remote execution
- Secure remote execution via microsandbox server
- Support for Python and Node.js environments
- Fluent configuration API with builder pattern
- Real-time resource usage tracking with metrics
- Modern Python async support
- Enhanced resource management with memory monitoring and process lifecycle management
- Automatic cleanup system for zombie processes and resource leaks
- Thread pool management with configurable limits
- Advanced security system with regex-based command filtering
- Multi-level security enforcement (LOW, MEDIUM, HIGH, CRITICAL)
- Filesystem access controls and network security
- Real-time security audit logging and violation tracking
- Secure workspace creation and management
- Input validation and sanitization
- Port allocation and network access controls
- MCP tools for resource stats and emergency cleanup
- Comprehensive file artifact handling
- Safe shell command execution with timeouts
- Flexible sandbox configuration options
- Comprehensive examples and guides

### [0.2.0] - 2023-07-01
#### Added
- Full mathematical animation support with Manim
- 4 new MCP tools: create_manim_animation, list_manim_animations, cleanup_manim_animation, get_manim_examples
- Multiple animation quality presets
- Auto-saving MP4 animations as artifacts
- Built-in Manim code examples

### [0.1.0] - 2023-01-15
#### Added
- Initial enhanced package structure
- Dynamic project root detection
- Robust virtual environment integration
- Enhanced error handling with detailed tracebacks
- Artifact management with Matplotlib/PIL support
- Web app launching (Flask/Streamlit)
- Comprehensive test suite
- MCP server integration (HTTP and stdio)
- CLI entry points
- LM Studio compatibility

## Future Plans
- Container isolation integration (Docker, microVMs)
- Enhanced monitoring features
- More language support
- Cloud deployment options
