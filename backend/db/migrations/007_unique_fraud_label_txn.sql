-- Ensure each transaction has at most one fraud label for label upserts.
CREATE UNIQUE INDEX IF NOT EXISTS uq_fraud_labels_txn ON fraud_labels (txn_id);
