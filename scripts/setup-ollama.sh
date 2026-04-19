#!/usr/bin/env bash

set -euo pipefail

DEFAULT_MODEL="${LLM_CF_OLLAMA_MODEL:-lfm2.5-thinking-128k:latest}"
INSTALL_IF_MISSING=0
START_DAEMON=1
PULL_MODELS=1

MODELS=()

print_usage() {
  cat <<'EOF'
Usage: scripts/setup-ollama.sh [options]

Options:
  --model <name>     Model to ensure is installed (repeatable).
                     Default: $LLM_CF_OLLAMA_MODEL or lfm2.5-thinking-128k:latest
  --install          Attempt to install Ollama if missing (macOS/Linux only)
  --no-start         Do not start ollama serve automatically
  --no-pull          Do not pull model(s); only verify local availability
  --help             Show this help

Examples:
  scripts/setup-ollama.sh
  scripts/setup-ollama.sh --model llama3.2:3b
  scripts/setup-ollama.sh --install --model lfm2.5-thinking-128k:latest
EOF
}

log() {
  printf '%s\n' "$*"
}

warn() {
  printf 'WARNING: %s\n' "$*" >&2
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

normalize_models() {
  if [ ${#MODELS[@]} -eq 0 ]; then
    MODELS=("$DEFAULT_MODEL")
  fi
}

install_ollama() {
  local platform
  platform="$(uname -s)"

  case "$platform" in
    Darwin)
      if has_cmd brew; then
        log "Installing Ollama via Homebrew..."
        brew install ollama
      else
        fail "Ollama not found and Homebrew is unavailable. Install from https://ollama.com/download"
      fi
      ;;
    Linux)
      if has_cmd curl; then
        log "Installing Ollama via official install script..."
        curl -fsSL https://ollama.com/install.sh | sh
      else
        fail "Ollama not found and curl is unavailable. Install manually: https://ollama.com/download"
      fi
      ;;
    *)
      fail "Automatic Ollama install is unsupported on this platform ($platform). Install manually: https://ollama.com/download"
      ;;
  esac
}

check_ollama_installed() {
  if has_cmd ollama; then
    return 0
  fi

  if [ "$INSTALL_IF_MISSING" -eq 1 ]; then
    install_ollama
  else
    fail "Ollama is not installed. Install it from https://ollama.com/download or rerun with --install"
  fi

  has_cmd ollama || fail "Ollama installation did not provide the 'ollama' command"
}

ollama_is_healthy() {
  curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1
}

start_ollama_if_needed() {
  if ollama_is_healthy; then
    log "Ollama API is already running at http://127.0.0.1:11434"
    return
  fi

  if [ "$START_DAEMON" -eq 0 ]; then
    fail "Ollama API is not running. Start it with 'ollama serve' or rerun without --no-start"
  fi

  log "Starting Ollama daemon..."
  nohup ollama serve >/tmp/llm-cf-ollama.log 2>&1 &

  local i
  for i in $(seq 1 30); do
    if ollama_is_healthy; then
      log "Ollama API is ready"
      return
    fi
    sleep 1
  done

  warn "Last 50 lines of /tmp/llm-cf-ollama.log:"
  tail -n 50 /tmp/llm-cf-ollama.log 2>/dev/null || true
  fail "Timed out waiting for Ollama API startup"
}

is_model_available() {
  local model="$1"
  ollama list | awk 'NR>1 {print $1}' | grep -Fxq "$model"
}

ensure_models() {
  local model

  for model in "${MODELS[@]}"; do
    if is_model_available "$model"; then
      log "Model already installed: $model"
      continue
    fi

    if [ "$PULL_MODELS" -eq 1 ]; then
      log "Pulling model: $model"
      ollama pull "$model"
    fi

    if is_model_available "$model"; then
      log "Model ready: $model"
    else
      fail "Model not available: $model"
    fi
  done
}

while [ $# -gt 0 ]; do
  case "$1" in
    --model)
      [ $# -lt 2 ] && fail "--model requires a value"
      MODELS+=("$2")
      shift 2
      ;;
    --install)
      INSTALL_IF_MISSING=1
      shift
      ;;
    --no-start)
      START_DAEMON=0
      shift
      ;;
    --no-pull)
      PULL_MODELS=0
      shift
      ;;
    --help)
      print_usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      ;;
  esac
done

normalize_models
check_ollama_installed
start_ollama_if_needed
ensure_models

log ""
log "Ollama setup complete."
log "Models verified: ${MODELS[*]}"
log "API endpoint: http://127.0.0.1:11434"
