from sqlalchemy import create_engine, text

URL = "postgresql+psycopg2://ckchurch_app:cksecret@localhost:5432/ckchurch_db"
engine = create_engine(URL)

with engine.begin() as conn:
    cur = conn.execute(text("SELECT version_num FROM alembic_version"))
    before = cur.scalar_one()
    print("Before:", before)
    conn.execute(text("UPDATE alembic_version SET version_num='77c6958025b9'"))
    cur = conn.execute(text("SELECT version_num FROM alembic_version"))
    after = cur.scalar_one()
    print("After :", after)
