# Renderer (Epic 7, reworked in E10-S1): draw.io desktop CLI + Mermaid CLI behind one small HTTP wrapper.
#
# Debian rather than the Alpine-based minlag/mermaid-cli image, because draw.io desktop ships as a .deb.
# Every version is pinned; bump them deliberately (the .deb is checksum-verified).
FROM node:22.20.0-bookworm-slim

ARG DRAWIO_VERSION=32.4.1
ARG DRAWIO_SHA256_AMD64=f4455b3bba3d3b539c3cd069218fc64f0462b1b01610fe8d11acc3ca8566f32b
ARG DRAWIO_SHA256_ARM64=724d3f18c18dc42489760c7811508581803824880d1e98e035e3a8dd3b5c7bba
ARG MERMAID_CLI_VERSION=11.17.1
ARG PUPPETEER_VERSION=24.43.1

ENV DEBIAN_FRONTEND=noninteractive \
    PUPPETEER_SKIP_DOWNLOAD=1 \
    DISPLAY=:99 \
    ELECTRON_DISABLE_SECURITY_WARNINGS=1

# System packages in their own layer, so a failed .deb download does not re-fetch Chromium.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl xvfb xauth chromium \
      fonts-liberation fonts-dejavu-core fonts-noto-core \
 && rm -rf /var/lib/apt/lists/*

RUN arch="$(dpkg --print-architecture)" \
 && case "$arch" in \
      amd64) sum="$DRAWIO_SHA256_AMD64" ;; \
      arm64) sum="$DRAWIO_SHA256_ARM64" ;; \
      *) echo "unsupported architecture: $arch" >&2; exit 1 ;; \
    esac \
 && curl -fsSL --http1.1 --retry 5 --retry-all-errors --retry-delay 3 -o /tmp/drawio.deb \
      "https://github.com/jgraph/drawio-desktop/releases/download/v${DRAWIO_VERSION}/drawio-${arch}-${DRAWIO_VERSION}.deb" \
 && echo "${sum}  /tmp/drawio.deb" | sha256sum -c - \
 && apt-get update \
 && apt-get install -y --no-install-recommends /tmp/drawio.deb \
 && rm -f /tmp/drawio.deb \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g --omit=dev "@mermaid-js/mermaid-cli@${MERMAID_CLI_VERSION}" "puppeteer@${PUPPETEER_VERSION}" \
 && npm cache clean --force

RUN useradd --create-home --uid 10001 renderer
WORKDIR /app
COPY puppeteer-config.json /puppeteer-config.json
COPY entrypoint.sh /app/entrypoint.sh
COPY server.js /app/server.js
RUN chmod +x /app/entrypoint.sh

USER renderer
ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
