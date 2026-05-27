#!/usr/bin/env bash
set -euo pipefail

SUPPORTED_PROVIDERS=(opencode anthropic all)
DEFAULT_BASE_URL="${TRANQUERA_BASE_URL:-https://proxy.tranquera.dev}"
DEFAULT_MODEL="${TRANQUERA_MODEL:-gpt-5.1-codex}"
DEFAULT_OPENCODE_CONFIG="${OPENCODE_CONFIG:-${HOME}/.config/opencode/opencode.json}"

PROVIDER="all"
BASE_URL="${DEFAULT_BASE_URL}"
TOKEN="${TRANQUERA_TOKEN:-}"
MODEL="${DEFAULT_MODEL}"
OPENCODE_CONFIG="${DEFAULT_OPENCODE_CONFIG}"
SHELL_RC="${TRANQUERA_SHELL_RC:-}"
DRY_RUN=0
INTERACTIVE=0
[[ $# -eq 0 ]] && INTERACTIVE=1

usage() {
  cat <<'EOF'
Usage:
  setup-multi-provider.sh [options]

Options:
  --interactive                        Prompt for provider, URL, token and file options
  --provider <opencode|anthropic|all>  Provider setup to apply (default: all)
  --base-url <url>                     Tranquera proxy base URL (default: TRANQUERA_BASE_URL or production URL)
  --token <token>                      Tranquera path token (or TRANQUERA_TOKEN)
  --model <model>                      Default OpenAI-compatible model for opencode
  --opencode-config <path>             opencode config path (default: ~/.config/opencode/opencode.json)
  --shell-rc <path>                    Shell rc file for Anthropic setup (auto-detected by default)
  --dry-run                            Print safe actions without writing files
  -h, --help                           Show this help

Examples:
  ./scripts/setup-multi-provider.sh
  ./scripts/setup-multi-provider.sh --interactive
  ./scripts/setup-multi-provider.sh --provider all --token "$TRANQUERA_TOKEN"
  ./scripts/setup-multi-provider.sh --provider opencode --base-url http://127.0.0.1:8080 --token "$TRANQUERA_TOKEN"
  ./scripts/setup-multi-provider.sh --provider anthropic --token "$TRANQUERA_TOKEN" --dry-run

Security:
  This script never prints the token or full tokenized provider URLs. It may write the token
  into local client config files because path-token attribution requires it.
EOF
}

log() {
  printf '[tranquera-setup] %s\n' "$*"
}

fail() {
  printf '[tranquera-setup] error: %s\n' "$*" >&2
  exit 1
}

contains_provider() {
  local item="$1"
  local candidate
  for candidate in "${SUPPORTED_PROVIDERS[@]}"; do
    [[ "${candidate}" == "${item}" ]] && return 0
  done
  return 1
}

strip_trailing_slash() {
  local value="$1"
  printf '%s' "${value%/}"
}

require_token() {
  [[ -n "${TOKEN}" ]] || fail "missing token; pass --token or set TRANQUERA_TOKEN"
}

backup_file() {
  local path="$1"
  [[ -f "${path}" ]] || return 0
  local backup="${path}.bak.$(date +%Y%m%d%H%M%S)"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "would create backup: ${backup}"
  else
    cp "${path}" "${backup}"
    log "backup created: ${backup}"
  fi
}

detect_shell_rc() {
  if [[ -n "${SHELL_RC}" ]]; then
    printf '%s' "${SHELL_RC}"
    return 0
  fi

  case "${SHELL:-}" in
    */zsh) printf '%s' "${HOME}/.zshrc" ;;
    */bash)
      if [[ -f "${HOME}/.bash_profile" ]]; then
        printf '%s' "${HOME}/.bash_profile"
      else
        printf '%s' "${HOME}/.bashrc"
      fi
      ;;
    */fish) printf '%s' "${HOME}/.config/fish/config.fish" ;;
    *) printf '%s' "${HOME}/.profile" ;;
  esac
}

provider_url_anthropic() {
  printf '%s/cli/%s' "$(strip_trailing_slash "${BASE_URL}")" "${TOKEN}"
}

