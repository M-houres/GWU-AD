#!/bin/sh
set -eu

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_root="${BACKUP_DIR:-/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-7}"

db_dir="${backup_root}/db"
runtime_dir="${backup_root}/runtime"

mkdir -p "${db_dir}" "${runtime_dir}"

db_file="${db_dir}/mysql_${timestamp}.sql.gz"
runtime_file="${runtime_dir}/runtime_${timestamp}.tar.gz"

echo "[backup] starting mysql dump ${timestamp}"
mysqldump \
  --host="${MYSQL_HOST:-mysql}" \
  --port="${MYSQL_PORT:-3306}" \
  --user="${MYSQL_USER:-root}" \
  --password="${MYSQL_PASSWORD:-}" \
  --single-transaction \
  --quick \
  --skip-lock-tables \
  "${MYSQL_DATABASE:-wuhongai}" | gzip > "${db_file}"

echo "[backup] archiving runtime volumes ${timestamp}"
tar -czf "${runtime_file}" -C /volumes uploads output algorithms

find "${backup_root}" -type f -mtime +"${retention_days}" -delete

echo "[backup] completed db=${db_file} runtime=${runtime_file}"
