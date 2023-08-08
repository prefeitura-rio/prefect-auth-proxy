# -*- coding: utf-8 -*-
import json

import httpx
from fastapi import APIRouter, Depends, Request, Response
from loguru import logger

from app import config
from app.dependencies import validate_token
from app.models import Tenant, User
from app.utils import (
    filter_tenants,
    graphql_request,
    is_tenant_query,
    modify_operations,
)

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
    logger.info(f"User {user.username} is requesting tenant ID {tenant_id}")
    logger.info(f"User {user.username} has access to tenants {await user.tenants.all()}")
    if await user.tenants.filter(id=tenant_id).count() == 0:
        logger.error(f"User {user.username} does not have access to tenant ID {tenant_id}")
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
    perform_operations, operations = await modify_operations(operations, tenant_id)
    # If the user is not allowed to perform any of the operations, return a 403
    if not perform_operations:
        logger.error(f"Access denied for tenant ID {tenant_id}")
        return Response(
            content=json.dumps({"error": "Access denied"}),
            status_code=403,
        )
    # Now we want to check if there's a tenant query in the body. If there is, we want to
    # filter the results later.
    is_tenant_query_operation = [await is_tenant_query(operation) for operation in operations]
    if isinstance(body, list):
        body = operations
    else:
        body = operations[0]
    response = await graphql_request(body)
    if response.status_code != 200:
        logger.error(f"Prefect API returned {response.status_code}")
        logger.error(f"Body was: {body}")
    # Filter results if necessary
    if any(is_tenant_query_operation):
        # Parse the response body as JSON
        try:
            body = response.json()
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON: {body}")
            return Response(
                content="Invalid JSON",
                status_code=400,
            )
        # Filter the results
        if isinstance(body, list):
            response_body = []
            for i, result in enumerate(body):
                if is_tenant_query_operation[i]:
                    response_body.append(await filter_tenants(result, user))
                else:
                    response_body.append(result)
        else:
            response_body = await filter_tenants(body, user)
        # Fix the Content-Length header
        content = json.dumps(response_body)
        response.headers["Content-Length"] = str(len(content))
        # Return the response
        return Response(
            content=content,
            status_code=response.status_code,
            headers=response.headers,
        )
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response.headers,
    )
