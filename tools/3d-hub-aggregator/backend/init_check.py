from sqlalchemy import create_engine, text
import os

db_path = os.path.join(os.path.dirname(os.path.abspath('.')), 'data', 'catalog.db')
engine = create_engine(f'sqlite:///{db_path}')

# Try to create all tables from metadata
from database import Base, engine as db_engine
Base.metadata.create_all(bind=db_engine)

with db_engine.connect() as conn:
    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    tables = [r[0] for r in result]
    print('TABLES_AFTER_CREATE:', tables)
    for t in tables:
        cnt = conn.execute(text(f'SELECT count(*) FROM {t}')).scalar()
        print(f'  {t}: {cnt} rows')
