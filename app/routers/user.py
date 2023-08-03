# -*- coding: utf-8 -*-
from uuid import uuid4

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel
from tortoise.contrib.pydantic import pydantic_model_creator

from app.dependencies import validate_token
from app.models import Tenant, User
from app.utils import Status, password_hash

TenantPydantic = pydantic_model_creator(Tenant)
UserPydantic = pydantic_model_creator(User)
UserInPydantic = pydantic_model_creator(User, name="UserIn", exclude_readonly=True)
UserOutPydantic = pydantic_model_creator(User, name="UserOut", exclude=["password", "token"])
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


@router.get("/")
async def get_users() -> list[UserPydantic]:
    return await UserPydantic.from_queryset(User.all())


@router.post("/", status_code=201)
async def create_user(user: UserInPydantic) -> UserPydantic:
    new_user = await User.create(
        username=user.username,
        password=await password_hash(user.password),
        is_active=user.is_active,
        token=uuid4(),
        token_expiry=user.token_expiry,
        scopes=user.scopes,
    )
    return UserPydantic.from_orm(new_user)


@router.get("/{id}", responses={404: {"description": "User not found"}})
async def get_user(id: str, user: User = Depends(validate_token)) -> UserOutPydantic:
    if id != "me":
        user = await User.get(id=id)
    return UserOutPydantic.from_orm(user)


@router.patch("/{id}", responses={404: {"description": "User not found"}})
async def update_user(
    id: str, user: UserPatchPydantic, me_user: User = Depends(validate_token)
) -> UserOutPydantic:
    user_data = user.dict(exclude_unset=True)
    if user_data.get("password"):
        user_data["password"] = await password_hash(user_data["password"])
    logger.debug(user_data)
    if id != "me":
        user: User = await User.get(id=id)
    else:
        user = me_user
    await user.update_from_dict(user_data).save()
    return UserOutPydantic.from_orm(user)


@router.delete("/{id}", responses={404: {"description": "User not found"}})
async def delete_user(id: str, user: User = Depends(validate_token)) -> Status:
    if id != "me":
        user = await User.get(id=id)
    try:
        await user.delete()
    except Exception:
        return Status(message=f"Failed to delete user {id}", success=False)
    return Status(message=f"Deleted user {id}", success=True)


@router.get("/{id}/tenant/", responses={404: {"description": "User not found"}})
async def get_user_tenants(id: str, user: User = Depends(validate_token)) -> list[TenantPydantic]:
    if id != "me":
        user = await User.get(id=id)
    return await TenantPydantic.from_queryset(user.tenants.all())


@router.post(
    "/{id}/tenant/{tenant_id}", responses={404: {"description": "User or Tenant not found"}}
)
async def add_user_tenant(id: str, tenant_id: str, user: User = Depends(validate_token)) -> Status:
    if id != "me":
        user = await User.get(id=id)
    tenant = await Tenant.get(id=tenant_id)
    await user.tenants.add(tenant)
    return Status(message=f"Added tenant {tenant_id} to user {id}", success=True)


@router.delete(
    "/{id}/tenant/{tenant_id}", responses={404: {"description": "User or Tenant not found"}}
)
async def remove_user_tenant(
    id: str, tenant_id: str, user: User = Depends(validate_token)
) -> Status:
    if id != "me":
        user = await User.get(id=id)
    tenant = await Tenant.get(id=tenant_id)
    await user.tenants.remove(tenant)
    return Status(message=f"Removed tenant {tenant_id} from user {id}", success=True)
