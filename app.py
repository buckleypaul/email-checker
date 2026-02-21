#!/usr/bin/env python3
"""Email Checker — macOS menu bar app that surfaces important emails via Claude + Gmail MCP."""

import json
import logging
import os
import re
import subprocess
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

import rumps

SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_DIR = Path.home() / ".config" / "email-checker"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = CONFIG_DIR / "state.json"
MCP_CONFIG = CONFIG_DIR / "mcp_config.json"
# User config takes priority; fall back to the copy bundled with the app
PROMPT_FILE = CONFIG_DIR / "prompt.md"
DEFAULT_PROMPT = SCRIPT_DIR / "prompt.md"
MAX_EMAILS = 10
MENU_DISPLAY_LIMIT = 5

# (key, label, timedelta) — "new" uses get_new_emails; others use search_emails
CHECK_PERIODS = [
    ("new", "Since last check", None),
    ("1h",  "Last hour",        timedelta(hours=1)),
    ("24h", "Last 24 hours",    timedelta(hours=24)),
    ("7d",  "Last 7 days",      timedelta(days=7)),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(CONFIG_DIR / "email-checker.log"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)


class EmailCheckerApp(rumps.App):
    def __init__(self):
        super().__init__("✉", quit_button=None)
        self.important_emails = []
        self.last_checked = None
        self.check_period = "new"
        self._check_timer = None
        self._is_checking = False
        self._pending_rebuild = False
        self._load_state()
        self._rebuild_menu()
        self._schedule_next_check()

    # ── State persistence ────────────────────────────────────────────────────

    def _load_state(self):
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                self.important_emails = data.get("important_emails", [])
                last = data.get("last_checked")
                self.last_checked = datetime.fromisoformat(last) if last else None
                self.check_period = data.get("check_period", "new")
                log.info("Loaded %d emails from state", len(self.important_emails))
            except Exception:
                log.exception("Failed to load state")

    def _save_state(self):
        try:
            STATE_FILE.write_text(
                json.dumps(
                    {
                        "important_emails": self.important_emails,
                        "last_checked": self.last_checked.isoformat() if self.last_checked else None,
                        "check_period": self.check_period,
                    },
                    indent=2,
                )
            )
        except Exception:
            log.exception("Failed to save state")

    # ── Scheduling ───────────────────────────────────────────────────────────

    def _schedule_next_check(self, delay_seconds=None):
        """Schedule the next check. If delay_seconds is None, sync to :25/:55."""
        if self._check_timer is not None:
            self._check_timer.cancel()

        if delay_seconds is None:
            now = datetime.now()
            minute = now.minute
            second = now.second
            if minute < 25:
                target_minute = 25
            elif minute < 55:
                target_minute = 55
            else:
                target_minute = 85  # next hour :25
            delay_seconds = (target_minute - minute) * 60 - second
            if delay_seconds <= 0:
                delay_seconds = 30 * 60

        log.info("Next check in %.0f seconds", delay_seconds)
        self._check_timer = threading.Timer(delay_seconds, self._timer_fired)
        self._check_timer.daemon = True
        self._check_timer.start()

    def _timer_fired(self):
        self.run_check()
        self._schedule_next_check(delay_seconds=30 * 60)

    # ── Claude invocation ────────────────────────────────────────────────────

    def run_check(self):
        """Run in a background thread; signals main thread to update UI when done."""
        log.info("Running email check")
        self._is_checking = True

        if not MCP_CONFIG.exists():
            log.error("mcp_config.json not found at %s — copy mcp_config.json.example", MCP_CONFIG)
            self._is_checking = False
            self._pending_rebuild = True
            return

        prompt_path = PROMPT_FILE if PROMPT_FILE.exists() else DEFAULT_PROMPT
        try:
            base_prompt = prompt_path.read_text()
        except Exception:
            log.exception("Could not read prompt.md")
            self._is_checking = False
            self._pending_rebuild = True
            return

        # Build period-aware prompt and tool selection
        period_entry = next(p for p in CHECK_PERIODS if p[0] == self.check_period)
        _, period_label, period_delta = period_entry

        if period_delta is None:
            allowed_tools = "mcp__gmail__get_new_emails"
            prompt = base_prompt
        else:
            allowed_tools = "mcp__gmail__search_emails"
            cutoff = datetime.now() - period_delta
            after_date = cutoff.strftime("%Y/%m/%d")
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M")
            prompt = (
                f"Use the search_emails tool with query 'after:{after_date}' to find emails. "
                f"Focus only on emails received since {cutoff_str} ({period_label}).\n\n"
                + base_prompt
            )
            log.info("Period check: %s (after %s)", period_label, cutoff_str)

        cmd = [
            "claude",
            "-p",
            "--mcp-config", str(MCP_CONFIG),
            "--allowedTools", allowed_tools,
            "--output-format", "json",
            "--dangerously-skip-permissions",
            prompt,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            log.error("Claude timed out")
            self._is_checking = False
            self._pending_rebuild = True
            return
        except Exception:
            log.exception("Failed to run Claude")
            self._is_checking = False
            self._pending_rebuild = True
            return

        if result.returncode != 0:
            log.error("Claude exited %d: %s", result.returncode, result.stderr[:500])
            self._is_checking = False
            self._pending_rebuild = True
            return

        emails = self._parse_claude_output(result.stdout)
        if emails is None:
            self._is_checking = False
            self._pending_rebuild = True
            return

        self.last_checked = datetime.now(tz=timezone.utc)
        self._notify_new_emails(emails)
        if self.check_period == "new":
            self.important_emails = (emails + self.important_emails)[:MAX_EMAILS]
        else:
            # Period-based check: replace the list entirely
            self.important_emails = emails[:MAX_EMAILS]
        self._save_state()
        log.info("Check complete — %d important email(s) returned", len(emails))
        self._is_checking = False
        self._pending_rebuild = True

    def _parse_claude_output(self, stdout):
        """Parse Claude's --output-format json wrapper and extract the email array."""
        try:
            outer = json.loads(stdout)
            text = outer.get("result", "")
        except json.JSONDecodeError:
            log.error("Could not parse Claude outer JSON: %s", stdout[:300])
            return None

        # Try direct parse first (result is already a JSON array)
        text = text.strip()
        try:
            emails = json.loads(text)
            if isinstance(emails, list):
                return emails
        except json.JSONDecodeError:
            pass

        # Fallback: extract JSON array with regex
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                emails = json.loads(match.group())
                if isinstance(emails, list):
                    log.warning("Used regex fallback to extract JSON array")
                    return emails
            except json.JSONDecodeError:
                pass

        log.error("No JSON array found in Claude result: %s", text[:300])
        return None

    # ── Notifications ────────────────────────────────────────────────────────

    def _notify_new_emails(self, new_emails):
        existing_ids = {e["id"] for e in self.important_emails}
        truly_new = [e for e in new_emails if e.get("id") not in existing_ids]
        for email in truly_new:
            rumps.notification(
                title=email.get("subject", "(no subject)"),
                subtitle=email.get("from", ""),
                message=email.get("reason", ""),
                sound=True,
            )

    # ── Menu ─────────────────────────────────────────────────────────────────

    def _rebuild_menu(self):
        count = len(self.important_emails)
        self.title = f"✉ {count}" if count > 0 else "✉"

        items = []

        # Header
        if count > 0:
            header = rumps.MenuItem(f"{count} important email{'s' if count != 1 else ''}")
        else:
            header = rumps.MenuItem("No new important emails")
        header.set_callback(None)
        items.append(header)
        items.append(rumps.separator)

        # Email entries (up to MENU_DISPLAY_LIMIT)
        for email in self.important_emails[:MENU_DISPLAY_LIMIT]:
            subject = email.get("subject", "(no subject)")[:40]
            sender = email.get("from", "")
            # Extract just the name part if in "Name <email>" format
            name_match = re.match(r"^([^<]+)", sender)
            sender_display = name_match.group(1).strip() if name_match else sender
            sender_display = sender_display[:20]
            label = f"{subject} · {sender_display}"
            item = rumps.MenuItem(label, callback=self._make_open_callback(email.get("id", "")))
            items.append(item)

        items.append(rumps.separator)

        # Run Now
        run_now = rumps.MenuItem("Run Now", callback=self._on_run_now)
        items.append(run_now)

        # Check period submenu
        period_menu = rumps.MenuItem("Check period")
        for key, label, _ in CHECK_PERIODS:
            prefix = "✓ " if key == self.check_period else "    "
            item = rumps.MenuItem(prefix + label, callback=self._make_period_callback(key))
            period_menu.add(item)
        items.append(period_menu)

        # Last checked
        last_checked_label = self._last_checked_label()
        last_item = rumps.MenuItem(last_checked_label)
        last_item.set_callback(None)
        items.append(last_item)

        items.append(rumps.separator)

        # Clear
        items.append(rumps.MenuItem("Clear", callback=self._on_clear))

        # Quit
        items.append(rumps.MenuItem("Quit", callback=self._on_quit))

        self.menu.clear()
        self.menu = items

    def _last_checked_label(self):
        if self.last_checked is None:
            return "Not checked yet"
        now = datetime.now(tz=timezone.utc)
        diff = now - self.last_checked
        minutes = int(diff.total_seconds() // 60)
        if minutes < 1:
            return "Last checked: just now"
        elif minutes == 1:
            return "Last checked: 1m ago"
        else:
            return f"Last checked: {minutes}m ago"

    def _make_period_callback(self, key):
        def callback(_):
            self.check_period = key
            self._save_state()
            self._pending_rebuild = True
        return callback

    def _make_open_callback(self, email_id):
        def callback(_):
            url = f"https://mail.google.com/mail/u/0/#inbox/{email_id}"
            webbrowser.open(url)
        return callback

    # ── Main-thread UI poll ──────────────────────────────────────────────────

    @rumps.timer(1)
    def _ui_tick(self, _):
        """Called every second on the main thread — safe to update Cocoa UI here."""
        if self._is_checking:
            self.title = "✉ …"
        elif self._pending_rebuild:
            self._pending_rebuild = False
            self._rebuild_menu()

    # ── Menu callbacks ───────────────────────────────────────────────────────

    def _on_run_now(self, _):
        self._schedule_next_check(delay_seconds=30 * 60)
        self.title = "✉ …"
        threading.Thread(target=self.run_check, daemon=True).start()

    def _on_clear(self, _):
        self.important_emails = []
        self._save_state()
        self._rebuild_menu()

    def _on_quit(self, _):
        self._save_state()
        if self._check_timer is not None:
            self._check_timer.cancel()
        rumps.quit_application()


if __name__ == "__main__":
    EmailCheckerApp().run()
