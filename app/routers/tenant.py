# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel
from tortoise.contrib.pydantic import pydantic_model_creator

from app.dependencies import validate_admin
from app.models import Tenant
from app.utils import Status, graphql_request

TenantPydantic = pydantic_model_creator(Tenant)
TenantInPydantic = pydantic_model_creator(Tenant, name="TenantIn", include=("slug",))
TenantPatchPydantic = pydantic_model_creator(
    Tenant,
    name="TenantPatch",
    exclude_readonly=True,
    optional=list(TenantPydantic.schema()["properties"].keys()),
)

router = APIRouter(prefix="/tenant", tags=["tenant"], dependencies=[Depends(validate_admin)])


class LoginResponse(BaseModel):
    token: str
    success: bool


@router.get("/")
async def get_tenants() -> list[TenantPydantic]:
    return await TenantPydantic.from_queryset(Tenant.all())


@router.post("/", status_code=201)
async def create_tenant(tenant: TenantInPydantic) -> TenantPydantic:
    try:
        query = """
            mutation CreateTenant($input: create_tenant_input!) {
                create_tenant(input: $input) {
                    id
                }
            }
        """
        variables = {"input": {"name": tenant.slug, "slug": tenant.slug}}
        operations = {"query": query, "variables": variables}
        response = await graphql_request(operations)
        response.raise_for_status()
        tenant_id = response.json()["data"]["create_tenant"]["id"]
    except Exception as exc:
        raise exc
    new_tenant = await Tenant.create(
        id=tenant_id,
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
