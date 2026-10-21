# Open WebUI with the voice fixes in patches/ applied to its built files. Each patch checks that the code
# it changes looks exactly as expected and fails the build otherwise, so the base image stays pinned.
FROM node:24-bookworm-slim AS openui
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git init && git remote add origin https://github.com/thesysdev/open-intelligent-ui && \
    git fetch --depth 1 origin 03213439358bf3408ad61a46ec9e3230c5572e48 && git checkout --detach FETCH_HEAD
RUN npm ci --no-audit --no-fund
COPY openui/entry.tsx src/buddy/entry.tsx
COPY openui/host.js src/buddy/host.js
COPY openui/build.mjs ./buddy-build.mjs
RUN node buddy-build.mjs src/buddy/entry.tsx /out

FROM ghcr.io/open-webui/open-webui:v0.12.3@sha256:a537bbe1e6b428820f52ed4a029d7fff97062e24d5cf32c365fba36fd0542def
COPY --from=openui /out /app/backend/open_webui/static/buddy-openui
COPY openui/buddy_openui.py /app/backend/open_webui/tools/buddy_openui.py
COPY patches /tmp/patches
# frontend_release must run last (it versions the others)
RUN set -e; for p in tts_split tts_playback call_latency call_audio voice_prompt builtin_tools openui frontend_release; do \
        python /tmp/patches/patch_openwebui_$p.py; \
    done; rm -rf /tmp/patches
