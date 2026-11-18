-- Short-lived posts (daily menu, bus updates, announcements) have their own origin.
ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_origin_check;
ALTER TABLE documents ADD CONSTRAINT documents_origin_check CHECK (origin IN ('git','web','sheet','note'));
