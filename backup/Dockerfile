# Backup container: uses the official MySQL client (matches MySQL 8 auth plugins)
# so mysqldump can connect to the db service without auth plugin issues.
FROM mysql:8.0

RUN microdnf install -y cronie \
    && microdnf clean all

COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh

# Run the backup every hour (cronie reads /etc/cron.d; the user field is required).
RUN echo "0 * * * * root /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1" > /etc/cron.d/evote-backup

CMD ["crond", "-n"]
