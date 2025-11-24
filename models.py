import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, declarative_base
from database import engine
Base = declarative_base()

class User(Base):
    __tablename__= "users"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    firstName = Column(String, nullable=False)
    lastName = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    dateOfBirth = Column(DateTime, nullable=True)
    registerDate = Column(DateTime, default=datetime.utcnow)
    phone = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    location = Column(Text, nullable=True)

    posts = relationship("Post", back_populates="owner", cascade="all, delete")
    comments = relationship("Comment", back_populates="owner", cascade="all, delete")


class Post(Base):
    __tablename__= "posts"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    text = Column(Text, nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    publishDate = Column(DateTime, default=datetime.utcnow)
    image = Column(String, nullable=True)
    likes = Column(Integer, default=0)
    link = Column(String(200), nullable=True)
    tags = Column(Text, nullable=True)

    owner = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post_relation", cascade="all, delete")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    message = Column(String, nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    post_id = Column(String, ForeignKey("posts.id"), nullable=False)
    publishDate = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="comments")
    post_relation = relationship("Post", back_populates="comments")


Base.metadata.create_all(bind=engine)