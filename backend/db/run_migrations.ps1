# run_migrations.ps1
# Sequential migration runner for S.P.A.R.K. database

$migrations = @(
    "backend/db/migrations/001_init_schema.sql",
    "backend/db/migrations/002_hypertable_setup.sql",
    "backend/db/migrations/003_scoring_tables.sql",
    "backend/db/migrations/004_graph_tables.sql",
    "backend/db/migrations/005_auth_hardening.sql",
    "backend/db/migrations/006_audit_event_type.sql",
    "backend/db/migrations/007_unique_fraud_label_txn.sql",
    "backend/db/migrations/008_integrity_and_thresholds.sql"
)

Write-Host "Running database migrations on spark-postgres..." -ForegroundColor Cyan

foreach ($file in $migrations) {
    if (Test-Path $file) {
        Write-Host "Executing $file..." -ForegroundColor Yellow
        Get-Content $file | docker exec -i spark-postgres psql -U spark_user -d spark_db
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error executing $file" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Migration file not found: $file" -ForegroundColor Red
        exit 1
    }
}

Write-Host "All migrations executed successfully!" -ForegroundColor Green
