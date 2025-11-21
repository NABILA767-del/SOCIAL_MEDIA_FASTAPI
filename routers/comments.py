from fastapi import APIRouter, Depends, Query, Header, Path, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from io import BytesIO
from datetime import datetime
import uuid
import json
from hashlib import md5
import unicodedata

from models import Comment, User, Post, CommentCreate, CommentRead, UserSummary
from database import get_db
from utils import remove_accents, safe_str, format_date, choose_encoding, compress_response, validate_uuid, parse_accept_header,json2xml_bytes

router = APIRouter()

@router.get(
    "",
    tags=["Comments"],
    summary="Retrieve the list of comments",
    description="""
Retrieves all comments with support for:
- Pagination (page, limit)
- Sorting (sort_by, sort_order)
- Filtering (owner_id, post_id, publishDate)
- Accent-insensitive search (search)
- HATEOAS: self and pagination links
- Cache: If-None-Match, If-Modified-Since
- Compression: Accept-Encoding
- i18n: Accept-Language for date/format
""",
    response_model=dict
)
def get_comments(
    page: int = 1,
    limit: int = 10,
    sort_by: str = Query("publishDate", description="Champ pour trier"),
    sort_order: str = Query("desc", description="Ordre de tri: asc/desc"),
    owner_id: Optional[str] = None,
    post_id: Optional[str] = None,
    publishDate: Optional[str] = None,
    search: Optional[str] = None,
    accept_encoding: str = Header("identity", description="Compression préférée du client"),
    accept_language: str = Header("en", description="Langue de la réponse"),
    accept: str = Header("application/json"),
    if_none_match: Optional[str] = Header(None, description="ETag pour cache"),
    if_modified_since: Optional[str] = Header(None, description="Dernière date connue"),
    db: Session = Depends(get_db)
):
    try:
        version, format_type = parse_accept_header(accept)
        lang = "fr" if accept_language.lower().startswith("fr") else "en"

        query = db.query(Comment)
        if owner_id:
            query = query.filter(Comment.owner_id == owner_id)
        if post_id:
            query = query.filter(Comment.post_id == post_id)
        if publishDate:
            query = query.filter(Comment.publishDate == publishDate)
        comments_list = query.all()

        if search:
            s_norm = remove_accents(search).lower()
            comments_list = [
                c for c in comments_list
                if s_norm in remove_accents(safe_str(c.message)).lower()
            ]

        if sort_by in ["message", "publishDate"]:
            reverse = sort_order.lower() == "desc"
            comments_list.sort(
                key=lambda c: remove_accents(safe_str(getattr(c, sort_by))).lower()
                if isinstance(getattr(c, sort_by), str) else getattr(c, sort_by),
                reverse=reverse
            )

        total = len(comments_list)
        start = (page - 1) * limit
        end = start + limit
        comments_page = comments_list[start:end]

        result = []
        for c in comments_page:
            owner = c.owner
            result.append({
                "id": safe_str(c.id),
                "message": safe_str(c.message),
                "post_id": safe_str(c.post_id),
                "publishDate": format_date(c.publishDate, lang),
                "owner": {
                    "id": safe_str(owner.id),
                    "firstName": safe_str(owner.firstName),
                    "lastName": safe_str(owner.lastName),
                    "title": safe_str(owner.title),
                    "picture": safe_str(owner.picture)
                },
                "links": {
                    "self": f"/comments/{c.id}"
                }
            })

        last_page = max((total - 1) // limit + 1, 1)
        base_url = "/api/v1/comments"
        links = {
            "self": f"{base_url}?page={page}&limit={limit}",
            "first": f"{base_url}?page=1&limit={limit}",
            "last": f"{base_url}?page={last_page}&limit={limit}",
        }
        if page > 1:
            links["prev"] = f"{base_url}?page={page-1}&limit={limit}"
        if page < last_page:
            links["next"] = f"{base_url}?page={page+1}&limit={limit}"

        response_data = {
            "api_version": "v1",
            "data": result,
            "total": total,
            "page": page,
            "limit": limit,
            "links": links
        }

        response_text = json.dumps(response_data, sort_keys=True)
        etag = md5(response_text.encode("utf-8")).hexdigest()
        last_modified = max([c.publishDate for c in comments_list], default=datetime.utcnow()).strftime("%a, %d %b %Y %H:%M:%S GMT")
        if if_none_match == etag or (if_modified_since and if_modified_since == last_modified):
            return StreamingResponse(BytesIO(b""), status_code=304)
        if format_type == "application/xml":
            response_bytes = json2xml_bytes(response_data)
            media_type = "application/xml"
        else:
            response_bytes = json.dumps(response_data, ensure_ascii=False).encode("utf-8")
            media_type = "application/json"

        chosen_encoding = choose_encoding(accept_encoding)
        response_bytes = compress_response(response_bytes, chosen_encoding)

        headers = {
            "Content-Type": media_type,
            "Cache-Control": "public, max-age=60, must-revalidate",
            "ETag": etag,
            "Last-Modified": last_modified,
            "Content-Encoding": chosen_encoding,
            "Content-Language": lang,
            "Vary": "Accept-Encoding, Accept-Language"
        }

        return StreamingResponse(BytesIO(response_bytes), media_type=media_type, headers=headers)

    except Exception as e:
        return Response(
            content=json.dumps({"error": str(e)}),
            media_type="application/json",
            status_code=500
        )


@router.post(
    "",
    tags=["Comments"],
    summary="Create a comment",
    description="Creates a comment linked to an existing post and an existing user.",
    response_model=CommentRead
)
def create_comment(comment: CommentCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == comment.owner_id).first()
    post = db.query(Post).filter(Post.id == comment.post_id).first()
    if not user or not post:
        raise HTTPException(404, detail="RESOURCE_NOT_FOUND:user or post not found")

    db_comment = Comment(
        id=str(uuid.uuid4()),
        message=comment.message,
        owner_id=comment.owner_id,
        post_id=comment.post_id
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    owner = db_comment.owner
    return CommentRead(
        id=db_comment.id,
        message=db_comment.message,
        post_id=db_comment.post_id,
        publishDate=db_comment.publishDate.isoformat(),
        owner=UserSummary(
            id=owner.id,
            firstName=owner.firstName,
            lastName=owner.lastName,
            title=owner.title,
            picture=owner.picture
        )
    )


@router.get(
    "/{comment_id}",
    tags=["Comments"],
    summary="Retrieve a comment by ID",
    description="Retrieves a specific comment by its identifier.",
    response_model=CommentRead
)
def get_comment(comment_id: str, db: Session = Depends(get_db)):
    validate_uuid(comment_id, "comment_id")
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND: comment not found")
    return comment


@router.put(
    "/{comment_id}",
    tags=["Comments"],
    summary="Update a comment",
    description="Updates an existing comment. The owner_id cannot be changed.",
    response_model=CommentRead
)
def update_comment(comment_id: str, comment: CommentCreate, db: Session = Depends(get_db)):
    validate_uuid(comment_id, "comment_id")
    db_comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(404, detail="RESOURCE_NOT_FOUND:comment not found")
    if comment.owner_id != db_comment.owner_id:
        raise HTTPException(400, detail="Cannot change owner")
    db_comment.message = comment.message
    db.commit()
    db.refresh(db_comment)
    return db_comment


@router.delete(
    "/{comment_id}",
    tags=["Comments"],
    summary="Delete a comment",
    description="Deletes a specific comment by ID."
)
def delete_comment(comment_id: str, db: Session = Depends(get_db)):
    validate_uuid(comment_id,"comment_id")
    db_comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(404, detail="RESOURCE_NOT_FOUND:comment not found")
    db.delete(db_comment)
    db.commit()
    return {"deleted_comment_id": comment_id}


@router.head(
    "",
    tags=["Comments"],
    summary="Check comments (HEAD)",
    description="Returns only status 200 to verify the comments resource."
)
def head_comments():
    return Response(status_code=200)


@router.options(
    "",
    tags=["Comments"],
    summary="OPTIONS for /comments",
    description="Returns the allowed HTTP methods for the /comments resource."
)
def options_comments():
    headers = {"Allow": "GET, POST, PUT, DELETE, HEAD, OPTIONS"}
    return Response(status_code=200, headers=headers)