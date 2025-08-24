from __future__ import annotations

from app.models.sacrament import SacramentType
from app.services import sacraments as svc


def test_funeral_alias_and_labels():
    # accept "funeral" from API payload, store as enum DEATH
    assert svc._enum_from_payload("funeral") == SacramentType.DEATH
    assert svc._enum_from_payload("FUNERAL") == SacramentType.DEATH

    # user-facing labels & type normalization
    assert svc._readable_label("DEATH") == "Funeral"
    assert svc._external_type_from_enum("DEATH") == "funeral"

    # category naming uses the readable label
    label = svc._readable_label("DEATH")
    assert f"Sacraments – {label}" == "Sacraments – Funeral"
