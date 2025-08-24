from sqlalchemy.orm import Session
from app.models.categories import Category
from app.schemas.categories import CategoryCreate

def create_category(db: Session, data: CategoryCreate) -> Category:
    category = Category(**data.dict())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category

def get_all_categories(db: Session):
    return db.query(Category).all()
