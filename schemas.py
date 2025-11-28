import re
from datetime import datetime, date
from typing import List, Optional,TypeVar, Generic
from pydantic import BaseModel, EmailStr, HttpUrl, field_validator, ConfigDict
from pydantic.generics import GenericModel
from fastapi import Header, HTTPException


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
    links: Optional[List[Link]] = []

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


class PostResponse(BaseModel):
    id: str
    text: str
    image: Optional[str]
    likes: int
    tags: List[str]
    publishDate: str
    user: UserSummary


class PostListResponse(BaseModel):
    data: List[PostResponse]
    total: int
    page: int
    limit: int
    links: List[Link] = []


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
    links: Optional[List[Link]] = []

    model_config = ConfigDict(from_attributes=True)


class CommentResponse(BaseModel):
    id: str
    message: str
    post_id: str
    publishDate: datetime
    owner: Optional[UserSummary] = None



class TagWithLinks(BaseModel):
    tag: str
    links: List[Link]


class ParamsNotValidException(HTTPException):
    def init(self, param_name: str):
        super().init(
            status_code=400,
            detail=f"PARAMS_NOT_VALID: {param_name} format invalid"
        )