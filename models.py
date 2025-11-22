import uuid
import json
from datetime import datetime, date
from typing import List, Optional, Dict, TypeVar, Generic
import re
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, declarative_base
from pydantic import BaseModel, EmailStr, HttpUrl, field_validator,ConfigDict
from pydantic.generics import GenericModel
from fastapi import Header, HTTPException

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


T = TypeVar("T")

class PaginatedResponse(GenericModel, Generic[T]):
    data: List[T]
    total: int
    page: int
    limit: int


class Location(BaseModel):
    street: Optional[str] = None
    city: str
    state: Optional[str] = None
    country: str
    timezone: Optional[str] = None

    @field_validator('timezone')
    def check_timezone(cls, v):
        if v is None:
            return v
        pattern = r'^(\+|-)([01]\d|2[0-3]):[0-5]\d$'
        if not re.match(pattern, v):
            raise ValueError("timezone must be in format +HH:MM or -HH:MM")
        return v


class Link(BaseModel):
    rel: str
    href: str


class UserCreate(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    title: str
    dateOfBirth: Optional[date] = None
    phone: Optional[str] = None
    picture: Optional[HttpUrl] = None
    location: Optional[Location] = None


class UserRead(UserCreate):
    id: str
    registerDate: datetime

    model_config = ConfigDict(from_attributes=True)


class UserSummary(BaseModel):
    id: str
    firstName: str
    lastName: str
    title: Optional[str] = None
    picture: Optional[str] = None


class UserLinks(BaseModel):
    rel: str
    href: str


class UserData(UserCreate):
    links:List[Link]=[]

class UserData(BaseModel):
    id:str
    firstName:str
    lastName:str
    email:str
    title:Optional[str]=None
    dateOfBirth:Optional[str]=None
    registerDate:Optional[str]=None
    phone:Optional[str]=None
    picture:Optional[str]=None
    location:Optional[Dict]=None
    links:List[UserLinks]=[]
    


class UsersResponse(BaseModel):
    data: List[UserData]
    total: int
    page: int
    limit: int
    links: List[UserLinks] = []


class PostCreate(BaseModel):
    text: str
    owner_id: str
    tags: Optional[List[str]] = []
    image: Optional[HttpUrl] = None
    link: Optional[HttpUrl] = None
    likes: Optional[int] = 0


class PostRead(BaseModel):
    id: str
    text: str
    tags: List[str]
    publishDate: datetime
    likes: int
    image: Optional[HttpUrl] = None
    user: UserSummary

    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    message: str
    owner_id: str
    post_id: str


class CommentRead(BaseModel):
    id: str
    message: str
    owner: UserSummary
    post_id: str
    publishDate: datetime
    model_config = ConfigDict(from_attributes=True)
class UserLinks(BaseModel):
    rel:str
    href:str

class PostResponse(BaseModel):
    id:str
    text:str
    image:Optional[str]
    likes:int
    tags:List[str]
    publishDate:str
    user:UserSummary

class PostListResponse(BaseModel):
    data:List[PostResponse]
    total:int
    page:int
    limit:int
    links:List[Link]=[]

class ParamsNotValidException(HTTPException):
    def __init__(self, param_name: str):
        super().__init__(
            status_code=400,
            detail=f"PARAMS_NOT_VALID: {param_name} format invalid"
        )
class TagResponse(BaseModel):
    tags: List[str]
def get_api_version(accept: Optional[str] = Header(None)):
    if accept and "vnd.myapp.v1" in accept:
        return "v1"
    elif accept and "vnd.myapp.v2" in accept:
        return "v2"
    return "default"
class CommentResponse(BaseModel):
    id: str
    message: str
    post_id: str
    publishDate: datetime
    owner: Optional[UserSummary] = None

class PaginatedUserResponse(PaginatedResponse[UserRead]):
    api_version: str


class PaginatedPostResponse(PaginatedResponse[PostRead]):
    api_version: str


class PaginatedCommentResponse(PaginatedResponse[CommentRead]):
    api_version: str