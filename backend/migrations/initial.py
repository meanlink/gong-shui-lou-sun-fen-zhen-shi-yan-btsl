from sqlalchemy import inspect, text
from src.config.database import Base, engine
from src import models
JOB_COLUMNS = [
    ('kind', "VARCHAR(20) NOT NULL DEFAULT 'normal'"),
    ('attempt', "INTEGER NOT NULL DEFAULT 0"),
    ('executor', "VARCHAR(80) NOT NULL DEFAULT ''"),
    ('claimed_at', "DOUBLE PRECISION"),
    ('queue_note', "VARCHAR(300) NOT NULL DEFAULT ''"),
]
def migrate():
    Base.metadata.create_all(engine)
    # 旧库就地补列：既有试验保留原状，照常查看
    insp = inspect(engine)
    if 'jobs' in insp.get_table_names():
        have = {c['name'] for c in insp.get_columns('jobs')}
        with engine.begin() as conn:
            for name, ddl in JOB_COLUMNS:
                if name not in have:
                    conn.execute(text(f'ALTER TABLE jobs ADD COLUMN {name} {ddl}'))
if __name__=='__main__':migrate()