provider_url_openai() {
  printf '%s/openai/cli/%s/v1' "$(strip_trailing_slash "${BASE_URL}")" "${TOKEN}"
}

read_line() {
  local prompt="$1"
  local default_value="${2:-}"
  local answer=""

  if [[ -n "${default_value}" ]]; then
    printf '%s [%s]: ' "${prompt}" "${default_value}" >&2
  else
    printf '%s: ' "${prompt}" >&2
  fi

  IFS= read -r answer || answer=""
  if [[ -z "${answer}" ]]; then
    printf '%s' "${default_value}"
  else
    printf '%s' "${answer}"
  fi
}

read_secret() {
  local prompt="$1"
  local answer=""
  printf '%s: ' "${prompt}" >&2
  IFS= read -rs answer || answer=""
  printf '\n' >&2
  printf '%s' "${answer}"
}

prompt_provider() {
  local choice=""
  while true; do
    cat >&2 <<'EOF'
Provider setup:
  1) all       Configure opencode + Anthropic/Claude Code
  2) opencode  Configure only opencode via OpenAI-compatible
  3) anthropic Configure only Anthropic/Claude Code via ANTHROPIC_BASE_URL
EOF
    choice="$(read_line "Choose provider" "1")"
    case "${choice}" in
      1|all) printf 'all'; return 0 ;;
      2|opencode) printf 'opencode'; return 0 ;;
      3|anthropic) printf 'anthropic'; return 0 ;;
      *) printf '[tranquera-setup] invalid provider option: %s\n' "${choice}" >&2 ;;
    esac
  done
}

is_yes() {
  case "$1" in
    y|Y|yes|YES|Yes|s|S|si|SI|Sí|sí) return 0 ;;
    *) return 1 ;;
  esac
}

run_interactive() {
  local input=""
  local default_rc=""

  cat <<'EOF'
Tranquera multi-provider setup
This wizard will not print your token or tokenized provider URLs.
EOF

  PROVIDER="$(prompt_provider)"
  BASE_URL="$(read_line "Tranquera base URL" "${BASE_URL}")"
  BASE_URL="$(strip_trailing_slash "${BASE_URL}")"

  if [[ -z "${TOKEN}" ]]; then
    TOKEN="$(read_secret "Tranquera token (hidden)")"
  else
    input="$(read_line "Use token from TRANQUERA_TOKEN?" "Y")"
    if ! is_yes "${input}"; then
      TOKEN="$(read_secret "Tranquera token (hidden)")"
    fi
  fi

  if [[ "${PROVIDER}" == "opencode" || "${PROVIDER}" == "all" ]]; then
    MODEL="$(read_line "Default opencode model" "${MODEL}")"
    OPENCODE_CONFIG="$(read_line "opencode config path" "${OPENCODE_CONFIG}")"
  fi

  if [[ "${PROVIDER}" == "anthropic" || "${PROVIDER}" == "all" ]]; then
    default_rc="$(detect_shell_rc)"
    SHELL_RC="$(read_line "Shell rc path for ANTHROPIC_BASE_URL" "${default_rc}")"
  fi

  input="$(read_line "Dry run only?" "N")"
  if is_yes "${input}"; then
    DRY_RUN=1
  fi

  cat <<EOF

Summary:
  provider: ${PROVIDER}
  base URL: ${BASE_URL}
  token: <hidden>
  dry run: ${DRY_RUN}
EOF
  if [[ "${PROVIDER}" == "opencode" || "${PROVIDER}" == "all" ]]; then
    cat <<EOF
  opencode model: ${MODEL}
  opencode config: ${OPENCODE_CONFIG}
EOF
  fi
  if [[ "${PROVIDER}" == "anthropic" || "${PROVIDER}" == "all" ]]; then
    cat <<EOF
  shell rc: ${SHELL_RC}
EOF
  fi

  input="$(read_line "Continue?" "Y")"
  is_yes "${input}" || fail "cancelled by user"
}

