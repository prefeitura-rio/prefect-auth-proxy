# -*- coding: utf-8 -*-
from uuid import uuid4

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel
from tortoise.contrib.pydantic import pydantic_model_creator

from app.dependencies import validate_token
from app.models import User
from app.utils import Status, password_hash

UserPydantic = pydantic_model_creator(User)
UserInPydantic = pydantic_model_creator(User, name="UserIn", exclude_readonly=True)
UserPatchPydantic = pydantic_model_creator(
    User,
    name="UserPatch",
    exclude_readonly=True,
    optional=list(UserPydantic.schema()["properties"].keys()),
)

router = APIRouter(prefix="/user", tags=["user"], dependencies=[Depends(validate_token)])


class LoginResponse(BaseModel):
    token: str
    success: bool


@router.post("/create/", status_code=201)
async def create_user(user: UserInPydantic) -> UserPydantic:
    new_user = await User.create(
        username=user.username,
        password=password_hash(user.password),
        is_active=user.is_active,
        token=uuid4(),
        token_expiry=user.token_expiry,
        scopes=user.scopes,
    )
    return UserPydantic.from_orm(new_user)


@router.patch("/{id}", responses={404: {"description": "User not found"}})
async def update_user(id: str, user: UserPatchPydantic) -> UserPydantic:
    user_data = user.dict(exclude_unset=True)
    if user_data.get("password"):
        user_data["password"] = password_hash(user_data["password"])
    logger.debug(user_data)
    user: User = await User.get(id=id)
    await user.update_from_dict(user_data).save()
    return UserPydantic.from_orm(user)


@router.delete("/{id}", responses={404: {"description": "User not found"}})
async def delete_user(id: str) -> Status:
    user = await User.get(id=id)
    try:
        await user.delete()
    except Exception:
        return Status(message=f"Failed to delete user {id}", success=False)
    return Status(message=f"Deleted user {id}", success=True)
