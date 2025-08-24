from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.db import get_db
from app.schemas.categories import CategoryCreate, CategoryOut
from app.services.categories import create_category, get_all_categories

router = APIRouter()

@router.post("/", response_model=CategoryOut)
def create(data: CategoryCreate, db: Session = Depends(get_db)):
    return create_category(db, data)

@router.get("/", response_model=List[CategoryOut])
def list_all(db: Session = Depends(get_db)):
    return get_all_categories(db)
