# Implementation Plan - Sandbox MCP Complete Remediation

**Track:** quality-remediation_20260306
**Approach:** TDD with growing coverage, grouped by architecture

---

## Phase 1: Critical Syntax & Runtime Fixes

### Goal
Fix blocking syntax errors and make package importable

- [x] Task: Fix `code_validator.py` syntax error
  - [x] Subtask: Write failing test for CodeValidator import
  - [x] Subtask: Remove literal `\n` at line 74
  - [x] Subtask: Verify `python -m compileall src` passes
- [x] Task: Add missing `aiohttp` dependency to pyproject.toml
  - [x] Subtask: Add aiohttp to dependencies
  - [x] Subtask: Verify `import sandbox` succeeds
- [x] Task: Create tests directory structure
  - [x] Subtask: Create tests/ directory with __init__.py
  - [x] Subtask: Create tests/unit/ subdirectory
  - [x] Subtask: Create tests/integration/ subdirectory
  - [x] Subtask: Create tests/fixtures/ subdirectory
- [x] Task: Write smoke test for package import
  - [x] Subtask: Create test_import_smoke.py
  - [x] Subtask: Test that `import sandbox` succeeds
  - [x] Subtask: Test that all main submodules are importable
- [x] Task: Maestro - Phase Verification and Checkpoint 'Critical Syntax & Runtime Fixes' (Protocol in workflow.md) [checkpoint: d94b818]

---

## Phase 2: Dependency & Packaging Architecture

### Goal
Implement dependency extras and fix version inconsistencies

- [x] Task: Implement dependency extras structure
  - [x] Subtask: Write tests for optional extras imports
  - [x] Subtask: Add `[project.optional-dependencies]` with `web`, `sdk-remote`, `dev`
  - [x] Subtask: Move Flask/Streamlit to `web` extra
  - [x] Subtask: Verify core works without optional deps
- [x] Task: Fix version inconsistencies across files
  - [x] Subtask: Write tests for version constant
  - [x] Subtask: Create single source of truth in pyproject.toml
  - [x] Subtask: Update `__init__.py` to read version from package
  - [x] Subtask: Update SDK `__init__.py` to read version
  - [x] Subtask: Verify all versions match
- [x] Task: Update README/docs for Python version consistency
  - [x] Subtask: Document Python 3.11+ requirement (not 3.9+)
  - [x] Subtask: Remove or qualify undocumented features (Flask/Streamlit)
  - [x] Subtask: Add supported feature matrix to README
- [x] Task: Maestro - Phase Verification and Checkpoint 'Dependency & Packaging Architecture' (Protocol in workflow.md) [checkpoint: 11a5d08]

---

## Phase 3: Test Infrastructure

### Goal
Build comprehensive test suite with TDD

- [x] Task: MCP server startup smoke test
  - [x] Subtask: Write test for stdio server initialization
  - [x] Subtask: Write test for HTTP server initialization
  - [x] Subtask: Verify FastMCP tool registration
- [x] Task: Local execution happy path test
  - [x] Subtask: Write test for basic code execution
  - [x] Subtask: Write test for stdout capture
  - [x] Subtask: Write test for stderr capture
- [x] Task: Artifact capture tests
  - [x] Subtask: Write test for matplotlib plot capture
  - [x] Subtask: Write test for PIL image capture
  - [x] Subtask: Write test for artifact categorization
- [x] Task: Security filter behavior tests
  - [x] Subtask: Write test for dangerous command blocking
  - [x] Subtask: Write test for directory access restrictions
  - [x] Subtask: Write test for resource limit enforcement
- [x] Task: Regression tests for execution context
  - [x] Subtask: Write test for session state persistence (covered in test_local_execution.py)
  - [x] Subtask: Write test for globals_dict serialization (covered in test_local_execution.py)
  - [x] Subtask: Write test for execution history storage (covered in test_local_execution.py)
- [x] Task: Maestro - Phase Verification and Checkpoint 'Test Infrastructure' (Protocol in workflow.md) [checkpoint: fa0ebfd]

---

## Phase 4: Core Services Extraction

### Goal
Consolidate duplicate execution context and shared behavior into core

- [x] Task: Extract shared execution context to core
  - [x] Subtask: Write failing tests for unified ExecutionContext interface
  - [x] Subtask: Create `src/sandbox/core/execution_services.py`
  - [x] Subtask: Move duplicate logic from both MCP servers
  - [x] Subtask: Update servers to use core services
- [x] Task: Extract shared artifact services to core
  - [x] Subtask: Write failing tests for artifact service module
  - [x] Subtask: Create `src/sandbox/core/artifact_services.py`
  - [x] Subtask: Move artifact capture logic from servers
  - [x] Subtask: Update servers to use core artifact services
- [x] Task: Extract monkey-patching to core utilities
  - [x] Subtask: Write failing tests for patching utilities
  - [x] Subtask: Create `src/sandbox/core/patching.py`
  - [x] Subtask: Move matplotlib/PIL patching from servers
- [~] Task: Fix SDK coupling to server implementation
  - [ ] Subtask: Write failing tests for SDK independence from server
  - [ ] Subtask: Remove ExecutionContext import from local_sandbox.py
  - [ ] Subtask: Use core services instead
- [ ] Task: Maestro - Phase Verification and Checkpoint 'Core Services Extraction' (Protocol in workflow.md)

---

## Phase 5: Server Refactoring

### Goal
Split oversized stdio server into focused modules

- [ ] Task: Split execution/session service module
  - [ ] Subtask: Write tests for session service module
  - [ ] Subtask: Create `src/sandbox/server/session_service.py`
  - [ ] Subtask: Move session logic from stdio server
  - [ ] Subtask: Verify <500 lines per module
