from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class Site(Base):
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)

    nodes: Mapped[list["Node"]] = relationship(
        back_populates="site", 
        cascade="all, delete-orphan"
    )
    tokens: Mapped[list["RegistrationToken"]] = relationship(
        back_populates="site", 
        cascade="all, delete-orphan"
    )