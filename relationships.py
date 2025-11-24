
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
import json
from typing import List
from uuid import uuid4
from database import get_db
from models import User, Post, Comment
from utils import  validate_uuid
from schemas import UserSummary, PostRead, CommentRead, PaginatedResponse
router = APIRouter()

@router.get(
    "/api/v1/users/{user_id}/posts",
    tags=["Users Relationships"],
    summary="Retrieve posts of a user",
    description="""
Retrieves all posts of a given user with pagination.
Relations:
- Each post includes information about the user who created it.
Pagination:
- page: page number
- limit: number of items per page
""",
    response_model=PaginatedResponse[PostRead],
    responses={404: {"description": "User not found"}}
)
def get_user_posts(
    user_id: str,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    validate_uuid(user_id, "user_id")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="RESOURCE_NOT_FOUND:user not found")

    offset = (page - 1) * limit
    posts = db.query(Post).filter(Post.owner_id == user_id).offset(offset).limit(limit).all()
    total = db.query(Post).filter(Post.owner_id == user_id).count()

    result = []
    for p in posts:
        post_item = PostRead(
            id=p.id,
            text=p.text,
            tags=json.loads(p.tags) if p.tags else [],
            publishDate=p.publishDate,
            likes=p.likes,
            image=p.image,
            user=UserSummary(
                id=user.id,
                firstName=user.firstName,
                lastName=user.lastName,
                title=user.title,
                picture=user.picture
            )
        )
        
        post_item.links = [
            {"rel": "self", "href": f"/api/v1/posts/{p.id}"},
            {"rel": "owner", "href": f"/api/v1/users/{user.id}"}
        ]
        result.append(post_item)

    
    total_pages = (total + limit - 1) // limit
    collection_links = [
        {"rel": "first", "href": f"/api/v1/users/{user_id}/posts?page=1&limit={limit}"},
        {"rel": "last", "href": f"/api/v1/users/{user_id}/posts?page={total_pages}&limit={limit}"}
    ]
    if page > 1:
        collection_links.append({"rel": "prev", "href": f"/api/v1/users/{user_id}/posts?page={page-1}&limit={limit}"})
    if page < total_pages:
        collection_links.append({"rel": "next", "href": f"/api/v1/users/{user_id}/posts?page={page+1}&limit={limit}"})

    return PaginatedResponse(data=result, total=total, page=page, limit=limit, links=collection_links)

@router.get(
    "/api/v1/users/{user_id}/comments",
    tags=["Users Relationships"],
    summary="Retrieve comments of a user",
    description="""
Retrieves all comments posted by a given user with pagination.
Relations:
- Each comment includes post_id to indicate which post it belongs to.
Pagination:
- page: page number
- limit: number of items per page
""",
    response_model=PaginatedResponse[CommentRead],
    responses={404: {"description": "User not found"}}
)
def get_user_comments(
    user_id: str,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    validate_uuid(user_id, "user_id")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="RESOURCE_NOT_FOUND:user not found")

    offset = (page - 1) * limit
    comments = db.query(Comment).filter(Comment.owner_id == user_id).offset(offset).limit(limit).all()
    total = db.query(Comment).filter(Comment.owner_id == user_id).count()

    result = []
    for c in comments:
        result.append(
            CommentRead(
                id=c.id,
                message=c.message,
                owner_id=c.owner_id,
                post_id=c.post_id,
                publishDate=c.publishDate,
                owner=UserSummary(
                    id=user.id,
                    firstName=user.firstName,
                    lastName=user.lastName,
                    title=user.title,
                    picture=user.picture
                ),
                links=[
                    {"rel": "self", "href": f"/api/v1/comments/{c.id}"},
                    {"rel": "post", "href": f"/api/v1/posts/{c.post_id}"}
                ]
            )
        )

    total_pages = (total + limit - 1) // limit
    collection_links = [
        {"rel": "self", "href": f"/api/v1/users/{user_id}/comments?page={page}&limit={limit}"},
        {"rel": "first", "href": f"/api/v1/users/{user_id}/comments?page=1&limit={limit}"},
        {"rel": "last", "href": f"/api/v1/users/{user_id}/comments?page={total_pages}&limit={limit}"}
    ]
    if page > 1:
        collection_links.append({"rel": "prev", "href": f"/api/v1/users/{user_id}/comments?page={page-1}&limit={limit}"})
    if page < total_pages:
        collection_links.append({"rel": "next", "href": f"/api/v1/users/{user_id}/comments?page={page+1}&limit={limit}"})

    return PaginatedResponse(data=result, total=total, page=page, limit=limit, links=collection_links)


