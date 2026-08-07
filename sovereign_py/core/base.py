"""
Neutral SQLAlchemy declarative base.

Exists to break the circular import between core/database.py (which needs
Base to define its tables) and core/enhanced_models.py (which needs Base
from database.py to define its own tables, but database.py can't import
enhanced_models.py back without a cycle). Both modules import Base from
here instead of from each other.
"""

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