setup_opencode() {
  require_token

  local config_path="${OPENCODE_CONFIG}"
  local config_dir
  config_dir="$(dirname "${config_path}")"
  local base_url
  base_url="$(provider_url_openai)"

  log "configuring opencode provider 'tranquera'"
  log "target config: ${config_path}"
  log "model: ${MODEL}"

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "dry-run: would merge provider.tranquera into opencode config"
    return 0
  fi

  mkdir -p "${config_dir}"
  backup_file "${config_path}"

  python3 - "${config_path}" "${base_url}" "${MODEL}" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
base_url = sys.argv[2]
model = sys.argv[3]

if config_path.exists() and config_path.read_text().strip():
    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {config_path}: {exc}")
else:
    config = {}

config.setdefault("$schema", "https://opencode.ai/config.json")
providers = config.setdefault("provider", {})
providers["tranquera"] = {
    "npm": "@ai-sdk/openai-compatible",
    "name": "Tranquera",
    "options": {
        "baseURL": base_url,
    },
    "models": {
        model: {"name": f"{model} via Tranquera"},
    },
}
config["model"] = f"tranquera/{model}"

config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
PY

  log "opencode config updated without printing tokenized URL"
}

setup_anthropic() {
  require_token

  local rc_path
  rc_path="$(detect_shell_rc)"
  local rc_dir
  rc_dir="$(dirname "${rc_path}")"
  local anthropic_base_url
  anthropic_base_url="$(provider_url_anthropic)"

  log "configuring Anthropic/Claude Code base URL"
  log "target rc: ${rc_path}"

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "dry-run: would write idempotent ANTHROPIC_BASE_URL block"
    return 0
  fi

  mkdir -p "${rc_dir}"
  touch "${rc_path}"
  backup_file "${rc_path}"

  python3 - "${rc_path}" "${anthropic_base_url}" <<'PY'
import sys
from pathlib import Path

rc_path = Path(sys.argv[1])
base_url = sys.argv[2]
start = "# >>> tranquera anthropic"
end = "# <<< tranquera anthropic"
block = f"{start}\nexport ANTHROPIC_BASE_URL='{base_url}'\n{end}\n"
text = rc_path.read_text() if rc_path.exists() else ""

if start in text and end in text:
    before = text.split(start, 1)[0].rstrip() + "\n"
    after = text.split(end, 1)[1].lstrip()
    new_text = before + block + after
else:
    separator = "" if not text or text.endswith("\n") else "\n"
    new_text = text + separator + block

rc_path.write_text(new_text)
PY

  log "Anthropic rc block updated without printing tokenized URL"
  log "reload shell or run: source ${rc_path}"
}

setup_provider() {
  case "$1" in
    opencode) setup_opencode ;;
    anthropic) setup_anthropic ;;
    all)
      setup_opencode
      setup_anthropic
      ;;
    *) fail "unsupported provider: $1" ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interactive)
      INTERACTIVE=1
      shift
      ;;
    --provider)
      [[ $# -ge 2 ]] || fail "--provider requires a value"
      PROVIDER="$2"
      shift 2
      ;;
    --base-url)
      [[ $# -ge 2 ]] || fail "--base-url requires a value"
      BASE_URL="$2"
      shift 2
      ;;
    --token)
      [[ $# -ge 2 ]] || fail "--token requires a value"
      TOKEN="$2"
      shift 2
      ;;
    --model)
      [[ $# -ge 2 ]] || fail "--model requires a value"
      MODEL="$2"
      shift 2
      ;;
    --opencode-config)
      [[ $# -ge 2 ]] || fail "--opencode-config requires a value"
      OPENCODE_CONFIG="$2"
      shift 2
      ;;
    --shell-rc)
      [[ $# -ge 2 ]] || fail "--shell-rc requires a value"
      SHELL_RC="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

if [[ "${INTERACTIVE}" -eq 1 ]]; then
  run_interactive
fi

contains_provider "${PROVIDER}" || fail "unsupported provider '${PROVIDER}'. Supported: ${SUPPORTED_PROVIDERS[*]}"
BASE_URL="$(strip_trailing_slash "${BASE_URL}")"

setup_provider "${PROVIDER}"
log "done"
