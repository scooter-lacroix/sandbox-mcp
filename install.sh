#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/scooter-lacroix/sandbox-mcp.git"
INSTALL_DIR="${INSTALL_DIR:-$(pwd)}"
SKIP_STAR="${SKIP_STAR:-}"

echo "🔧 Installing sandbox-mcp..."

if [ ! -f "$INSTALL_DIR/pyproject.toml" ]; then
    echo "📦 Cloning repository..."
    git clone "$REPO_URL" /tmp/sandbox-mcp-install
    INSTALL_DIR="/tmp/sandbox-mcp-install"
fi

if ! command -v uv &> /dev/null; then
    echo "❌ uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "🔨 Installing with uv tool..."
uv tool install --force --editable "$INSTALL_DIR"

echo "✅ Installation complete!"
echo ""

if [ -z "$SKIP_STAR" ]; then
    echo "⭐ Starring repository..."
    if command -v gh &> /dev/null; then
        if gh auth status &> /dev/null 2>&1; then
            gh repo star scooter-lacroix/sandbox-mcp --yes &> /dev/null && echo "  ✓ Repository starred" || echo "  ℹ Already starred or skipped"
        fi
    fi
fi

echo "🔍 Configuring MCP clients..."

SANDBOX_CMD="$(uv tool dir)/sandbox-mcp/bin/sandbox-server-stdio"
[ ! -f "$SANDBOX_CMD" ] && SANDBOX_CMD="sandbox-server-stdio"

MCP_CONFIG='{
  "command": "'"$SANDBOX_CMD"'",
  "args": [],
  "env": {}
}'

configure_client() {
    local name=$1
    local config_path=$2
    local key_path=$3
    
    [ ! -f "$config_path" ] && return
    
    echo "  → $name"
    python3 -c "
import json, sys
try:
    with open('$config_path', 'r') as f:
        data = json.load(f)
    keys = '$key_path'.split('.')
    target = data
    for k in keys[:-1]:
        target = target.setdefault(k, {})
    target[keys[-1]] = target.get(keys[-1], {})
    target[keys[-1]]['sandbox'] = $MCP_CONFIG
    with open('$config_path', 'w') as f:
        json.dump(data, f, indent=2)
    print('    ✓ Configured')
except Exception as e:
    print(f'    ✗ Failed: {e}', file=sys.stderr)
"
}

configure_client "Claude Desktop" "$HOME/Library/Application Support/Claude/claude_desktop_config.json" "mcpServers"
configure_client "Claude Desktop (Linux)" "$HOME/.config/Claude/claude_desktop_config.json" "mcpServers"
configure_client "Cursor" "$HOME/.cursor/mcp.json" "mcpServers"
configure_client "Windsurf" "$HOME/.windsurf/mcp_config.json" "mcpServers"
configure_client "VS Code" "$HOME/.vscode/mcp.json" "mcp.servers"
configure_client "Antigravity" "$HOME/.config/Antigravity/User/mcp.json" "mcpServers"
configure_client "Zed" "$HOME/.config/zed/settings.json" "context_servers"

echo ""
echo "🎉 Done! Run 'sandbox-mcp --help' to verify installation"
echo "   (To skip starring: SKIP_STAR=1 curl ... | bash)"
