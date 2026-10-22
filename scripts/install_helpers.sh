# shellcheck shell=bash
# Shared by the installer and its hardware-free regression tests.
model_verified() {
  local file=$1 size=$2 digest=$3
  [[ -f "$file" && "$(stat -Lc %s "$file")" == "$size" ]] || return 1
  printf '%s  %s\n' "$digest" "$file" | sha256sum -c --quiet -
}

# Prebuilt speech images by digest, since a registry tag can be moved. They are pulled by digest and
# given the tag compose.yml names; when that fails they are built from the npu-cosyvoice tag instead.
SPEECH_IMAGES=(
  "setup ghcr.io/yuhuabillchen/npu-cosyvoice-voice:0.1.2@sha256:94949f675543f4261656c46912580311dc2c5aa83dec24fa906393894c90614a"
  "whisper ghcr.io/yuhuabillchen/npu-cosyvoice-whisper:0.1.2@sha256:b27218b6193a8a4b95bac7d5acba4410ae7053074053ea52b8b8715fc1443f7f"
)

prepare_images() {
  # Pull the pinned upstream engine; a failure must not silently select another build.
  docker compose pull llm || return 1
  local entry service ref name pinned
  for entry in "${SPEECH_IMAGES[@]}"; do
    read -r service ref <<<"$entry"
    name=${ref%@*}
    pinned=${name%:*}@${ref#*@}
    if [[ -n "${NPU_COSYVOICE_SRC:-}" ]] || ! { docker pull "$pinned" && docker tag "$pinned" "$name"; }; then
      docker compose --profile setup build "$service" || return 1
    fi
  done
  # This checkout owns the UI patches. Always rebuild so git pull updates the running code.
  docker compose build webui
}

services_ready() {
  docker compose exec -T voice python -c "import json,sys,urllib.request; sys.exit(json.load(urllib.request.urlopen('http://localhost:8000/health', timeout=5))['status'] != 'ok')" >/dev/null 2>&1 &&
  docker compose exec -T whisper /opt/npu-whisper/refenv/bin/python -c "import json,sys,urllib.request; sys.exit(json.load(urllib.request.urlopen('http://localhost:8090/health', timeout=5))['status'] != 'ok')" >/dev/null 2>&1 &&
  docker compose exec -T webui curl --max-time 5 -fsS http://llm:8080/health >/dev/null 2>&1 &&
  docker compose exec -T webui curl --max-time 5 -fsS http://localhost:8080/health >/dev/null 2>&1
}

published_webui_port() {
  local mapping port
  mapping=$(docker compose port webui 8080) || return 1
  port=${mapping##*:}
  [[ "$port" =~ ^[0-9]+$ && "$port" -gt 0 && "$port" -le 65535 ]] || return 1
  printf '%s\n' "$port"
}
