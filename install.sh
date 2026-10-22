#!/bin/bash
# Local Voice Buddy installer: checks the machine, prepares it, downloads the model and starts everything.
# Safe to run again; finished steps are skipped. Run it from this folder as your normal user (not root).
set -euo pipefail
cd "$(dirname "$0")"
source scripts/install_helpers.sh

MODEL_URL=https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-UD-Q4_K_M.gguf
MODEL_FILE=models/Qwen3.8-27B-UD-Q4_K_M.gguf
MODEL_SHA256=322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482
MODEL_SIZE=16464440224
NEED_GTT_GB=22  # the model (15.3 GiB) + its context + the speech models' NPU buffers live in GPU-mapped memory

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
fail() { printf '\n\033[31mStopped: %s\033[0m\n' "$*" >&2; exit 1; }
ask() { local a; read -r -p "$1 [Y/n] " a; [[ -z "$a" || "$a" =~ ^[Yy] ]]; }

say "Checking this machine"
[ "$(uname -s)-$(uname -m)" = Linux-x86_64 ] || fail "this needs Linux on x86_64"
[ "$(id -u)" != 0 ] || fail "run it as your normal user, not root (it asks for sudo when needed)"
[ -e /dev/accel/accel0 ] || fail "no NPU found (/dev/accel/accel0). This needs a Ryzen AI 7040/8040 CPU and the amdxdna driver (Linux 6.14 or newer)."
ls /dev/dri/renderD* >/dev/null 2>&1 || fail "no GPU render device in /dev/dri"
command -v python3 >/dev/null || fail "Python 3 is required"
command -v curl >/dev/null || fail "curl is required"
command -v docker >/dev/null || fail "Docker is not installed: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || fail "the Docker compose plugin is missing (package docker-compose-v2 or docker-compose-plugin)"
docker info >/dev/null 2>&1 || fail "cannot talk to Docker; add yourself to the docker group (sudo usermod -aG docker \$USER) and log in again"
# what Linux sees plus what the BIOS set aside for the GPU (anything from 0.5 to 16 GB)
vram_kb=$(cat /sys/class/drm/card*/device/mem_info_vram_total 2>/dev/null | awk '{s+=$1} END {print s/1024}')
mem_gb=$(awk -v v="${vram_kb:-0}" '/MemTotal/ {printf "%d", ($2+v)/1048576}' /proc/meminfo)
[ "$mem_gb" -ge 30 ] || fail "found ${mem_gb} GB of memory; this needs a 32 GB machine"
free_gb=$(df -BG --output=avail . | tail -1 | tr -dc 0-9)
[ -f "$MODEL_FILE" ] || [ "$free_gb" -ge 60 ] || fail "needs about 60 GB of free disk here, found ${free_gb} GB"
echo "ok: NPU, GPU, Docker, ${mem_gb} GB RAM, ${free_gb} GB free disk"

say "Preparing the system (needs sudo once)"
RULE=/etc/udev/rules.d/60-amdxdna-awake.rules
if [ ! -f "$RULE" ]; then
  echo "The NPU can fail to wake from power saving when memory is tight, which kills the speech services."
  if ask "Keep the NPU awake (adds $RULE)?"; then
    echo 'SUBSYSTEM=="pci", ACTION=="add|bind", DRIVER=="amdxdna", ATTR{power/control}="on"' | sudo tee "$RULE" >/dev/null
    sudo udevadm control --reload
    for d in /sys/bus/pci/drivers/amdxdna/0000:*; do [ -e "$d" ] && echo on | sudo tee "$d/power/control" >/dev/null; done
  fi
fi
swap_gb=$(awk '/SwapTotal/ {printf "%d", $2/1048576}' /proc/meminfo)
if [ "$swap_gb" -lt 4 ] && [ ! -f /swapfile-voice-buddy ]; then
  echo "Only ${swap_gb} GB of swap. After a reboot all three models load at once and briefly need more"
  echo "than 32 GB; swap absorbs that."
  if ask "Add an 8 GB swap file (/swapfile-voice-buddy)?"; then
    sudo fallocate -l 8G /swapfile-voice-buddy && sudo chmod 600 /swapfile-voice-buddy
    sudo mkswap /swapfile-voice-buddy >/dev/null && sudo swapon /swapfile-voice-buddy
    echo '/swapfile-voice-buddy none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  fi
