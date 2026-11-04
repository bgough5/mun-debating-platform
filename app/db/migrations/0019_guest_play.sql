-- D-099: single player for guests. One committee per scenario pack holds the clauses and positions the engine needs;
-- a guest's game lives in their browser and is sent with each move, so nothing about the guest is stored.
-- These committees are never listed for staff and nobody signs in to them.
ALTER TABLE committee ADD COLUMN guest_pack TEXT;
CREATE INDEX idx_committee_guest_pack ON committee (guest_pack);
