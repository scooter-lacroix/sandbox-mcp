# Tzar of Excellence Review – Phase 5 (partial) and Phases 1–4

Date: 2026-03-07
Scope: Completed phases 1–4 and completed Phase 5 tasks (session_service.py, artifact_service.py). Remaining Phase 5 tasks are excluded.

## Verdict
FAIL – critical issues identified.

## Critical Issues
1. ExecutionContext ignores provided `project_root`; explicit overrides leave `project_root` unset, causing runtime errors. [src/sandbox/core/execution_services.py](../src/sandbox/core/execution_services.py#L23-L45)
2. Session `created_at` uses random UUIDs instead of timestamps, breaking ordering, expiry, and auditability. [src/sandbox/server/session_service.py](../src/sandbox/server/session_service.py#L41-L47)
3. `PLOT_EXTENSIONS` is unused; plots are misclassified as `other`, breaking downstream routing. [src/sandbox/core/artifact_services.py](../src/sandbox/core/artifact_services.py#L22-L54)
4. `create_artifacts_dir` concatenates unsanitized `session_id`, allowing path traversal outside `sandbox_area`. [src/sandbox/core/artifact_services.py](../src/sandbox/core/artifact_services.py#L142-L160)
5. Session store is in‑memory only with no locking/expiration; state is lost on restart and races can corrupt sessions. [src/sandbox/server/session_service.py](../src/sandbox/server/session_service.py#L24-L166)

## Improvements Needed
- Honor explicit `project_root`, create sandbox area with parents, and normalize installed vs. editable layouts. [execution_services.py](../src/sandbox/core/execution_services.py#L31-L45)
- Record real UTC timestamps, last_seen, enforce idle/absolute timeouts, and validate status transitions. [session_service.py](../src/sandbox/server/session_service.py#L41-L117)
- Artifact scanning: skip symlinks, add depth/size limits, and MIME sniffing to prevent extension spoofing. [artifact_services.py](../src/sandbox/core/artifact_services.py#L76-L190)
- Normalize artifact metadata (ISO timestamps, checksums) and sanitize category filters; avoid following symlinks. [server/artifact_service.py](../src/sandbox/server/artifact_service.py#L40-L131)

## Optimization Opportunities
- Cache resolved venv site-packages and avoid mutating `sys.executable` per request; reduce sys.path rebuild overhead. [execution_services.py](../src/sandbox/core/execution_services.py#L96-L139)
- Avoid duplicate `stat()` calls during scans; streamline directory walks. [artifact_services.py](../src/sandbox/core/artifact_services.py#L91-L101)

## Edge Cases Not Handled
- Session cleanup lacks per-session teardown hooks (e.g., running web servers), leading to leaks. [session_service.py](../src/sandbox/server/session_service.py#L155-L165)
- Artifact cleanup deletes based on day granularity and ignores in-use files; should use precise age checks with locking. [artifact_services.py](../src/sandbox/core/artifact_services.py#L162-L190)
- Manim detection is substring-based and may mislabel unrelated content; needs explicit scoping. [server/artifact_service.py](../src/sandbox/server/artifact_service.py#L47-L63)

## Security Concerns
- Path traversal via `session_id` in artifact directories (high severity). [artifact_services.py](../src/sandbox/core/artifact_services.py#L142-L160)
- Unvalidated `update_session` allows arbitrary metadata injection. [session_service.py](../src/sandbox/server/session_service.py#L102-L117)
- Artifact listing follows symlinks, enabling host disclosure. [server/artifact_service.py](../src/sandbox/server/artifact_service.py#L72-L105)

## Performance Issues
- Unbounded recursive walks in both artifact services can stall large trees; need limits and pagination. [artifact_services.py](../src/sandbox/core/artifact_services.py#L76-L108) and [server/artifact_service.py](../src/sandbox/server/artifact_service.py#L72-L105)

## Next Steps (must fix before continuing Phase 5)
1) Fix project_root handling and sandbox_area creation in ExecutionContext.
2) Replace UUID timestamps with real UTC datetimes; add session expiry and locking.
3) Wire `PLOT_EXTENSIONS` into categorization and add path validation to create_artifacts_dir.
4) Add symlink/recursion limits and metadata normalization in both artifact services.
5) Introduce persistence or durable backing for session state with concurrency safety.

