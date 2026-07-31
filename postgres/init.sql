-- ============================================================
-- OrderFlow - Data Warehouse schema
-- ============================================================
-- Se ejecuta automaticamente en el primer arranque de Postgres.
-- ============================================================

CREATE TABLE IF NOT EXISTS orders (
    order_id       VARCHAR(64)   PRIMARY KEY,
    customer_id    VARCHAR(32)   NOT NULL,
    region         VARCHAR(32)   NOT NULL,
    total_amount   NUMERIC(12,2) NOT NULL,
    currency       VARCHAR(4)    NOT NULL DEFAULT 'PEN',
    items_count    INTEGER       NOT NULL,
    created_at     TIMESTAMPTZ   NOT NULL,
    processed_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_region       ON orders (region);
CREATE INDEX IF NOT EXISTS idx_orders_created_at   ON orders (created_at);
CREATE INDEX IF NOT EXISTS idx_orders_processed_at ON orders (processed_at);

-- Vista util para verificaciones rapidas
CREATE OR REPLACE VIEW orders_summary AS
SELECT
    region,
    COUNT(*)                       AS orders_count,
    SUM(total_amount)              AS total_revenue,
    AVG(total_amount)              AS avg_order_value,
    MIN(processed_at)              AS first_order_at,
    MAX(processed_at)              AS last_order_at
FROM orders
GROUP BY region
ORDER BY orders_count DESC;
