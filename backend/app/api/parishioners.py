from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.db import get_db
from app.schemas.parishioners import ParishionerCreate, ParishionerOut
from app.services.parishioners import create_parishioner, get_all_parishioners

router = APIRouter()

@router.post("/", response_model=ParishionerOut)
def create(data: ParishionerCreate, db: Session = Depends(get_db)):
    return create_parishioner(db, data)

@router.get("/", response_model=List[ParishionerOut])
def list_all(db: Session = Depends(get_db)):
    return get_all_parishioners(db)
