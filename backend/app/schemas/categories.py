# app/schemas/categories.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None

    # Pydantic v2 replacement for orm_mode
    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CategoryRead(CategoryBase):
    id: int


# Back-compat for older imports (e.g., from app.schemas.categories import CategoryOut)
CategoryOut = CategoryRead
