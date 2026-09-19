FROM quay.io/hummingbird/python:latest-fips-builder AS builder
USER 0
RUN dnf install -y --setopt=install_weak_deps=False systemd && dnf clean all
WORKDIR /app
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
# Stage journalctl and its shared libraries for the runtime image, preserving
# paths — journalctl finds libsystemd-shared via /usr/lib64/systemd, so a flat
# copy into /usr/lib64 would not resolve. No awk in this base image.
RUN mkdir -p /staging && \
    cp -L --parents /usr/bin/journalctl /staging/ && \
    ldd /usr/bin/journalctl | sed -n 's|.*=> \(/[^ ]*\).*|\1|p' | sort -u | \
    xargs -I{} cp -L --parents {} /staging/

FROM quay.io/hummingbird/python:latest-fips

LABEL name="mcp-systemd-crunchtools" \
      version="0.1.0" \
      summary="MCP server for systemd unit management via D-Bus" \
      maintainer="crunchtools.com" \
      org.opencontainers.image.source="https://github.com/crunchtools/mcp-systemd" \
      org.opencontainers.image.description="MCP server for systemd unit management" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"

COPY --from=builder /app/venv /app/venv
COPY --from=builder /staging/usr/ /usr/
ENV PATH="/app/venv/bin:$PATH"

EXPOSE 8022
ENTRYPOINT ["python", "-m", "mcp_systemd_crunchtools"]
