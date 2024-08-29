# db/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker

DATABASE_URL = 'sqlite:///db/esvitlo.db'
engine = create_engine(DATABASE_URL, pool_size=30, max_overflow=50)

SessionMain = scoped_session(sessionmaker(bind=engine))
#session = SessionMain()
