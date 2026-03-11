# Marketplace Presentation and Deployment

This document is the directory-facing companion to the runtime metadata exposed by Sandbox MCP.

## Positioning

Sandbox MCP is a general-purpose Python execution server for MCP clients. It is intentionally broad:

- Run short Python snippets with persistent execution state.
- Generate artifacts such as plots, images, CSV/JSON files, and Manim renders.
- Execute guarded shell commands for lightweight workflows.
- Launch and export small Flask or Streamlit demos.
- Provide MCP-native prompts and resources so an LLM can discover templates, skills, and capability summaries without reading the whole repository.

It should be presented as a broadly useful coding, prototyping, and teaching sandbox, not as a marketplace-specific one-off integration.

## What to Surface in Listings

For MCPHub, MCPMarket, LobeHub, and similar catalogs, highlight:

- Succinct summary: general-purpose Python sandbox with artifacts, Manim, shell access, and web app workflows.
- Strong fit: demos, tutorials, prototyping, data visualization, classroom visuals, quick reproducible examples.
- Safety note: guarded execution environment, not a hardened isolation boundary.
- Discovery support: exposes tools, prompts, resources, a skill catalog, and interactive templates.

The machine-readable counterpart lives in [`marketplace-profile.json`](./marketplace-profile.json).

The registry manifest lives at [`../server.json`](../server.json). It is prepared for a PyPI-backed listing using the reverse-DNS name `io.github.scooter-lacroix/sandbox-mcp`.

## Skills and Interactive Templates

Sandbox MCP now exposes the following higher-level LLM interfaces:

- `manim_storyboard_skill`
  Produces a storyboard, complete Manim code, and a suggested Sandbox MCP execution flow.
- `manim_scene_template`
  Produces a focused Manim scene from a concept, target duration, and quality preset.
- `sandbox_example_template`
  Produces a runnable example that creates a plot, image, table, or file artifact.
- `sandbox_web_app_template`
  Produces a small Flask or Streamlit demo suitable for launching or exporting.

These are user-activated MCP prompts, not hidden system behavior.

## Hosted Deployment Guidance

For local desktop assistants, prefer stdio:

```bash
uv run sandbox-server-stdio
```

For remote hosting and directory listings that prefer URL-based servers, use the HTTP transport:

```bash
python -m sandbox.mcp_sandbox_server

# Hosted example
SANDBOX_MCP_HOST=0.0.0.0 SANDBOX_MCP_PORT=8765 python -m sandbox.mcp_sandbox_server
```

Recommended hosted deployment posture:

1. Put the HTTP server behind TLS termination.
2. Require authentication before exposing it beyond a trusted network.
3. Add an outer isolation boundary such as a container or VM if untrusted code may run.
4. Use reverse-proxy controls and network policy to limit blast radius.
5. Document the remote URL, auth model, and any rate or execution limits in the marketplace listing.

## Suggested Listing Assets

- Primary README: [`../README.md`](../README.md)
- Machine-readable profile: [`./marketplace-profile.json`](./marketplace-profile.json)
- Registry manifest: [`../server.json`](../server.json)
- Installation examples: [`../MCP_CONFIGURATION.md`](../MCP_CONFIGURATION.md)
- Capability source of truth in code: [`../src/sandbox/server/catalog.py`](../src/sandbox/server/catalog.py)

## Future Registry Work

If you later publish Sandbox MCP to a registry that requires a strict manifest, keep the following in sync:

- package identifier or hosted URL
- server summary and long description
- transport details
- auth and remote deployment notes
- tools, prompts, resources, and skills
- README ownership marker and install instructions
