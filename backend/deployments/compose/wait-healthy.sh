#!/usr/bin/env bash
# Wait until one or more Compose containers are healthy, then exit.
# Hard timeout: never spin forever (agents must cut off and report).
#
# Usage:
#   ./wait-healthy.sh [--timeout SEC] [--interval SEC] CONTAINER [CONTAINER...]
#
# CONTAINER may be a Compose service name, container name, or container ID.
# Progress lines use human service names (not raw hashes).
#
# Exit codes:
#   0  all containers healthy
#   1  timeout (still starting/unhealthy)
#   2  container missing, exited, or restarting loop
#   64 usage error

set -euo pipefail

TIMEOUT_SEC=300
INTERVAL_SEC=5
CONTAINERS=()

usage() {
  echo "Usage: $0 [--timeout SEC] [--interval SEC] CONTAINER [CONTAINER...]" >&2
  echo "Defaults: --timeout ${TIMEOUT_SEC} --interval ${INTERVAL_SEC}" >&2
  exit 64
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout)
      [[ $# -ge 2 ]] || usage
      TIMEOUT_SEC="$2"
      shift 2
      ;;
    --interval)
      [[ $# -ge 2 ]] || usage
      INTERVAL_SEC="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    --)
      shift
      CONTAINERS+=("$@")
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      ;;
    *)
      CONTAINERS+=("$1")
      shift
      ;;
  esac
done

[[ ${#CONTAINERS[@]} -gt 0 ]] || usage

deadline=$((SECONDS + TIMEOUT_SEC))
# Restarting more than this many consecutive polls ⇒ treat as failure (not "still booting").
max_restarting_streak=6
declare -A restarting_streak=()
declare -A display_names=()

# Prefer Compose service label, else container name, else short id.
display_name() {
  local ref="$1" svc name
  if [[ -n "${display_names[$ref]:-}" ]]; then
    printf '%s\n' "${display_names[$ref]}"
    return 0
  fi
  svc="$(docker inspect --format='{{index .Config.Labels "com.docker.compose.service"}}' "$ref" 2>/dev/null || true)"
  svc="${svc//$'\r'/}"
  svc="${svc%%$'\n'*}"
  if [[ -n "$svc" ]]; then
    display_names["$ref"]="$svc"
    printf '%s\n' "$svc"
    return 0
  fi
  name="$(docker inspect --format='{{.Name}}' "$ref" 2>/dev/null || true)"
  name="${name//$'\r'/}"
  name="${name%%$'\n'*}"
  name="${name#/}"
  if [[ -n "$name" ]]; then
    display_names["$ref"]="$name"
    printf '%s\n' "$name"
    return 0
  fi
  # Already a short/human token (service name) or truncate long ids.
  if [[ ${#ref} -gt 16 ]]; then
    display_names["$ref"]="${ref:0:12}"
  else
    display_names["$ref"]="$ref"
  fi
  printf '%s\n' "${display_names[$ref]}"
}

# Raw docker health/state → short operator-facing word.
status_word() {
  case "$1" in
    healthy) echo ready ;;
    starting) echo starting ;;
    unhealthy) echo unhealthy ;;
    restarting) echo restarting ;;
    missing) echo missing ;;
    exited|dead) echo "$1" ;;
    running) echo running ;;
    *) echo "$1" ;;
  esac
}

status_of() {
  local name="$1" out
  if ! out="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$name" 2>/dev/null)"; then
    echo missing
    return 0
  fi
  out="${out//$'\r'/}"
  out="${out%%$'\n'*}"
  if [[ -z "$out" ]]; then
    echo missing
  else
    printf '%s\n' "$out"
  fi
}

all_healthy() {
  local name st
  for name in "${CONTAINERS[@]}"; do
    st="$(status_of "$name")"
    [[ "$st" == "healthy" ]] || return 1
  done
  return 0
}

progress_line() {
  local remaining="$1" ref st label word parts=()
  for ref in "${CONTAINERS[@]}"; do
    st="$(status_of "$ref")"
    label="$(display_name "$ref")"
    word="$(status_word "$st")"
    parts+=("${label}: ${word}")
  done
  local joined
  joined="$(IFS=', '; echo "${parts[*]}")"
  echo "Waiting for databases (${remaining}s left): ${joined}"
}

echo "Checking health for: $(
  labels=()
  for ref in "${CONTAINERS[@]}"; do
    labels+=("$(display_name "$ref")")
  done
  IFS=', '
  echo "${labels[*]}"
)"

while (( SECONDS < deadline )); do
  remaining=$((deadline - SECONDS))
  failed=0
  line="$(progress_line "$remaining")"

  for name in "${CONTAINERS[@]}"; do
    st="$(status_of "$name")"
    label="$(display_name "$name")"

    case "$st" in
      healthy)
        restarting_streak["$name"]=0
        ;;
      missing|exited|dead)
        echo "$line" >&2
        echo "FAIL: ${label} is ${st} — aborting (not waiting full timeout)" >&2
        docker logs "$name" 2>&1 | tail -40 || true
        exit 2
        ;;
      restarting)
        restarting_streak["$name"]=$((${restarting_streak["$name"]:-0} + 1))
        if (( restarting_streak["$name"] >= max_restarting_streak )); then
          echo "$line" >&2
          echo "FAIL: ${label} restarting for ${restarting_streak[$name]} polls — aborting" >&2
          docker logs "$name" 2>&1 | tail -50 || true
          exit 2
        fi
        ;;
      *)
        restarting_streak["$name"]=0
        ;;
    esac
  done

  echo "$line"

  if all_healthy; then
    labels=()
    for ref in "${CONTAINERS[@]}"; do
      labels+=("$(display_name "$ref")")
    done
    echo "OK: all healthy ($(IFS=', '; echo "${labels[*]}"))"
    exit 0
  fi

  # Sleep at most INTERVAL, but never past the deadline by more than a second.
  sleep_for=$INTERVAL_SEC
  if (( SECONDS + sleep_for > deadline )); then
    sleep_for=$((deadline - SECONDS))
    (( sleep_for > 0 )) || break
  fi
  sleep "$sleep_for"
done

echo "TIMEOUT: waited ${TIMEOUT_SEC}s; still not healthy:" >&2
for name in "${CONTAINERS[@]}"; do
  label="$(display_name "$name")"
  st="$(status_of "$name")"
  echo "  ${label}: $(status_word "$st")" >&2
  docker logs "$name" 2>&1 | tail -30 || true
done
exit 1