- [ ] Task: Split artifact service module
  - [ ] Subtask: Write tests for server artifact service
  - [ ] Subtask: Create `src/sandbox/server/artifact_service.py`
  - [ ] Subtask: Move artifact logic from stdio server
- [ ] Task: Split web export service module
  - [ ] Subtask: Write tests for web export service
  - [ ] Subtask: Create `src/sandbox/server/web_export_service.py`
  - [ ] Subtask: Move Flask/Streamlit logic from stdio server
- [ ] Task: Split MCP tool registration module
  - [ ] Subtask: Write tests for tool registration
  - [ ] Subtask: Create `src/sandbox/server/tool_registry.py`
  - [ ] Subtask: Move FastMCP tool definitions
- [ ] Task: Split REPL UX/help text module
  - [ ] Subtask: Write tests for REPL helpers
  - [ ] Subtask: Create `src/sandbox/server/repl_helpers.py`
  - [ ] Subtask: Move REPL and magic command logic
- [ ] Task: Refactor stdio server main file
  - [ ] Subtask: Write tests for refactored stdio server
  - [ ] Subtask: Reduce main file to imports and wiring only
  - [ ] Subtask: Verify <500 lines for main file
- [ ] Task: Maestro - Phase Verification and Checkpoint 'Server Refactoring' (Protocol in workflow.md)

---

## Phase 6: Import Architecture Cleanup

### Goal
Remove eager imports and reduce coupling

- [ ] Task: Refactor package __init__.py files
  - [ ] Subtask: Write tests for lazy import behavior
  - [ ] Subtask: Remove server module imports from `src/sandbox/__init__.py`
  - [ ] Subtask: Remove eager imports from `src/sandbox/sdk/__init__.py`
  - [ ] Subtask: Export only stable primitives
- [ ] Task: Implement lazy imports for optional features
  - [ ] Subtask: Write tests for optional feature loading
  - [ ] Subtask: Create lazy import helpers
  - [ ] Subtask: Apply to remote sandbox, node sandbox
  - [ ] Subtask: Apply to web app features
- [ ] Task: Verify import performance
  - [ ] Subtask: Benchmark package import time
  - [ ] Subtask: Verify memory usage on import
  - [ ] Subtask: Document before/after metrics
- [ ] Task: Maestro - Phase Verification and Checkpoint 'Import Architecture Cleanup' (Protocol in workflow.md)

---

## Phase 7: Security & Documentation Alignment

### Goal
Align security claims with implementation and fix pickle concerns

- [ ] Task: Document security positioning accurately
  - [ ] Subtask: Update docs to reflect "guarded execution" not "strong isolation"
  - [ ] Subtask: Remove/qualify "no internet access" claims
  - [ ] Subtask: Document current limitations of filtering
- [ ] Task: Address pickle security in persistence
  - [ ] Subtask: Write tests for JSON-only persistence
  - [ ] Subtask: Prefer JSON serialization over pickle
  - [ ] Subtask: Document trust boundary if pickle remains
- [ ] Task: Update FAQ docs for accuracy
  - [ ] Subtask: Fix environment path documentation
  - [ ] Subtask: Update feature descriptions to match actual capabilities
  - [ ] Subtask: Add version/Python support consistency checks
- [ ] Task: Maestro - Phase Verification and Checkpoint 'Security & Documentation Alignment' (Protocol in workflow.md)

---

## Phase 8: CI/CD Infrastructure

### Goal
Add automated quality gates

- [ ] Task: Add compileall check to CI
  - [ ] Subtask: Create CI config with compileall step
  - [ ] Subtask: Verify no syntax errors in src/
- [ ] Task: Add package import smoke test to CI
  - [ ] Subtask: Add import smoke test to CI pipeline
  - [ ] Subtask: Verify clean environment import works
- [ ] Task: Add pytest to CI
  - [ ] Subtask: Configure pytest in CI
  - [ ] Subtask: Add coverage reporting
  - [ ] Subtask: Fail build on coverage drop
- [ ] Task: Add docs consistency checks
  - [ ] Subtask: Create script to check version consistency
  - [ ] Subtask: Create script to check Python version consistency
  - [ ] Subtask: Add checks to CI pipeline
- [ ] Task: Add golden path end-to-end test
  - [ ] Subtask: Write E2E test for execution + artifacts
  - [ ] Subtask: Add E2E test to CI
- [ ] Task: Maestro - Phase Verification and Checkpoint 'CI/CD Infrastructure' (Protocol in workflow.md)

---

## Phase 9: Final Verification & Documentation

### Goal
Ensure all acceptance criteria met and document improvements

- [ ] Task: Verify all acceptance criteria
  - [ ] Subtask: Confirm `import sandbox` succeeds
  - [ ] Subtask: Confirm pytest collects 15+ tests
  - [ ] Subtask: Confirm compileall passes
  - [ ] Subtask: Confirm version consistency
  - [ ] Subtask: Confirm stdio server <500 lines/module
  - [ ] Subtask: Confirm single ExecutionContext in core
- [ ] Task: Update CHANGELOG with remediation summary
  - [ ] Subtask: Document all fixes and improvements
  - [ ] Subtask: Add upgrade notes for users
- [ ] Task: Create before/after metrics report
  - [ ] Subtask: Document startup time improvement
  - [ ] Subtask: Document memory usage improvement
  - [ ] Subtask: Document test coverage growth
- [ ] Task: Final Tzar of Excellence review
  - [ ] Subtask: Conduct comprehensive review of all changes
  - [ ] Subtask: Address any remaining issues
  - [ ] Subtask: Verify production readiness
- [ ] Task: Maestro - Phase Verification and Checkpoint 'Final Verification & Documentation' (Protocol in workflow.md)
