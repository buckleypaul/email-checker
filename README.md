# email-checker

A macOS menu bar app that periodically asks Claude to scan your Gmail and surface emails that need a response.

## How it works

Every 30 minutes (synced to :25 and :55) the app runs Claude with the `gmail` MCP tool, which fetches new emails via the [gmail-mcp](https://github.com/buckleypaul/gmail-mcp) server. Claude analyses them against your prompt and returns a JSON list of emails worth responding to. These appear in the menu bar and trigger macOS notifications.

The filtering prompt is a plain markdown file you can edit at any time — no code changes required.

## Prerequisites

- [Claude Code](https://claude.ai/code) CLI installed and authenticated (`claude --version`)
- [gmail-mcp](https://github.com/buckleypaul/gmail-mcp) server set up and authorised
- Node.js (for the gmail-mcp server)

## Install

```sh
brew tap buckleypaul/email-checker https://github.com/buckleypaul/email-checker
brew install email-checker
```

### 1. Configure the Gmail MCP server

```sh
mkdir -p ~/.config/email-checker
cp $(brew --prefix)/opt/email-checker/libexec/mcp_config.json.example \
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

Without this, macOS will prompt for folder permissions repeatedly and checks may time out.

### 3. Start

```sh
brew services start email-checker
```

Look for the **✉** icon in your menu bar.

## Usage

### Menu bar icon

| Icon | Meaning |
|------|---------|
| `✉` | App is running, no important emails |
| `✉ 3` | 3 important emails found |
| `✉ …` | Check in progress |

### Menu items

| Item | Action |
|------|--------|
| `3 important emails` | Header — shows count |
| Email entries | Click to open that email in Gmail |
| **Run Now** | Trigger an immediate check (title briefly shows `✉ …`) |
| `Last checked: 5m ago` | Time of last successful check |
| **Clear** | Dismiss the current list and reset the count |
| **Quit** | Exit the app |

### Notifications

A macOS notification fires for each newly found important email, showing the subject, sender, and why Claude flagged it. Click the notification to do nothing — open it from the menu instead.

### Checks run automatically

Checks fire at :25 and :55 past each hour. After a **Run Now** the next auto-check is rescheduled 30 minutes later, so manual checks don't cause a double-up.

### Surviving sleep and restarts

The app is managed by `launchd` (`KeepAlive: true`), so it restarts automatically after sleep, logout, or a crash. The list of important emails is persisted to `~/.config/email-checker/state.json` and restored on startup.

## Customise the prompt

The prompt controls which emails Claude surfaces. Edit it any time — changes take effect on the next check.

```sh
open ~/.config/email-checker/prompt.md
```

If this file doesn't exist, the default bundled with the app is used. To start customising, copy the default first:

```sh
cp $(brew --prefix)/opt/email-checker/libexec/prompt.md \
   ~/.config/email-checker/prompt.md
```

Example tweaks:
- Add a sender's name to always include their emails
- Add your company domain to always include internal mail
- Exclude specific mailing lists or senders

## Logs

```sh
tail -f ~/.config/email-checker/email-checker.log
```

## Uninstall

```sh
brew services stop email-checker
brew uninstall email-checker
brew untap buckleypaul/email-checker
rm -rf ~/.config/email-checker   # optional: remove config and state
```
