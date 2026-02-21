# Email Checker — Project Notes

## Releasing a new version

1. Make changes and commit
2. Bump the version in `Formula/email-checker.rb` (url line and sha256)
3. Tag and push:
   ```sh
   git tag vX.Y.Z && git push origin vX.Y.Z
   gh release create vX.Y.Z
   ```
4. Recompute sha256:
   ```sh
   curl -sL https://github.com/buckleypaul/email-checker/archive/refs/tags/vX.Y.Z.tar.gz | shasum -a 256
   ```
5. Update `sha256` in `Formula/email-checker.rb` and push

## Key paths

| What | Where |
|------|-------|
| User config (mcp_config.json, prompt.md, state.json, logs) | `~/.config/email-checker/` |
| Bundled default prompt | `app.py`'s directory (`prompt.md`) |
| Homebrew formula | `Formula/email-checker.rb` |

## Local dev

The app runs directly without Homebrew:
```sh
python3 -m venv venv && venv/bin/pip install rumps
cp mcp_config.json.example ~/.config/email-checker/mcp_config.json
# edit mcp_config.json with real path to gmail-mcp/index.js
venv/bin/python3 app.py
```

## Architecture

- `app.py` — `rumps`-based menu bar app; scheduling via `threading.Timer`, UI updates via `@rumps.timer(1)` on main thread
- Claude is invoked as a subprocess with `--output-format json` and `--mcp-config` pointing at the gmail MCP server
- `prompt.md` controls filtering criteria; user copy at `~/.config/email-checker/prompt.md` takes priority over the bundled default
- `mcp_config.json` must exist at `~/.config/email-checker/mcp_config.json` before the app will run checks
