-- DBeaver: substitute the IDs with values from the first query.
SELECT * FROM admin_chat_history ORDER BY asked_at DESC LIMIT 100;
SELECT * FROM admin_chat_history WHERE session_id = '<session-id>' ORDER BY sequence_number;
SELECT * FROM admin_chat_history WHERE user_id = '<user-id>' ORDER BY asked_at DESC;
SELECT * FROM admin_chat_history WHERE response_status = 'FAILED' ORDER BY asked_at DESC;
SELECT * FROM admin_chat_evidence WHERE message_id = '<assistant-message-id>' ORDER BY rank;
SELECT * FROM admin_chat_history WHERE latency_ms > 5000 ORDER BY latency_ms DESC;
