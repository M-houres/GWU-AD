#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="${REPO_OWNER:-M-houres}"
REPO_NAME="${REPO_NAME:-GWU-AD}"
BRANCH="${BRANCH:-main}"

APP_DIR="${APP_DIR:-/opt/gewuxueshu}"
ENV_FILE="${ENV_FILE:-${APP_DIR}/.env.prod}"
COMPOSE_FILE="${COMPOSE_FILE:-${APP_DIR}/docker-compose.prod.yml}"
KEEP_ENV="${KEEP_ENV:-1}"
INFRA_SERVICES=(mysql redis)
APP_SERVICES=(backend worker-submission worker-processing worker-maintenance worker-beat frontend edge backup)

TARBALL_URL="${TARBALL_URL:-https://codeload.github.com/${REPO_OWNER}/${REPO_NAME}/tar.gz/refs/heads/${BRANCH}}"
TMP_ROOT="$(mktemp -d /tmp/gewu-update.XXXXXX)"

log() {
  printf "\n[%s] %s\n" "$(date '+%F %T')" "$*"
}

abort() {
  echo "ERROR: $*" >&2
  exit 1
}

cleanup() {
  rm -rf "${TMP_ROOT}"
}
trap cleanup EXIT

run_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

upsert_env_value() {
  local key="$1"
  local value="$2"
  local file="$3"
  local escaped_value
  escaped_value="$(printf '%s' "${value}" | sed 's/[&/\]/\\&/g')"
  if run_root grep -q "^${key}=" "${file}" 2>/dev/null; then
    run_root sed -i "s|^${key}=.*|${key}=${escaped_value}|" "${file}"
  else
    printf '\n%s=%s\n' "${key}" "${value}" | run_root tee -a "${file}" >/dev/null
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || abort "Missing command: $1"
}

