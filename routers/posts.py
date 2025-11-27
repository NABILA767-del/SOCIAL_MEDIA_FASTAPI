from fastapi import APIRouter, Depends, Query, Header, Path, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Optional
from io import BytesIO
from fastapi.responses import StreamingResponse
from models import Post, User
from schemas import  PostCreate, PostRead, UserSummary,PostListResponse
from database import get_db
from utils import remove_accents, safe_str, format_date, choose_encoding, compress_response, validate_uuid,parse_accept_header,json2xml_bytes
from hashlib import md5
import json
from datetime import datetime
import uuid

router = APIRouter()

@router.get(
    "",
    response_model=PostListResponse,
    tags=["Posts"],
    summary="Retrieve all posts",
    description="""
Retrieves all posts with support for:
- Pagination (page, limit)
- Sorting (sort_by, sort_order)
- Filtering (owner_id, likes, tags, publishDate)
- Accent-insensitive search (search)
- HATEOAS: pagination links (first, prev, next, last) and self link
- i18n: Accept-Language (fr/en)
- Compression: Accept-Encoding
- Caching: ETag and Last-Modified
"""
)
def get_posts(
    page: int = Query(1, description="Numéro de page"),
    limit: int = Query(10, description="Nombre de posts par page"),
    sort_by: str = Query("publishDate", description="Champ pour trier"),
    sort_order: str = Query("desc", description="Ordre de tri: 'asc' ou 'desc'"),
    owner_id: Optional[str] = Query(None, description="Filtrer par ID du propriétaire"),
    likes: Optional[int] = Query(None, description="Filtrer par nombre de likes"),
    tags: Optional[str] = Query(None, description="Filtrer par tags (séparés par virgule)"),
    publishDate: Optional[str] = Query(None, description="Filtrer par date de publication"),
    search: Optional[str] = Query(None, description="Recherche dans le texte des posts"),
    accept: str = Header("application/json"),
    accept_encoding: str = Header("identity", description="Support de la compression"),
    accept_language: str = Header("en", description="Langue de la réponse"),
    if_none_match: Optional[str] = Header(None),
    if_modified_since: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    try:
        version, format_type = parse_accept_header(accept)
        lang = "fr" if accept_language.lower().startswith("fr") else "en"

        query = db.query(Post)
        if owner_id:
            query = query.filter(Post.owner_id == owner_id)
        if likes is not None:
            query = query.filter(Post.likes == likes)
        if publishDate:
            query = query.filter(Post.publishDate == publishDate)
        if tags:
            tag_list = [t.strip().lower() for t in tags.split(",")]
            for t in tag_list:
                query = query.filter(Post.tags.ilike(f'%"{t}"%'))
        posts_list = query.all()

        if search:
            s_norm = remove_accents(search).lower()
            posts_list = [p for p in posts_list if s_norm in remove_accents(safe_str(p.text)).lower()]

        if sort_by in ["text", "publishDate", "likes"]:
            reverse = sort_order.lower() == "desc"
            posts_list.sort(
                key=lambda p: remove_accents(safe_str(getattr(p, sort_by))).lower()
                if isinstance(getattr(p, sort_by), str) else getattr(p, sort_by),
                reverse=reverse
            )

        total = len(posts_list)
        start = (page - 1) * limit
        end = start + limit
        posts_page = posts_list[start:end]

        result = []
        for p in posts_page:
            owner = p.owner
            result.append({
                "id": safe_str(p.id),
                "text": safe_str(p.text),
                "image": safe_str(p.image),
                "likes": p.likes,
                "tags": json.loads(p.tags) if p.tags else [],
                "publishDate": format_date(p.publishDate, lang),
                "user": {
                    "id": safe_str(owner.id),
                    "firstName": safe_str(owner.firstName),
                    "lastName": safe_str(owner.lastName),
                    "title": safe_str(owner.title),
                    "picture": safe_str(owner.picture),
                    "links": [
    {"rel": "self", "href": f"/api/v1/posts/{p.id}"},
    {"rel": "users", "href": f"/api/v1/users/{owner.id}/posts"},
    {"rel": "comments", "href": f"/api/v1/posts/{p.id}/comments"}
                            ]
                }
            })

        last_page = max((total - 1) // limit + 1, 1)
        base_url = "/api/v1/posts"
        links = {
            "first": f"{base_url}?page=1&limit={limit}",
            "last": f"{base_url}?page={last_page}&limit={limit}",
        }
        if page > 1:
            links["prev"] = f"{base_url}?page={page-1}&limit={limit}"
        if page < last_page:
            links["next"] = f"{base_url}?page={page+1}&limit={limit}"
    

        response_data = {"api_version": "v1", "data": result, "total": total, "page": page, "limit": limit, "links": links}

        response_text = json.dumps(response_data, sort_keys=True)
        etag = md5(response_text.encode("utf-8")).hexdigest()
        last_modified = max([p.publishDate for p in posts_list], default=datetime.utcnow()).strftime("%a, %d %b %Y %H:%M:%S GMT")
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
            "Vary": "Accept-Language, Accept-Encoding"
        }
        return StreamingResponse(BytesIO(response_bytes), media_type=media_type, headers=headers)

    except Exception as e:
        return Response(content=json.dumps({"error": str(e)}), media_type="application/json", status_code=500)


@router.post(
    "",
    tags=["Posts"],
    summary="Create a new post",
    description="Creates a post with text, image, likes, and tags. Must specify owner_id.",
    response_model=PostRead
)
def create_post(post: PostCreate, db: Session = Depends(get_db)):
    owner = db.query(User).filter(User.id == post.owner_id).first()
    if not owner:
        raise HTTPException(404, detail="RESOURCE_NOT_FOUND:owner not found")

    db_post = Post(
        id=str(uuid.uuid4()),
        text=post.text,
        owner_id=post.owner_id,
        image=str(post.image) if post.image else None,
        likes=post.likes,
        tags=json.dumps(post.tags),
        publishDate=datetime.utcnow()
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)

    user_summary = UserSummary(
        id=owner.id,
        firstName=owner.firstName,
        lastName=owner.lastName,
        title=owner.title,
        picture=owner.picture,
        links=[
            {"rel": "self", "href": f"/api/v1/users/{owner.id}"}
        ]
    )

    post_dict = PostRead(
        id=db_post.id,
        text=db_post.text,
        image=db_post.image,
        likes=db_post.likes,
        tags=post.tags,
        publishDate=db_post.publishDate,
        user=user_summary
    ).dict()

    
    post_dict["links"] = [
        {"rel": "self", "href": f"/api/v1/posts/{db_post.id}"},
        {"rel": "owner", "href": f"/api/v1/users/{owner.id}"},
        {"rel": "comments", "href": f"/api/v1/posts/{db_post.id}/comments"}
    ]

    return post_dict


@router.put(
    "/{post_id}",
    tags=["Posts"],
    summary="Update a post",
    description="Updates an existing post. The owner_id cannot be changed.",
    response_model=PostRead
)
def update_post(post_id: str, post_data: PostCreate, db: Session = Depends(get_db)):
    validate_uuid(post_id, "post_id")
    db_post = db.query(Post).filter(Post.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND:post not found")
    if post_data.owner_id != db_post.owner_id:
        raise HTTPException(status_code=400, detail="Cannot change owner_id")

    db_post.text = post_data.text
    db_post.image = str(post_data.image) if post_data.image else db_post.image
    db_post.likes = post_data.likes or db_post.likes
    db_post.tags = json.dumps(post_data.tags) if post_data.tags else db_post.tags

    db.commit()
    db.refresh(db_post)

    owner = db_post.owner

    user_summary = UserSummary(
        id=owner.id,
        firstName=owner.firstName,
        lastName=owner.lastName,
        title=owner.title,
        picture=owner.picture
    )

    post_dict = PostRead(
        id=db_post.id,
        text=db_post.text,
        image=db_post.image,
        likes=db_post.likes,
        tags=json.loads(db_post.tags),
        publishDate=db_post.publishDate,
        user=user_summary
    ).dict()

    
    post_dict["links"] = [
        {"rel": "self", "href": f"/api/v1/posts/{db_post.id}"},
        {"rel": "owner", "href": f"/api/v1/users/{owner.id}"},
        {"rel": "comments", "href": f"/api/v1/posts/{db_post.id}/comments"}
    ]

    return post_dict


@router.get(
    "/{post_id}",
    tags=["Posts"],
    summary="Retrieve a post by ID",
    description="Retrieves a specific post by its ID.",
    response_model=PostRead
)
def get_post(
    post_id: str = Path(..., description="UUID of the post"),
    db: Session = Depends(get_db)
):

    validate_uuid(post_id, "post_id")


    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND: post not found")

    
    post_dict = {
        "id": safe_str(post.id),
        "text": safe_str(post.text),
        "image": safe_str(post.image),
        "likes": post.likes,
        "tags": json.loads(post.tags) if post.tags else [],
        "publishDate": format_date(post.publishDate, "en"),
        "user": {
            "id": safe_str(post.owner.id),
            "firstName": safe_str(post.owner.firstName),
            "lastName": safe_str(post.owner.lastName),
            "title": safe_str(post.owner.title),
            "picture": safe_str(post.owner.picture)
        },
        "links": [
            {"rel": "self", "href": f"/api/v1/posts/{post.id}"},
            {"rel": "owner", "href": f"/api/v1/users/{post.owner.id}"},
            {"rel": "comments", "href": f"/api/v1/posts/{post.id}/comments"}
        ]
    }

    return post_dict




@router.delete(
    "/{post_id}",
    tags=["Posts"],
    summary="Delete a post",
    description="Deletes a specific post by ID.",
)
def delete_post(post_id: str, db: Session = Depends(get_db)):
    validate_uuid(post_id,"post_id")
    db_post = db.query(Post).filter(Post.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND:post not found")
    db.delete(db_post)
    db.commit()
    return {"deleted_post_id": post_id}


@router.head(
    "",
    tags=["Posts"],
    summary="Check posts (HEAD)",
    description="Returns only status 200 to verify the posts resource."
)
def head_posts():
    return Response(status_code=200)

@router.options(
    "",
    tags=["Posts"],
    summary="OPTIONS for /posts",
    description="Returns the allowed HTTP methods for the /posts resource."
)
def options_posts():
    headers = {"Allow": "GET, POST, PUT, DELETE, HEAD, OPTIONS"}
    return Response(status_code=200, headers=headers)