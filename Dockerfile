# recompute-kit MCP server — containerized, mirrors the repo.
# Bundles the verbs' toolchain (git, gh, foundry/forge, poppler) so the container is a
# self-contained recompute tool, deployable next to other NAS services.
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# git + curl + poppler (pdftotext) + the GitHub CLI (gh)
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates bash gnupg poppler-utils \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Foundry (forge) — the recompute_repo verb's default test runner
RUN curl -L https://foundry.paradigm.xyz | bash \
    && /root/.foundry/bin/foundryup
ENV PATH="/root/.foundry/bin:${PATH}"

# Bun — runtime for stdio conformance adapters (e.g. the chronicle continuity gate)
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:${PATH}"

# MCP SDK + OpenTimestamps client (for the 8263/precedence recipe)
RUN pip install --no-cache-dir mcp opentimestamps-client pycryptodome

WORKDIR /app
COPY bin/ ./bin/
COPY mcp/ ./mcp/
COPY conformance/ ./conformance/
RUN chmod +x bin/*

EXPOSE 7079
# server.py binds 0.0.0.0:7079 (streamable-HTTP) and pins PATH to find forge/gh/pdftotext
CMD ["python", "mcp/server.py"]
