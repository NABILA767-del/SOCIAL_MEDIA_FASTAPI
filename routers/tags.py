from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.orm import Session
import json

from models import Post
from schemas import TagWithLinks
from database import get_db

router = APIRouter()



@router.get(
    "",
    tags=["Tags"],
    summary="Retrieve the list of all tags with HATEOAS links",
    description="Returns all unique tags used across posts, with links to fetch posts by tag.",
    response_model=List[TagWithLinks]
)
def get_tags(db: Session = Depends(get_db)):
    posts = db.query(Post).all()
    all_tags = set()

    for p in posts:
        if p.tags:
            try:
                tags_list = json.loads(p.tags)
                if isinstance(tags_list, list):
                    for t in tags_list:
                        if isinstance(t, str):
                            all_tags.add(t)
            except Exception:
                continue

    result = []
    for t in sorted(all_tags):
        result.append({
            "tag": t,
            "links": [
                {"rel": "self", "href": f"/api/v1/tags/{t}/posts"}
            ]
        })

    return result