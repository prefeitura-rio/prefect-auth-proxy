# -*- coding: utf-8 -*-
import json

import httpx
from fastapi import APIRouter, Depends, Request, Response
from loguru import logger

from app import config
from app.dependencies import validate_token
from app.models import Tenant, User
from app.utils import graphql_request, modify_operations

router = APIRouter(prefix="/proxy", tags=["proxy"])  # , dependencies=[Depends(validate_token)])


@router.options("", include_in_schema=False)
@router.options("/")
async def options():
    """
    Proxies requests to the Prefect API.
    """
    async with httpx.AsyncClient() as client:
        response = await client.options(
            config.PREFECT_API_URL,
        )
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response.headers,
    )


@router.post("", include_in_schema=False)
@router.post("/")
async def proxy(request: Request, user: User = Depends(validate_token)):
    """
    Proxies requests to the Prefect API.
    """
    # Parse the request body as JSON
    try:
        body = await request.body()
        body = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON: {body}")
        return Response(
            content="Invalid JSON",
            status_code=400,
        )
    # Assert that we have the tenant ID header
    headers = dict(request.headers)
    if not headers.get("x-prefect-tenant-id") or headers["x-prefect-tenant-id"] == "null":
        logger.error(f"Missing tenant ID in headers: {headers}")
        return Response(
            content=json.dumps({"error": "Please provide tenant ID"}),
            status_code=400,
        )
    tenant_id = headers["x-prefect-tenant-id"]
    # Verify API token and tenant ID permissions
    tenant: Tenant = await Tenant.get_or_none(id=tenant_id)
    if not tenant:
        logger.error(f"Invalid tenant ID: {tenant_id}")
        return Response(
            content=json.dumps({"error": "Invalid tenant ID"}),
            status_code=400,
        )
    if user.tenants.filter(id=tenant_id).count() == 0:
        logger.error(f"User {user.id} does not have access to tenant ID {tenant_id}")
        return Response(
            content=json.dumps({"error": "Access denied"}),
            status_code=403,
        )
    # Now, for each operation in the body, we modify them when necessary for compliance with
    # our access control model.
    if isinstance(body, list):
        operations = body
    else:
        operations = [body]
    # logger.info(f"Operations: {operations}")
    perform_operations, operations = await modify_operations(operations, tenant_id)
    # logger.info(f"Modified operations: {operations}")
    # If the user is not allowed to perform any of the operations, return a 403
    if not perform_operations:
        logger.error(f"Access denied for tenant ID {tenant_id}")
        return Response(
            content=json.dumps({"error": "Access denied"}),
            status_code=403,
        )
    if isinstance(body, list):
        body = operations
    else:
        body = operations[0]
    # if not headers.get("x-prefect-tenant-id") or headers["x-prefect-tenant-id"] == "null":
    #     logger.warning(f"Missing tenant ID in headers.")
    # else:
    #     logger.success(f"Tenant ID: {headers['x-prefect-tenant-id']}")
    # logger.info(f"Body: {body}")
    # try:
    #     ast = GraphQLParser().parse(body["query"])
    #     logger.error(body["query"])
    #     logger.success(f"GraphQL query: {ast}")
    # except Exception:
    #     logger.warning(f'Failed to parse body "{body}" as GraphQL query')
    # if not headers.get("x-prefect-tenant-id"):
    #     return Response(
    #         content=json.dumps({"error": "Please provide tenant ID"}),
    #         status_code=400,
    #     )
    response = await graphql_request(body)
    if response.status_code != 200:
        logger.error(f"Prefect API returned {response.status_code}")
        logger.error(f"Body was: {body}")
    # logger.info(f"Response: {response.content}")
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response.headers,
    )
