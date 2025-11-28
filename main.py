from fastapi import FastAPI
from utils import configure_cors, register_exception_handlers
from database import Base,engine
from routers import users,posts,comments,tags
from relationships import router as relationships_router
app=FastAPI(title="Social Media API")
Base.metadata.create_all(bind=engine)

app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(posts.router, prefix="/api/v1/posts", tags=["Posts"])
app.include_router(comments.router, prefix="/api/v1/comments", tags=["Comments"])
app.include_router(tags.router, prefix="/api/v1/tags", tags=["Tags"])
app.include_router(relationships_router)
configure_cors(app)
register_exception_handlers(app)






