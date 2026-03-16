"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, status

from ndai.api.dependencies import create_access_token
from ndai.api.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter()

# In-memory store for MVP (replaced by DB in production)
_users: dict[str, dict] = {}


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    if request.email in _users:
        raise HTTPException(status_code=400, detail="Email already registered")
    if request.role not in ("seller", "buyer"):
        raise HTTPException(status_code=400, detail="Role must be 'seller' or 'buyer'")

    import uuid
    from passlib.hash import bcrypt

    user_id = str(uuid.uuid4())
    _users[request.email] = {
        "id": user_id,
        "email": request.email,
        "password_hash": bcrypt.hash(request.password),
        "role": request.role,
        "display_name": request.display_name,
    }
    token = create_access_token(user_id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    from passlib.hash import bcrypt

    user = _users.get(request.email)
    if not user or not bcrypt.verify(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(user["id"])
    return TokenResponse(access_token=token)
