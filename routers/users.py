from fastapi import APIRouter, Depends, Query, Path, Header, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import uuid, json
from io import BytesIO
import hashlib 
from hashlib import md5
from fastapi.responses import JSONResponse,StreamingResponse
from database import get_db
from models import User
from schemas import UserCreate,UserRead,UserSummary
from utils import (
    validate_uuid,
    remove_accents,
    parse_accept_header,
    choose_encoding,
    compress_response,
    safe_str,
    format_date,
    is_valid_uuid,
    json2xml_bytes,
)

router = APIRouter()

@router.get("", summary="Retrieve all users", description="""
Retrieves all users with support for:
- Pagination (page, limit)
- Sorting (sort_by, sort_order)
- Filtering (firstName, lastName, email)
- Accent-insensitive search
- HATEOAS links for each user and collection
- i18n using Accept-Language (French/English)
- Compression using Accept-Encoding (gzip, br, identity)
- Cache: ETag / Last-Modified / 304
""")
def get_users(
    page: int = 1,
    limit: int = 10,
    sort_by: str = Query("firstName"),
    sort_order: str = Query("asc"),
    firstName: str | None = None,
    lastName: str | None = None,
    email: str | None = None,
    search: str | None = Query(None, description="Global search by name/first name/email"),
    accept: str = Header("application/json"),
    accept_encoding: str = Header("identity"),
    accept_language: str = Header("en"),
    if_none_match: str | None = Header(None),
    if_modified_since: str | None = Header(None),
    db: Session = Depends(get_db)
):
    try:
        version, format_type = parse_accept_header(accept)
        lang = "fr" if accept_language.lower().startswith("fr") else "en"

        query = db.query(User)
        if firstName:
            query = query.filter(User.firstName.ilike(f"%{remove_accents(firstName)}%"))
        if lastName:
            query = query.filter(User.lastName.ilike(f"%{remove_accents(lastName)}%"))
        if email:
            query = query.filter(User.email.ilike(f"%{email}%"))
        
        users_list = query.all()

        
        if search:
            s_norm = remove_accents(search).lower()
            users_list = [
                u for u in users_list
                if s_norm in remove_accents(u.firstName).lower()
                or s_norm in remove_accents(u.lastName).lower()
                or s_norm in remove_accents(u.email).lower()
            ]

        
        if sort_by in ["firstName", "lastName", "email", "registerDate", "dateOfBirth"]:
            reverse = sort_order.lower() == "desc"
            users_list.sort(
                key=lambda u: remove_accents(str(getattr(u, sort_by))).lower()
                if isinstance(getattr(u, sort_by), str)
                else getattr(u, sort_by),
                reverse=reverse
            )

        
        total = len(users_list)
        start = (page - 1) * limit
        end = start + limit
        users_page = users_list[start:end]

        result = []
        for u in users_page:
            location_dict = json.loads(u.location) if u.location else None
            user_dict = {
                "id": safe_str(u.id),
                "firstName": safe_str(u.firstName),
                "lastName": safe_str(u.lastName),
                "email": safe_str(u.email),
                "title": safe_str(u.title),
                "dateOfBirth": format_date(u.dateOfBirth, lang),
                "registerDate": format_date(u.registerDate, lang),
                "phone": safe_str(u.phone),
                "picture": safe_str(u.picture),
                "location": location_dict,
                "links": [
                    {"rel": "self", "href": f"/api/v1/users/{u.id}"},
                    {"rel": "posts", "href": f"/api/v1/users/{u.id}/posts"}
                ]
            }
            result.append(user_dict)

        collection_links = [
            {"rel": "first", "href": f"/api/v1/users?page=1&limit={limit}"},
            {"rel": "last", "href": f"/api/v1/users?page={(total - 1) // limit + 1}&limit={limit}"}
        ]
        if page > 1:
            collection_links.append({"rel": "prev", "href": f"/api/v1/users?page={page-1}&limit={limit}"})
        if page * limit < total:
            collection_links.append({"rel": "next", "href": f"/api/v1/users?page={page+1}&limit={limit}"})

        response_data = {
            "api_version": "v1",
            "data": result,
            "total": total,
            "page": page,
            "limit": limit,
            "links": collection_links
        }

        
        response_text = json.dumps(response_data, sort_keys=True)
        etag = md5(response_text.encode("utf-8")).hexdigest()
        last_modified = max(
            [u.registerDate for u in users_page], 
            default=datetime.utcnow()
        ).strftime("%a, %d %b %Y %H:%M:%S GMT")

        
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
            "Content-Encoding": chosen_encoding,
            "Content-Language": lang,
            "Cache-Control": "public, max-age=60, must-revalidate",
            "ETag": etag,
            "Last-Modified": last_modified,
            "Vary": "Accept-Encoding, Accept-Language"
        }

        return StreamingResponse(BytesIO(response_bytes), media_type=media_type, headers=headers)

    except Exception as e:
        return Response(
            content=json.dumps({"error": str(e)}),
            media_type="application/json",
            status_code=500
        )

