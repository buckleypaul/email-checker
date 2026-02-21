class EmailChecker < Formula
  desc "macOS menu bar app that surfaces important emails via Claude + Gmail MCP"
  homepage "https://github.com/buckleypaul/email-checker"
  url "https://github.com/buckleypaul/email-checker/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "PLACEHOLDER"
  license "MIT"

  depends_on :macos
  depends_on "python@3.13"

  def install
    python = Formula["python@3.13"].opt_bin/"python3.13"
    venv = libexec/"venv"
    system python, "-m", "venv", venv
    system "#{venv}/bin/pip", "install", "--quiet", "rumps"
    libexec.install "app.py", "prompt.md", "mcp_config.json.example"
  end

  service do
    run [opt_libexec/"venv/bin/python3", opt_libexec/"app.py"]
    keep_alive true
    log_path var/"log/email-checker.log"
    error_log_path var/"log/email-checker.log"
    environment_variables PATH: "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
  end

  def caveats
    <<~EOS
      Before starting, create your MCP config at:
        ~/.config/email-checker/mcp_config.json

      Copy the example and edit the path to your gmail-mcp server:
        cp #{opt_libexec}/../mcp_config.json.example ~/.config/email-checker/mcp_config.json

      Then start the app:
        brew services start #{name}

      To customise which emails are surfaced, edit:
        ~/.config/email-checker/prompt.md
      (a default is used on first run if this file doesn't exist)

      Logs are written to:
        ~/.config/email-checker/email-checker.log
    EOS
  end

  test do
    system opt_libexec/"venv/bin/python3", "-c", "import rumps; print('OK')"
  end
end