validate_paths() {
  [ -n "${APP_DIR}" ] || abort "APP_DIR is empty"
  [ "${APP_DIR}" != "/" ] || abort "APP_DIR cannot be /"
  case "${APP_DIR}" in
    /opt/*) ;;
    *)
      abort "APP_DIR must be under /opt for safety. Current: ${APP_DIR}"
      ;;
  esac
}

download_source() {
  local tarball="${TMP_ROOT}/source.tar.gz"
  log "Downloading source from ${TARBALL_URL}"
  curl -fL --retry 8 --retry-delay 2 --retry-all-errors "${TARBALL_URL}" -o "${tarball}"
  tar -xzf "${tarball}" -C "${TMP_ROOT}"
}

sync_source() {
  local src_dir
  src_dir="$(find "${TMP_ROOT}" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  [ -n "${src_dir}" ] || abort "Cannot locate extracted source directory"
  [ -f "${src_dir}/docker-compose.prod.yml" ] || abort "Invalid source: missing docker-compose.prod.yml"
  [ -f "${src_dir}/.env.prod.example" ] || abort "Invalid source: missing .env.prod.example"

  if [ "${KEEP_ENV}" = "1" ] && [ -f "${ENV_FILE}" ]; then
    cp "${ENV_FILE}" "${TMP_ROOT}/.env.prod.keep"
  fi

  log "Sync source into ${APP_DIR}"
  run_root mkdir -p "${APP_DIR}"

  if command -v rsync >/dev/null 2>&1; then
    run_root rsync -a --delete \
      --exclude ".env.prod" \
      --exclude ".env" \
      "${src_dir}/" "${APP_DIR}/"
  else
    validate_paths
    run_root rm -rf "${APP_DIR}"
    run_root mkdir -p "${APP_DIR}"
    run_root cp -a "${src_dir}/." "${APP_DIR}/"
  fi

  if [ "${KEEP_ENV}" = "1" ] && [ -f "${TMP_ROOT}/.env.prod.keep" ]; then
    run_root cp "${TMP_ROOT}/.env.prod.keep" "${ENV_FILE}"
  elif [ ! -f "${ENV_FILE}" ] && [ -f "${APP_DIR}/.env.prod.example" ]; then
    run_root cp "${APP_DIR}/.env.prod.example" "${ENV_FILE}"
  fi
}

normalize_runtime_scripts() {
  if [ -f "${APP_DIR}/scripts/update_prod_server.sh" ]; then
    run_root sed -i 's/\r$//' "${APP_DIR}/scripts/update_prod_server.sh" || true
    run_root chmod +x "${APP_DIR}/scripts/update_prod_server.sh" || true
  fi
  if [ -f "${APP_DIR}/deploy/backup_runtime_state.sh" ]; then
    run_root sed -i 's/\r$//' "${APP_DIR}/deploy/backup_runtime_state.sh" || true
    run_root chmod +x "${APP_DIR}/deploy/backup_runtime_state.sh" || true
  fi
  if [ -f "${APP_DIR}/deploy/edge-bootstrap.sh" ]; then
    run_root sed -i 's/\r$//' "${APP_DIR}/deploy/edge-bootstrap.sh" || true
    run_root chmod +x "${APP_DIR}/deploy/edge-bootstrap.sh" || true
  fi
}

prepare_public_edge() {
  local edge_domain cert_dir target_cert_dir
  edge_domain="$(grep -E '^EDGE_DOMAIN=' "${ENV_FILE}" 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  edge_domain="${edge_domain:-restin.top}"
  cert_dir="$(grep -E '^EDGE_CERTS_DIR=' "${ENV_FILE}" 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  target_cert_dir="${APP_DIR}/deploy/certs"
  run_root mkdir -p "${target_cert_dir}"
  if [ -d "/etc/letsencrypt/live/${edge_domain}" ] && [ -f "/etc/letsencrypt/live/${edge_domain}/fullchain.pem" ] && [ -f "/etc/letsencrypt/live/${edge_domain}/privkey.pem" ]; then
    log "Detected Let's Encrypt cert directory: /etc/letsencrypt/live/${edge_domain}"
    run_root cp -L "/etc/letsencrypt/live/${edge_domain}/fullchain.pem" "${target_cert_dir}/fullchain.pem"
    run_root cp -L "/etc/letsencrypt/live/${edge_domain}/privkey.pem" "${target_cert_dir}/privkey.pem"
    run_root chmod 644 "${target_cert_dir}/fullchain.pem"
    run_root chmod 600 "${target_cert_dir}/privkey.pem"
    cert_dir="${target_cert_dir}"
    log "Copied TLS certs into ${target_cert_dir}"
  elif [ -z "${cert_dir}" ]; then
    cert_dir="${target_cert_dir}"
  fi
  upsert_env_value "EDGE_CERTS_DIR" "${cert_dir}" "${ENV_FILE}"
  if command -v systemctl >/dev/null 2>&1; then
    run_root systemctl stop nginx || true
    run_root systemctl disable nginx || true
  fi
}

wait_for_service_state() {
  local service="$1"
  local desired="$2"
  local max_attempts="${3:-60}"
  local attempt status
  for attempt in $(seq 1 "${max_attempts}"); do
    status="$(run_root docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "wuhongai-${service}" 2>/dev/null || true)"
    if [ "${status}" = "${desired}" ]; then
      return 0
    fi
    sleep 2
  done
  echo "Service ${service} did not reach state ${desired}. Current: ${status:-unknown}" >&2
  return 1
}

ensure_infra() {
  log "Ensuring infrastructure services"
  cd "${APP_DIR}"
  run_root docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d "${INFRA_SERVICES[@]}"
  wait_for_service_state mysql healthy 90
  wait_for_service_state redis healthy 60
}

deploy_compose() {
  log "Deploying application services"
  cd "${APP_DIR}"
  run_root docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build --no-deps --remove-orphans "${APP_SERVICES[@]}"
  run_root docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
}

health_check() {
  log "Health check"
  wait_for_service_state backend healthy 120
  wait_for_service_state frontend healthy 90
  wait_for_service_state edge healthy 90
  wait_for_service_state worker-submission healthy 90
  wait_for_service_state worker-processing healthy 90
  wait_for_service_state worker-maintenance healthy 90
  wait_for_service_state worker-beat healthy 90

  if curl -fsS -H "Host: ${EDGE_DOMAIN:-restin.top}" http://127.0.0.1/api/v1/auth/options >/dev/null 2>&1; then
    echo "Health check passed."
    return 0
  fi
  echo "WARNING: health check timeout."
  echo "Run: sudo docker compose --env-file ${ENV_FILE} -f ${COMPOSE_FILE} logs --tail=200"
  return 1
}

main() {
  require_cmd curl
  require_cmd tar
  require_cmd docker
  validate_paths
  download_source
  sync_source
  normalize_runtime_scripts
  prepare_public_edge
  ensure_infra
  deploy_compose
  health_check
  log "Update complete"
  echo "App dir: ${APP_DIR}"
  echo "Branch: ${BRANCH}"
}

main "$@"
