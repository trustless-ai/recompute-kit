# recompute-kit MCP server — containerized, mirrors the repo.
# Bundles the verbs' toolchain (git, gh, foundry/forge, poppler) so the container is a
# self-contained recompute tool, deployable next to other NAS services.
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# git + curl + poppler (pdftotext) + the GitHub CLI (gh)
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates bash gnupg poppler-utils unzip \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Foundry (forge) — the recompute_repo verb's default test runner.
# Installed under /opt (world-readable) so the non-root runtime user can reach it.
ENV FOUNDRY_DIR=/opt/foundry
RUN curl -L https://foundry.paradigm.xyz | bash \
    && /opt/foundry/bin/foundryup
ENV PATH="/opt/foundry/bin:${PATH}"

# Bun — runtime for stdio conformance adapters (e.g. the chronicle continuity gate).
# Installed under /opt for the same reason.
ENV BUN_INSTALL=/opt/bun
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/opt/bun/bin:${PATH}"

# MCP SDK + OpenTimestamps client (for the 8263/precedence recipe). Pinned: unpinned mcp now
# resolves to 2.x, whose FastMCP->MCPServer rename breaks mcp/server.py at import.
RUN pip install --no-cache-dir mcp==1.30.0 opentimestamps-client==0.8.0 pycryptodome==4.5.0

WORKDIR /app
COPY bin/ ./bin/
COPY mcp/ ./mcp/
COPY conformance/ ./conformance/
RUN chmod +x bin/*

# Drop root: run the server as an unprivileged user (blast-radius hardening).
# The toolchains live under /opt (world-readable); /app is owned by this user.
RUN useradd --create-home --uid 10001 app \
    && chown -R app:app /app
USER app

EXPOSE 7079
# server.py binds 0.0.0.0:7079 (streamable-HTTP) and pins PATH to find forge/gh/pdftotext
CMD ["python", "mcp/server.py"]
