#!/bin/bash
# run_migrations.sh
# Sequential migration runner for S.P.A.R.K. database
set -e

for f in backend/db/migrations/001_init_schema.sql \
         backend/db/migrations/002_hypertable_setup.sql \
         backend/db/migrations/003_scoring_tables.sql \
         backend/db/migrations/004_graph_tables.sql \
         backend/db/migrations/005_auth_hardening.sql \
         backend/db/migrations/006_audit_event_type.sql \
         backend/db/migrations/007_unique_fraud_label_txn.sql \
         backend/db/migrations/008_integrity_and_thresholds.sql; do
  echo "Running $f..."
  docker exec -i spark-postgres psql -U spark_user -d spark_db < "$f"
done

echo "Migrations complete."