@router.get(
    "/api/v1/posts/{post_id}/comments",
    tags=["Posts Relationships"],
    summary="Retrieve comments of a post",
    description="""
Retrieves all comments of a given post with pagination.
Relations:
- Each comment includes owner_id to indicate which user created it.
Pagination:
- page: page number
- limit: number of items per page
""",
    response_model=PaginatedResponse[CommentRead],
    responses={404: {"description": "Post not found"}}
)
def get_post_comments(
    post_id: str,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    validate_uuid(post_id, "post_id")
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND:post not found")

    offset = (page - 1) * limit
    comments = db.query(Comment).filter(Comment.post_id == post_id).offset(offset).limit(limit).all()
    total = db.query(Comment).filter(Comment.post_id == post_id).count()

    result = []
    for c in comments:
        result.append(
            CommentRead(
                id=c.id,
                message=c.message,
                owner_id=c.owner_id,
                post_id=c.post_id,
                publishDate=c.publishDate,
                owner=UserSummary(
                    id=c.owner.id,
                    firstName=c.owner.firstName,
                    lastName=c.owner.lastName,
                    title=c.owner.title,
                    picture=c.owner.picture
                ) if c.owner else None,
                links=[
                    {"rel": "self", "href": f"/api/v1/comments/{c.id}"},
                    {"rel": "owner", "href": f"/api/v1/users/{c.owner_id}"} if c.owner_id else {}
                ]
            )
        )

    total_pages = (total + limit - 1) // limit
    collection_links = [
        {"rel": "self", "href": f"/api/v1/posts/{post_id}/comments?page={page}&limit={limit}"},
        {"rel": "first", "href": f"/api/v1/posts/{post_id}/comments?page=1&limit={limit}"},
        {"rel": "last", "href": f"/api/v1/posts/{post_id}/comments?page={total_pages}&limit={limit}"}
    ]
    if page > 1:
        collection_links.append({"rel": "prev", "href": f"/api/v1/posts/{post_id}/comments?page={page-1}&limit={limit}"})
    if page < total_pages:
        collection_links.append({"rel": "next", "href": f"/api/v1/posts/{post_id}/comments?page={page+1}&limit={limit}"})

    return PaginatedResponse(data=result, total=total, page=page, limit=limit, links=collection_links)


@router.get(
    "/api/v1/tags/{tagname}/posts",
    response_model=PaginatedResponse[PostRead],
    tags=["Tags Relationships"],
    summary="Retrieve all posts by tag",
    description="Returns all posts associated with a specific tag with pagination."
)
def get_posts_by_tag(
    tagname: str = Path(..., description="Tag name to filter"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Number of items per page"),
    db: Session = Depends(get_db)
):
    posts_query = db.query(Post).filter(Post.tags.ilike(f'%"{tagname.lower()}"%'))
    total = posts_query.count()
    offset = (page - 1) * limit
    posts = posts_query.offset(offset).limit(limit).all()

    if not posts:
        raise HTTPException(status_code=404, detail=f"No posts found for tag '{tagname}'")

    result = []
    for p in posts:
        result.append(
            PostRead(
                id=p.id,
                text=p.text,
                tags=json.loads(p.tags) if p.tags else [],
                publishDate=p.publishDate,
                likes=p.likes,
                image=p.image,
                user=UserSummary(
                    id=p.owner.id,
                    firstName=p.owner.firstName,
                    lastName=p.owner.lastName,
                    title=p.owner.title,
                    picture=p.owner.picture
                ),
                links=[
                    {"rel": "self", "href": f"/api/v1/posts/{p.id}"},
                    {"rel": "owner", "href": f"/api/v1/users/{p.owner.id}"}
                ]
            )
        )

    total_pages = (total + limit - 1) // limit
    collection_links = [
        {"rel": "self", "href": f"/api/v1/tags/{tagname}/posts?page={page}&limit={limit}"},
        {"rel": "first", "href": f"/api/v1/tags/{tagname}/posts?page=1&limit={limit}"},
        {"rel": "last", "href": f"/api/v1/tags/{tagname}/posts?page={total_pages}&limit={limit}"}
    ]
    if page > 1:
        collection_links.append({"rel": "prev", "href": f"/api/v1/tags/{tagname}/posts?page={page-1}&limit={limit}"})
    if page < total_pages:
        collection_links.append({"rel": "next", "href": f"/api/v1/tags/{tagname}/posts?page={page+1}&limit={limit}"})

    return PaginatedResponse(data=result, total=total, page=page, limit=limit, links=collection_links)