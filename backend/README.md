## Accounting rules for Sacraments

- When a sacrament is created with `fee > 0`, an **income** transaction is created:
  - `reference_no = "SAC-{id}"`, `description = "<Pretty Sacrament Name> fee"`,
    `category = "Sacraments – <Pretty Name>"`, `payment_method = "cash"` (default).
- Editing a sacrament:
  - Changes to `date`, `fee`, or `sacrament_type` update the linked transaction in place.
  - Changing `sacrament_type` updates both `description` and the category label.
- Setting `fee = 0` deletes the linked transaction.
- API responses return numeric `amount` values (floats/decimals), not strings.

### Pretty-name mapping examples
- `BAPTISM` → “Baptism”
- `CONFIRMATION` → “Confirmation”
- `DEATH` (aka `"funeral"`) → “Funeral”
