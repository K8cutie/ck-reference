from sqlalchemy.orm import Session
from app.models.transactions import Transaction
from app.schemas.transactions import TransactionCreate

def create_transaction(db: Session, tx: TransactionCreate) -> Transaction:
    db_tx = Transaction(**tx.model_dump())
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx

def get_transactions(db: Session):
    return db.query(Transaction).all()
