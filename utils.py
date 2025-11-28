
import uuid
import json
import gzip
import brotli
import hashlib
import unicodedata
from datetime import datetime
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from dicttoxml import dicttoxml
from schemas import ParamsNotValidException

def validate_uuid(param_value: str, param_name: str):
    """Check that the value is a valid UUID"""
    try:
        uuid.UUID(param_value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"PARAMS_NOT_VALID: {param_name} format invalid"
        )

def is_valid_uuid(val: str) -> bool:
    """Returns True if val is a valid UUID"""
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False


def remove_accents(s: str) -> str:
    """Remove the accents from a string"""
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')
def json2xml_bytes(data: dict) -> bytes:
    """Converts a Python dictionary into binary XML."""
    return dicttoxml(data, custom_root='response', attr_type=False)

def parse_accept_header(accept: str = None):
    """
    Parse the Accept header to detect the API version and format. Choose the format with the highest q value.
    """
    version = "default"
    format_type = "application/json"

    if accept:
        items = []
        for part in accept.split(","):
            parts = part.strip().split(";")
            media_type = parts[0].strip()
            q = 1.0
            for param in parts[1:]:
                if param.strip().startswith("q="):
                    try:
                        q = float(param.strip()[2:])
                    except:
                        pass
            items.append((media_type, q))

        items.sort(key=lambda x: x[1], reverse=True)
        best_media = items[0][0]

        
        if "vnd.myapp.v1" in best_media:
            version = "v1"
        elif "vnd.myapp.v2" in best_media:
            version = "v2"

        
        if "xml" in best_media.lower():
            format_type = "application/xml"
        elif "json" in best_media.lower():
            format_type = "application/json"

    return version, format_type


def generate_etag(data: dict) -> str:
    """Create an ETag based on the hash of the JSON content"""
    json_bytes = json.dumps(data, sort_keys=True).encode('utf-8')
    return hashlib.md5(json_bytes).hexdigest()


def choose_encoding(accept_encoding: str) -> str:
    """
    Select the best compression algorithm according to Accept-Encoding and q. Supports br, gzip, identity.
    """
    if not accept_encoding:
        return "identity"

    encodings = []

    for part in accept_encoding.split(","):
        part = part.strip()
        if ";" in part:
            alg, *params = part.split(";")
            q = 1.0
            for p in params:
                p = p.strip()
                if p.startswith("q="):
                    try:
                        q = float(p[2:])
                    except ValueError:
                        q = 0.0
        else:
            alg = part
            q = 1.0
        encodings.append((alg.lower(), q))

    
    encodings.sort(key=lambda x: x[1], reverse=True)

    
    for alg, _ in encodings:
        if alg in ["br", "gzip", "identity"]:
            return alg

    return "identity"

def compress_response(data: bytes, encoding: str) -> bytes:
    """Compress the response according to the chosen encoding"""
    if encoding == "br":
        return brotli.compress(data)
    elif encoding == "gzip":
        return gzip.compress(data)
    return data


def safe_str(value):
    """Converts a value to a string or None if invalid"""
    if value is None:
        return None
    try:
        return str(value)
    except Exception:
        return None


def format_date(dt: datetime, lang: str) -> str:
    """Format a date according to the language"""
    if not dt:
        return None
    if lang.startswith("fr"):
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def quick_translate(val, lang: str = "en"):
    """Quick recursive translation of French values into English"""
    translations = {
        "Bonjour": "Hello",
        "Utilisateur": "User",
        "Nom": "Name",
        "Prénom": "First Name",
        "Titre": "Title",
        "Lieu": "Location",
        "Rue": "Street",
        "Ville": "City",
        "État": "State",
        "Pays": "Country",
        "Fuseau horaire": "Timezone",
        "Texte": "Text",
        "Image": "Image",
        "Likes": "Likes",
        "Date de publication": "Publish Date",
        "Commentaire": "Message",
        "Auteur": "Owner",
    }

    if not val:
        return val
    if isinstance(val, str):
        if lang == "en":
            for fr, en in translations.items():
                val = val.replace(fr, en)
        return val
    elif isinstance(val, dict):
        return {k: quick_translate(v, lang) for k, v in val.items()}
    elif isinstance(val, list):
        return [quick_translate(i, lang) for i in val]
    return val

def configure_cors(app: FastAPI):
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://mon-frontend.com",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def resource_exists(instance, resource_name: str):
    if not instance:
        raise HTTPException(
            status_code=404,
            detail=f"RESOURCE_NOT_FOUND: {resource_name} not found"
        )


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(Exception)
    async def server_error_handler(request: Request, exc: Exception):
        print(f"Server error: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "SERVER_ERROR: something went wrong on the server"}
        )

    @app.exception_handler(StarletteHTTPException)
    async def path_not_found_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404 and exc.detail == "Not Found":
            return JSONResponse(
                status_code=404,
                content={"detail": "PATH_NOT_FOUND: the requested URL does not exist"}
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return JSONResponse(
            status_code=400,
            content={"detail": "BODY_NOT_VALID: check JSON format or fields"}
        )
    @app.exception_handler(ParamsNotValidException)
    async def params_not_valid_handler(request: Request, exc: ParamsNotValidException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    