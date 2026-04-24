-- Load all backtest events with full data
SELECT 
    id,
    source_id,
    event_name,
    event_date::date AS event_date,
    event_type,
    pre_event_trajectory,
    post_event_sector_returns,
    index_was_rising_pre_event,
    accuracy_note
FROM backtest_events
ORDER BY event_date