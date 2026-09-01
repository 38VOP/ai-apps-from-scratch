from sqlalchemy import create_engine, text
import os

db = os.path.join(os.path.dirname(os.path.abspath('.')), 'data', 'catalog.db')
engine = create_engine(f'sqlite:///{db}')
with engine.connect() as conn:
    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    tables = [r[0] for r in result]
    print('TABLES:', tables)
    for t in tables:
        cnt = conn.execute(text(f'SELECT count(*) FROM {t}')).scalar()
        print(f'  {t}: {cnt} rows')
