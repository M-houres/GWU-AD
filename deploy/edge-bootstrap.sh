#!/bin/sh
set -eu

TEMPLATE_DIR="/etc/nginx/templates"
TARGET_CONF="/etc/nginx/conf.d/default.conf"
CERT_DIR="/etc/nginx/certs"
EDGE_DOMAIN="${EDGE_DOMAIN:-restin.top}"
EDGE_WWW_DOMAIN="www.${EDGE_DOMAIN#www.}"

render_template() {
  sed \
    -e "s/__EDGE_DOMAIN__/${EDGE_DOMAIN}/g" \
    -e "s/__EDGE_WWW_DOMAIN__/${EDGE_WWW_DOMAIN}/g" \
    "$1" > "${TARGET_CONF}"
}

if [ -f "${CERT_DIR}/fullchain.pem" ] && [ -f "${CERT_DIR}/privkey.pem" ]; then
  render_template "${TEMPLATE_DIR}/https.conf"
  echo "[edge-bootstrap] TLS certificates found. Starting HTTPS edge."
else
  render_template "${TEMPLATE_DIR}/http.conf"
  echo "[edge-bootstrap] TLS certificates not found. Starting HTTP-only edge."
fi

exec nginx -g 'daemon off;'
