-- Documents kept out of the public repository (content-private/) have their own origin.
ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_origin_check;
ALTER TABLE documents ADD CONSTRAINT documents_origin_check CHECK (origin IN ('git','web','sheet','note','private'));
