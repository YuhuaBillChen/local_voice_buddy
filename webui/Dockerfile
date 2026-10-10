# Open WebUI with the voice fixes in patches/ applied to its built files. Each patch checks that the code
# it changes looks exactly as expected and fails the build otherwise, so the base image stays pinned.
FROM ghcr.io/open-webui/open-webui:v0.11.4@sha256:9591b13f13843c7721c2b8eaf7382846c81b3ffe126526d1888d1fed50c6a33f
COPY patches /tmp/patches
# call_trace defines the __ll() hook call_audio uses; frontend_release must run last (it versions the others)
RUN set -e; for p in tts_split tts_playback call_latency call_trace call_audio voice_prompt builtin_tools frontend_release; do \
        python /tmp/patches/patch_openwebui_$p.py; \
    done; rm -rf /tmp/patches