@router.get("/{user_id}", response_model=UserRead, summary="Retrieve a user by ID")
def get_user(
    user_id: str = Path(..., description="UUID of the user to retrieve"),
    db: Session = Depends(get_db)
):
    if not is_valid_uuid(user_id):
        raise HTTPException(status_code=422, detail="PARAMS_NOT_VALID: user_id invalid UUID")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND: user not found")

    if user.location:
        user.location = json.loads(user.location)


    user_dict = {
        "id": safe_str(user.id),
        "firstName": safe_str(user.firstName),
        "lastName": safe_str(user.lastName),
        "email": safe_str(user.email),
        "title": safe_str(user.title),
        "dateOfBirth": format_date(user.dateOfBirth, "en"),
        "registerDate": format_date(user.registerDate, "en"),
        "phone": safe_str(user.phone),
        "picture": safe_str(user.picture),
        "location": user.location,
        "links": [
            {"rel": "self", "href": f"/api/v1/users/{user.id}"},
            {"rel": "posts", "href": f"/api/v1/users/{user.id}/posts"},
            {"rel": "comments", "href": f"/api/v1/users/{user.id}/comments"}
        ]
    }

    return user_dict


@router.post("", response_model=UserRead, summary="Create a new user")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    db_user = User(
        id=str(uuid.uuid4()),
        firstName=user.firstName,
        lastName=user.lastName,
        email=user.email,
        title=user.title,
        dateOfBirth=user.dateOfBirth,
        registerDate=datetime.utcnow(),
        phone=user.phone,
        picture=str(user.picture) if user.picture else None,
        location=json.dumps(user.location.dict()) if user.location else None
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    
    user_dict = {
        "id": db_user.id,
        "firstName": db_user.firstName,
        "lastName": db_user.lastName,
        "email": db_user.email,
        "title": db_user.title,
        "dateOfBirth": db_user.dateOfBirth.isoformat() if db_user.dateOfBirth else None,
        "registerDate": db_user.registerDate.isoformat(),
        "phone": db_user.phone,
        "picture": db_user.picture,
        "location": json.loads(db_user.location) if db_user.location else None,
        "links": [
            {"rel": "self", "href": f"/api/v1/users/{db_user.id}"},
            {"rel": "posts", "href": f"/api/v1/users/{db_user.id}/posts"},
            {"rel": "comments", "href": f"/api/v1/users/{db_user.id}/comments"}
        ]
    }

    return user_dict

@router.put("/{user_id}", response_model=UserRead, summary="Update an existing user")
def update_user(user_id: str, user_data: UserCreate, db: Session = Depends(get_db)):
    validate_uuid(user_id, "user_id")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND: user not found")
    if user.email != user_data.email:
        raise HTTPException(status_code=400, detail="Cannot update email")
    if isinstance(user_data.dateOfBirth, str):
        try:
            user_data.dateOfBirth = datetime.strptime(user_data.dateOfBirth, "%Y-%m-%d")
        except:
            raise HTTPException(status_code=400, detail="BODY_NOT_VALID: invalid date format, expected YYYY-MM-DD")

    user.firstName = user_data.firstName
    user.lastName = user_data.lastName
    user.title = user_data.title
    user.dateOfBirth = user_data.dateOfBirth
    user.phone = user_data.phone
    user.picture = str(user_data.picture) if user_data.picture else None
    user.location = json.dumps(user_data.location.dict()) if user_data.location else None

    db.commit()
    db.refresh(user)

    
    user_dict = {
        "id": user.id,
        "firstName": user.firstName,
        "lastName": user.lastName,
        "email": user.email,
        "title": user.title,
        "dateOfBirth": user.dateOfBirth.isoformat() if user.dateOfBirth else None,
        "registerDate": user.registerDate.isoformat(),
        "phone": user.phone,
        "picture": user.picture,
        "location": json.loads(user.location) if user.location else None,
        "links": [
            {"rel": "self", "href": f"/api/v1/users/{user.id}"},
            {"rel": "posts", "href": f"/api/v1/users/{user.id}/posts"},
            {"rel": "comments", "href": f"/api/v1/users/{user.id}/comments"}
        ]
    }

    return user_dict

@router.delete("/{user_id}", summary="Delete a user")
def delete_user(user_id: str = Path(..., description="ID of the user to delete"), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="RESOURCE_NOT_FOUND:user not found")
    db.delete(user)
    db.commit()
    return {"deleted_user_id": user_id}


@router.head("", summary="HEAD /users")
def head_users():
    return Response(status_code=200)


@router.options("", summary="OPTIONS /users")
def options_users():
    return {"methods": ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]}