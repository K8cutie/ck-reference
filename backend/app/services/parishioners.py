from sqlalchemy.orm import Session
from app.models.parishioners import Parishioner
from app.schemas.parishioners import ParishionerCreate

def create_parishioner(db: Session, data: ParishionerCreate) -> Parishioner:
    parishioner = Parishioner(**data.model_dump())
    db.add(parishioner)
    db.commit()
    db.refresh(parishioner)
    return parishioner

def get_all_parishioners(db: Session):
    return db.query(Parishioner).all()
