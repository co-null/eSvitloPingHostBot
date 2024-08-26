# db/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = 'sqlite:///db/esvitlo.db'
engine = create_engine(DATABASE_URL)

SessionMain = sessionmaker(bind=engine)
session = SessionMain()
