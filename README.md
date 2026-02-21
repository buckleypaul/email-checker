# email-checker

A macOS menu bar app that periodically asks Claude to scan your Gmail and surface emails that need a response.

## How it works

Every 30 minutes (synced to :25 and :55) the app runs Claude with the `gmail` MCP tool, which fetches new emails via the [gmail-mcp](https://github.com/buckleypaul/gmail-mcp) server. Claude analyses them against your prompt and returns a JSON list of emails worth responding to. These appear in the menu bar and trigger macOS notifications.

The filtering prompt is a plain markdown file you can edit at any time — no code changes required.

## Install

```sh
brew tap buckleypaul/email-checker https://github.com/buckleypaul/email-checker
brew install email-checker
```

### 1. Configure the Gmail MCP server

```sh
mkdir -p ~/.config/email-checker
cp $(brew --prefix)/opt/email-checker/libexec/../mcp_config.json.example \
   ~/.config/email-checker/mcp_config.json
```

Edit `~/.config/email-checker/mcp_config.json` and point `args` at your `gmail-mcp/index.js`:

```json
{
  "mcpServers": {
    "gmail": {
      "command": "node",
      "args": ["/path/to/gmail-mcp/index.js"]
    }
  }
}
```

### 2. Grant Full Disk Access

Because the app runs as a login item and spawns `claude` and `node` as subprocesses, macOS requires Full Disk Access for the Python binary:

**System Settings → Privacy & Security → Full Disk Access → + → add:**
```
$(brew --prefix)/opt/email-checker/libexec/venv/bin/python3
```

### 3. Start

```sh
brew services start email-checker
```

Look for the **✉** icon in your menu bar.

## Customise the prompt

```sh
# Edit the filtering rules
open ~/.config/email-checker/prompt.md
```

Changes take effect on the next check (or click **Run Now**).

## Menu

| Item | Action |
|------|--------|
| `✉ 3` | Count of important emails in the list |
| Email entries | Click to open in Gmail |
| **Run Now** | Trigger an immediate check |
| `Last checked: 5m ago` | Time of last successful check |
| **Clear** | Dismiss current list |
| **Quit** | Exit the app |

## Logs

```sh
tail -f ~/.config/email-checker/email-checker.log
```

## Uninstall

```sh
brew services stop email-checker
brew uninstall email-checker
brew untap buckleypaul/email-checker
```
