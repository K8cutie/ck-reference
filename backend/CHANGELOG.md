## [Unreleased]

### Added
- Automatic sync between **Sacrament** and **Transaction**:
  - Create income transaction when `fee > 0`.
  - Keep transaction in sync on sacrament updates (date/amount/label/category).
  - Remove transaction when `fee` becomes `0`.
  - Support alias `"funeral"` → sacrament type `DEATH` (labels/categories use “Funeral”).

### Changed
- Schemas updated to Pydantic v2 style (`ConfigDict(from_attributes=True)`).
- Transaction responses now return **numeric** `amount` (not string).
- `payment_method` defaults to `"cash"` and is always non-null in API responses.

### Fixed
- `test_sacrament_update_keeps_transaction_in_sync` now passes (handles fee=0 delete).
- Smoke tests expect numeric amounts and pass.

### Notes
- No DB migration required for the above (optional: add UNIQUE index on `transactions.reference_no` later).