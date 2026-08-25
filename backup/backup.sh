#!/bin/sh
# Hourly mysqldump backup of the main eVoteGhana database.
# Backups are written to /backups (mounted volume) and pruned after 7 days.
set -e
set -o pipefail

OUT="/backups/evote_$(date +%Y%m%d_%H%M%S).sql.gz"

mysqldump \
  --host="${DB_HOST:-db}" \
  --user="${DB_USER:-root}" \
  --port="${DB_PORT:-3306}" \
  --password="${DB_PASSWORD}" \
  --single-transaction \
  "${DB_NAME_MAIN:-mydb}" \
  | gzip > "${OUT}"

# Prune backups older than 7 days
find /backups -name 'evote_*.sql.gz' -mtime +7 -delete

echo "$(date -Is) backup written: ${OUT}"
