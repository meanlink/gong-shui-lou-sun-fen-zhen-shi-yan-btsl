from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .settings import DATABASE_URL

class Base(DeclarativeBase):
    pass

connect_args = {'timeout': 30} if DATABASE_URL.startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800, connect_args=connect_args)
Session = sessionmaker(engine, expire_on_commit=False)

def get_db():
    with Session() as db:
        yield db
