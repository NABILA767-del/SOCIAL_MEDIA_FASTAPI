from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.orm import Session
import json

from models import Post,TagResponse
from database import get_db

router = APIRouter()

@router.get(
    "",
    tags=["Tags"],
    summary="Retrieve the list of all tags",
    description="""
Returns a list of all unique tags used across posts.

How it works:
- Reads the 'tags' field from every post.
- Extracts all tags (strings inside the JSON list).
- Removes duplicates.
""",
    response_model=List[str]
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

    return sorted(list(all_tags))