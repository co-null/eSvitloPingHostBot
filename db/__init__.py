# db/__init__.py
from .database import engine
from .models import Base

Base.metadata.create_all(bind=engine)