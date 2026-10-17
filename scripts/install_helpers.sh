# shellcheck shell=bash
# Shared by the installer and its hardware-free regression tests.
model_verified() {
  local file=$1 size=$2 digest=$3
  [[ -f "$file" && "$(stat -Lc %s "$file")" == "$size" ]] || return 1
  printf '%s  %s\n' "$digest" "$file" | sha256sum -c --quiet -
}

prepare_images() {
  # Pull the pinned upstream engine; a failure must not silently select another build.
  docker compose pull llm || return 1
  local service
  for service in setup whisper; do
    if [[ -n "${NPU_COSYVOICE_SRC:-}" ]] || ! docker compose --profile setup pull "$service"; then
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
