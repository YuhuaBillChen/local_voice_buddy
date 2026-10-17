# Open WebUI with the voice fixes in patches/ applied to its built files. Each patch checks that the code
# it changes looks exactly as expected and fails the build otherwise, so the base image stays pinned.
FROM ghcr.io/open-webui/open-webui:v0.12.3@sha256:a537bbe1e6b428820f52ed4a029d7fff97062e24d5cf32c365fba36fd0542def
COPY patches /tmp/patches
# frontend_release must run last (it versions the others)
RUN set -e; for p in tts_split tts_playback call_latency call_audio voice_prompt builtin_tools frontend_release; do \
        python /tmp/patches/patch_openwebui_$p.py; \
    done; rm -rf /tmp/patches
