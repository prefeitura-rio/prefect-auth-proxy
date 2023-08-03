# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel
from tortoise.contrib.pydantic import pydantic_model_creator

from app.dependencies import validate_token
from app.models import Tenant
from app.utils import Status

TenantPydantic = pydantic_model_creator(Tenant)
TenantInPydantic = pydantic_model_creator(Tenant, name="TenantIn", exclude_readonly=True)
TenantPatchPydantic = pydantic_model_creator(
    Tenant,
    name="TenantPatch",
    exclude_readonly=True,
    optional=list(TenantPydantic.schema()["properties"].keys()),
)

router = APIRouter(prefix="/tenant", tags=["tenant"], dependencies=[Depends(validate_token)])


class LoginResponse(BaseModel):
    token: str
    success: bool


@router.get("/")
async def get_tenants() -> list[TenantPydantic]:
    return await TenantPydantic.from_queryset(Tenant.all())


@router.post("/create/", status_code=201)
async def create_tenant(tenant: TenantPydantic) -> TenantPydantic:
    new_tenant = await Tenant.create(
        id=tenant.id,
        slug=tenant.slug,
    )
    return TenantPydantic.from_orm(new_tenant)


@router.patch("/{id}", responses={404: {"description": "Tenant not found"}})
async def update_tenant(id: str, tenant: TenantPatchPydantic) -> TenantPydantic:
    tenant_data = tenant.dict(exclude_unset=True)
    logger.debug(tenant_data)
    tenant: Tenant = await Tenant.get(id=id)
    await tenant.update_from_dict(tenant_data).save()
    return TenantPydantic.from_orm(tenant)


@router.delete("/{id}", responses={404: {"description": "Tenant not found"}})
async def delete_tenant(id: str) -> Status:
    tenant = await Tenant.get(id=id)
    try:
        await tenant.delete()
    except Exception:
        return Status(message=f"Failed to delete tenant {id}", success=False)
    return Status(message=f"Deleted tenant {id}", success=True)
