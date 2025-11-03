#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
Usage: scripts/reacher_validate.sh [OPTIONS] EMAIL [EMAIL...]

Validate one or more email addresses against the local Reacher service (default http://localhost:8080).

Positional arguments:
  EMAIL                Email address to validate (can provide multiple).

Options:
  --host URL           Reacher base URL (default: $REACHER_HOST or http://localhost:8080).
  --from EMAIL         From email used when probing SMTP (default: noreply@<hello_name>).
  --hello NAME         HELO/EHLO name for SMTP handshake (default: domain of --from email).
  --smtp-port PORT     SMTP port sent in JSON payload (default: 25).
  -v, --verbose        Output full JSON response for each email in addition to the boolean result.
  -h, --help           Show this help text and exit.

Environment variables:
  REACHER_HOST         Override default host URL for the Reacher API.
  REACHER_SMTP_PORT    Override default SMTP port.

EOF
}

HOST="${REACHER_HOST:-http://localhost:8080}"
SMTP_PORT="${REACHER_SMTP_PORT:-25}"
FROM_EMAIL=""
HELLO_NAME=""
VERBOSE=false
EMAILS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      exit 0
      ;;
    --host)
      [[ $# -ge 2 ]] || { echo "error: --host requires an argument" >&2; exit 1; }
      HOST="$2"
      shift 2
      ;;
    --from)
      [[ $# -ge 2 ]] || { echo "error: --from requires an argument" >&2; exit 1; }
      FROM_EMAIL="$2"
      shift 2
      ;;
    --hello)
      [[ $# -ge 2 ]] || { echo "error: --hello requires an argument" >&2; exit 1; }
      HELLO_NAME="$2"
      shift 2
      ;;
    --smtp-port)
      [[ $# -ge 2 ]] || { echo "error: --smtp-port requires an argument" >&2; exit 1; }
      SMTP_PORT="$2"
      shift 2
      ;;
    -v|--verbose)
      VERBOSE=true
      shift
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "error: unknown option $1" >&2
      exit 1
      ;;
    *)
      EMAILS+=("$1")
      shift
      ;;
  esac
done

EMAILS+=("$@")

if [[ ${#EMAILS[@]} -eq 0 ]]; then
  echo "error: EMAIL is required" >&2
  show_help >&2
  exit 1
fi

if [[ -z "$FROM_EMAIL" ]]; then
  DEFAULT_DOMAIN="${HELLO_NAME:-$(hostname -f 2>/dev/null || echo "localhost")}"
  FROM_EMAIL="noreply@${DEFAULT_DOMAIN#*@}"
fi

if [[ -z "$HELLO_NAME" ]]; then
  HELLO_NAME="${FROM_EMAIL##*@}"
fi

parse_is_reachable() {
  local response="$1"
  if command -v jq >/dev/null 2>&1; then
    echo "$response" | jq -r '.is_reachable // empty'
    return
  fi
  local python_cmd=""
  if command -v python3 >/dev/null 2>&1; then
    python_cmd="python3"
  elif command -v python >/dev/null 2>&1; then
    python_cmd="python"
  fi
  if [[ -n "$python_cmd" ]]; then
    echo "$response" | "$python_cmd" -c 'import json, sys; print(json.load(sys.stdin).get("is_reachable",""))'
  else
    echo ""
  fi
}

pretty_print() {
  local response="$1"
  if command -v jq >/dev/null 2>&1; then
    echo "$response" | jq .
    return
  fi
  local python_cmd=""
  if command -v python3 >/dev/null 2>&1; then
    python_cmd="python3"
  elif command -v python >/dev/null 2>&1; then
    python_cmd="python"
  fi
  if [[ -n "$python_cmd" ]]; then
    echo "$response" | "$python_cmd" -m json.tool
  else
    echo "$response"
  fi
}

for TO_EMAIL in "${EMAILS[@]}"; do
  PAYLOAD=$(cat <<EOF
{
  "to_email": "$TO_EMAIL",
  "from_email": "$FROM_EMAIL",
  "hello_name": "$HELLO_NAME",
  "smtp_port": $SMTP_PORT
}
EOF
)

  RESPONSE=$(curl -sS -X POST "$HOST/v0/check_email" \
    -H 'Content-Type: application/json' \
    -d "$PAYLOAD")

  IS_REACHABLE=$(parse_is_reachable "$RESPONSE")
  if [[ "$IS_REACHABLE" == "safe" ]]; then
    RESULT="True"
  else
    RESULT="False"
  fi

  echo "$TO_EMAIL: $RESULT"

  if $VERBOSE; then
    pretty_print "$RESPONSE"
  fi
done