fi
gtt_gb=0
for f in /sys/class/drm/card*/device/mem_info_gtt_total; do
  [ -r "$f" ] && gtt_gb=$(( $(cat "$f") / 1073741824 )) && break
done
if [ "$gtt_gb" -lt "$NEED_GTT_GB" ]; then
  echo "The GPU may only use ${gtt_gb} GB of system memory; the model needs ${NEED_GTT_GB} GB."
  echo "Fix: add  amdgpu.gttsize=24576 ttm.pages_limit=6291456  to the kernel command line and reboot."
  if python3 scripts/install_support.py grub-ready /etc/default/grub 2>/dev/null; then
    echo "Both requested parameters are configured. If this boot already uses them, inspect the GPU/driver configuration."
    echo "Otherwise reboot, then run ./install.sh again."
  elif [ -f /etc/default/grub ] && ask "Update the two GPU memory parameters in /etc/default/grub and rebuild GRUB?"; then
    grub_tmp=$(mktemp)
    trap 'rm -f "$grub_tmp"' EXIT
    python3 scripts/install_support.py grub-render /etc/default/grub > "$grub_tmp"
    sudo cp -p /etc/default/grub "/etc/default/grub.voice-buddy.$(date +%Y%m%d%H%M%S).bak"
    sudo tee /etc/default/grub < "$grub_tmp" >/dev/null
    sudo update-grub
    rm -f "$grub_tmp"
    trap - EXIT
    echo "Reboot, then run ./install.sh again."
  else
    echo "Configure both parameters with your bootloader before continuing."
  fi
  exit 1
fi

if [ ! -f .env ]; then
  {
    echo "RENDER_GID=$(getent group render | cut -d: -f3)"
    echo "VIDEO_GID=$(getent group video | cut -d: -f3)"
  } > .env
  cat .env.example >> .env
fi
set -a; . ./.env; set +a

if ! model_verified "$MODEL_FILE" "$MODEL_SIZE" "$MODEL_SHA256"; then
  say "Downloading Qwen3.8-27B (16.5 GB; an interrupted download resumes)"
  mkdir -p models
  # curl refuses to resume a file that is already complete, so skip the download then and just check it
  [ "$(stat -Lc %s "$MODEL_FILE" 2>/dev/null)" = "$MODEL_SIZE" ] || curl -fL --retry 5 -C - -o "$MODEL_FILE" "$MODEL_URL"
  echo "checking the download..."
  model_verified "$MODEL_FILE" "$MODEL_SIZE" "$MODEL_SHA256" || fail "the model file is damaged; delete $MODEL_FILE and run again"
  touch "$MODEL_FILE.ok"
fi

say "Getting the programs (prebuilt where available, otherwise built here: 20-40 minutes)"
prepare_images
say "Preparing the speech models (downloads ~5 GB the first time)"
docker compose run --rm --no-deps --pull never setup

say "Starting"
docker compose up -d --no-build --pull never
echo "Waiting for chat, synthesis, recognition and the web interface (first-start NPU compilation can take several minutes)..."
for _ in $(seq 480); do
  if services_ready; then
    web_port=$(published_webui_port) || fail "cannot determine the web interface port; see docker compose ps"
    web_host=${WEBUI_BIND:-127.0.0.1}
    [[ "$web_host" != 0.0.0.0 && "$web_host" != 127.0.0.1 ]] || web_host=localhost
    say "Ready"
    echo "Open http://${web_host}:${web_port} on this machine. The first account you create is the admin."
    echo "For another computer or phone, see 'Use it from your phone'"
    echo "in README.md. Chat and both speech services are ready."
    exit 0
  fi
  sleep 5
done
fail "not ready after the startup wait; see docker compose logs"
