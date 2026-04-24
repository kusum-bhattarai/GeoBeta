CREATE TABLE IF NOT EXISTS stock_prices (
    id                          SERIAL PRIMARY KEY,
    ticker                      VARCHAR(20) NOT NULL,
    price_date                  DATE NOT NULL,
    open                        NUMERIC(18, 4),
    high                        NUMERIC(18, 4),
    low                         NUMERIC(18, 4),
    close                       NUMERIC(18, 4),
    adjusted_close              NUMERIC(18, 4),
    volume                      BIGINT,
    dividend                    NUMERIC(18, 6),
    split_coefficient           NUMERIC(10, 6),
    price_delta_liberation_day_pct NUMERIC(10, 4),
    market_reaction_score       NUMERIC(10, 4),
    ingested_at                 TIMESTAMP DEFAULT NOW(),
    UNIQUE (ticker, price_date)
);

SELECT COUNT(*) AS existing_rows FROM stock_prices;