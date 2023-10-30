# -*- coding: utf-8 -*-
import base64
import hashlib
import json
import secrets
from typing import List, Tuple

import httpx
from fastapi import FastAPI, Request
from graphql import (
    ArgumentNode,
    FieldNode,
    FragmentDefinitionNode,
    ListValueNode,
    NameNode,
    ObjectFieldNode,
    ObjectValueNode,
    OperationDefinitionNode,
    OperationType,
    StringValueNode,
    VariableNode,
    parse,
    print_ast,
)
from loguru import logger
from pydantic import BaseModel
from pyinstrument import Profiler
from pyinstrument.renderers.html import HTMLRenderer
from pyinstrument.renderers.speedscope import SpeedscopeRenderer

from app import config
from app.cache import cache
from app.models import User


class Status(BaseModel):
    message: str
    success: bool


async def add_id_argument_to_where_variable(variables: dict, tenant_id: str) -> dict:
    name = "tenant_id"
    # Check if field with name `name` already exists.
    # If it does, make sure the _eq field exists with the tenant_id.
    if name in variables:
        variables[name]["_eq"] = tenant_id
    # If it doesn't, add it.
    else:
        variables[name] = {"_eq": tenant_id}
    return variables


async def add_id_argument_to_where_value_node(
    where_node: ObjectValueNode, variables: dict, tenant_id: str
) -> ObjectValueNode:
    name = "tenant_id"
    fields = list(where_node.fields)
    # Check if field with name `name` already exists.
    name_field: ObjectFieldNode = None
    for field in fields:
        if field.name.value == name:
            name_field = field
            break
    # If it does, check if _eq already exists.
    if name_field:
        eq_field: ObjectFieldNode = None
        for field in name_field.value.fields:
            if field.name.value == "_eq":
                eq_field = field
                break
        # If it does, assert that the value is a StringValueNode with the tenant_id.
        if eq_field:
            if isinstance(eq_field.value, StringValueNode):
                eq_field.value.value = tenant_id
            elif isinstance(eq_field.value, VariableNode):
                variables[eq_field.value.name.value] = tenant_id
        # If it doesn't, add it.
        else:
            name_field_fields = list(name_field.value.fields)
            name_field_fields.append(
                ObjectFieldNode(
                    name=NameNode(value="_eq"),
                    value=StringValueNode(value=tenant_id),
                )
            )
            name_field.value.fields = tuple(name_field_fields)
    # If it doesn't, add it.
    else:
        fields.append(
            ObjectFieldNode(
                name=NameNode(value=name),
                value=ObjectValueNode(
                    fields=[
                        ObjectFieldNode(
                            name=NameNode(value="_eq"),
                            value=StringValueNode(value=tenant_id),
                        )
                    ]
                ),
            )
        )
        where_node.fields = tuple(fields)
    return where_node, variables


async def build_where_argument(tenant_id: str) -> ArgumentNode:
    name = "tenant_id"
    return ArgumentNode(
        name=NameNode(value="where"),
        value=ObjectValueNode(
            fields=[
                ObjectFieldNode(
                    name=NameNode(value=name),
                    value=ObjectValueNode(
                        fields=[
                            ObjectFieldNode(
                                name=NameNode(value="_eq"),
                                value=StringValueNode(value=tenant_id),
                            )
                        ]
                    ),
                )
            ]
        ),
    )


async def check_if_entity_belongs_to_tenant(entity: str, id: str, tenant_id: str) -> bool:
    """Check if the entity belongs to the tenant.

    Args:
        entity (str): The entity name.
        id (str): The entity id.
        tenant_id (str): The tenant id.

    Returns:
        bool: True if the entity belongs to the tenant, False otherwise.
    """
    logger.debug(f"Checking if {entity} with id {id} belongs to tenant {tenant_id}.")
    cache_key = f"{entity}-{id}__tenant-{tenant_id}"
    cache_value = cache.get(cache_key)
    if cache_value is not None:
        logger.debug(f"Cache hit for {entity} with id {id} and tenant {tenant_id}.")
        return cache_value
    logger.debug(f"Cache miss for {entity} with id {id} and tenant {tenant_id}.")
    query = f"""
        query {{
            {entity}_by_pk(id: "{id}") {{
                tenant_id
            }}
        }}
    """
    logger.debug(f"Query: {query}")
    body = {"query": query}
    response = await graphql_request(body)
    if response.status_code != 200:
        logger.debug(f"Response status code: {response.status_code}")
        cache.set(cache_key, False)
        return False
    data = response.json()
    if "errors" in data:
        logger.debug(f"Errors: {data['errors']}")
        cache.set(cache_key, False)
        return False
    if not data["data"][f"{entity}_by_pk"]:
        logger.debug(f"{entity} with id {id} does not exist.")
        cache.set(cache_key, False)
        return False
    if data["data"][f"{entity}_by_pk"]["tenant_id"] != tenant_id:
        logger.debug(f"{entity} with id {id} does not belong to tenant {tenant_id}.")
        cache.set(cache_key, False)
        return False
    logger.debug(f"{entity} with id {id} belongs to tenant {tenant_id}.")
    cache.set(cache_key, True)
    return True


async def filter_tenants(result: list, user: User):
    """Filter the tenants based on the user's permissions.

    Args:
        result (dict): The result.
        user (User): The user.
    """
    logger.debug(f"filter_tenants result: {result}")
    tenants = result["data"]["tenant"]
    filtered_tenants = []
    for tenant in tenants:
        if await user.tenants.filter(id=tenant["id"]).exists():
            filtered_tenants.append(tenant)
    result["data"]["tenant"] = filtered_tenants
    return result


async def get_entities_and_ids_from_input(
    selection: FieldNode, variables: dict
) -> Tuple[List[str], List[str]]:
    """Get the entities and ids from the `input` argument.

    Args:
        selection (FieldNode): The selection.
        variables (dict): The variables.

    Returns:
        Tuple[List[str], List[str]]: The entities and ids.
    """
    entities = []
    ids = []
    for argument in selection.arguments:
        if argument.name.value == "input":
            if isinstance(argument.value, ObjectValueNode):
                _entities, _ids = await get_entities_and_ids_from_object_value_node(
                    argument.value, variables
                )
            elif isinstance(argument.value, VariableNode):
                _entities, _ids = await get_entities_and_ids_from_variable_node(
                    argument.value, variables
                )
            else:
                raise ValueError(
                    "Argument value should be either an ObjectValueNode or a VariableNode, not "
                    f"{type(argument.value)}."
                )
            entities.extend(_entities)
            ids.extend(_ids)
            break
    return entities, ids


async def get_entities_and_ids_from_insert(
    selection: FieldNode, variables: dict
) -> Tuple[List[str], List[str]]:
    """Get the entities and ids from the insert selection.

    Args:
        selection (FieldNode): The selection.
        variables (dict): The variables.

    Returns:
        Tuple[List[str], List[str]]: The entities and ids.
    """

    entities = []
    ids = []
    for arg in selection.arguments:
        if arg.name.value == "objects":
            if isinstance(arg.value, ListValueNode):
                for object_value_node in arg.value.values:
                    if isinstance(object_value_node, ObjectValueNode):
                        _entities, _ids = await get_entities_and_ids_from_object_value_node(
                            object_value_node, variables
                        )
                        entities.extend(_entities)
                        ids.extend(_ids)
                    else:
                        raise Exception("Invalid objects argument.")
            else:
                raise Exception("Invalid objects argument.")
        if arg.name.value == "object":
            if isinstance(arg.value, ObjectValueNode):
                _entities, _ids = await get_entities_and_ids_from_object_value_node(
                    arg.value, variables
                )
                entities.extend(_entities)
                ids.extend(_ids)
    return entities, ids


async def get_entities_and_ids_from_object_value_node(
    object_value_node: ObjectValueNode, variables: dict
) -> Tuple[List[str], List[str]]:
    """Get the entities and ids from the object value node.

    Args:
        object_value_node (ObjectValueNode): The object value node.

    Returns:
        Tuple[List[str], List[str]]: The entities and ids.
    """
    entities = []
    ids = []
    for field in object_value_node.fields:
        if field.name.value.endswith("id"):
            entity = field.name.value.split("_id")[0]
            if isinstance(field.value, StringValueNode):
                entities.append(entity)
                ids.append(field.value.value)
            elif isinstance(field.value, VariableNode):
                entities.append(entity)
                ids.append(variables[field.value.name.value])
    return entities, ids


async def get_entities_and_ids_from_variable_node(
    variable_node: VariableNode, variables: dict
) -> Tuple[List[str], List[str]]:
    """Get the entities and ids from the variable node.

    Args:
        variable_node (VariableNode): The variable node.

    Returns:
        Tuple[List[str], List[str]]: The entities and ids.
    """
    entities = []
    ids = []
    for variable_name in variables[variable_node.name.value]:
        if variable_name.endswith("id"):
            entity = variable_name.split("_id")[0]
            entities.append(entity)
            ids.append(variables[variable_node.name.value][variable_name])
    return entities, ids


async def get_entity_id(
    entity: str, selection: FieldNode, variables: dict, loosen: bool = False
) -> str:
    """Get the entity id from the selection.

    Args:
        entity (str): The entity name.
        selection (FieldNode): The selection.
        variables (dict): The variables.

    Returns:
        str: The entity id.
    """
    name_entity_id = f"{entity}_id"
    # First try to extract it from the variables.
    if variables and name_entity_id in variables:
        return variables[name_entity_id]
    # Else, try to extract it from the selection arguments.
    for arg in selection.arguments:
        if (arg.name.value in [name_entity_id, "id"]) or (
            loosen and arg.name.value.endswith("_id")
        ):
            if isinstance(arg.value, StringValueNode):
                return arg.value.value
            elif isinstance(arg.value, VariableNode):
                return variables[arg.value.name.value]
        elif arg.name.value == "where":
            if isinstance(arg.value, ObjectValueNode):
                for field in arg.value.fields:
                    if (field.name.value == name_entity_id) or (
                        loosen and field.name.value.endswith("_id")
                    ):
                        if isinstance(field.value, StringValueNode):
                            return field.value.value
                        elif isinstance(field.value, VariableNode):
                            return variables[field.value.name.value]
                    elif field.name.value == "_and":
                        for and_field in field.value.fields:
                            if isinstance(and_field, ObjectFieldNode):
                                if (and_field.name.value == name_entity_id) or (
                                    loosen and and_field.name.value.endswith("_id")
                                ):
                                    if isinstance(and_field.value, StringValueNode):
                                        return and_field.value.value
                                    elif isinstance(and_field.value, VariableNode):
                                        return variables[and_field.value.name.value]
                            elif isinstance(and_field, VariableNode):
                                return variables[and_field.name.value]
            elif isinstance(arg.value, VariableNode):
                for field in variables[arg.value.name.value]:
                    if field == "_and":
                        for and_field in variables[arg.value.name.value][field]:
                            if (and_field in [name_entity_id, "id"]) or (
                                loosen and and_field.endswith("_id")
                            ):
                                return variables[arg.value.name.value][field][and_field]["_eq"]
                    elif (field in [name_entity_id, "id"]) or (loosen and field.endswith("_id")):
                        return variables[arg.value.name.value][field]["_eq"]
        elif arg.name.value == "input":
            if isinstance(arg.value, ObjectValueNode):
                for field in arg.value.fields:
                    if (field.name.value == name_entity_id) or (
                        loosen and field.name.value.endswith("_id")
                    ):
                        if isinstance(field.value, StringValueNode):
                            return field.value.value
                        elif isinstance(field.value, VariableNode):
                            return variables[field.value.name.value]
            elif isinstance(arg.value, VariableNode):
                for field in variables[arg.value.name.value]:
                    if (field == name_entity_id) or (loosen and field.endswith("_id")):
                        return variables[arg.value.name.value][field]
    # Else, raise because we couldn't find it.
    raise ValueError(f"Couldn't find {name_entity_id} in selection arguments or variables.")


async def get_entity_ids_from_input_states(entity: str, selection: FieldNode, variables: dict):
    """Get the entity ids from the input states.

    Args:
        entity (str): The entity name.
        selection (FieldNode): The selection.
        variables (dict): The variables.

    Returns:
        List[str]: The entity ids.
    """
    entity_ids = []
    for arg in selection.arguments:
        if arg.name.value == "input":
            if isinstance(arg.value, ObjectValueNode):
                for field in arg.value.fields:
                    if field.name.value == "states":
                        if isinstance(field.value, ListValueNode):
                            for object_value_node in field.value.values:
                                entities, ids = await get_entities_and_ids_from_object_value_node(
                                    object_value_node, variables
                                )
                                if entity in entities:
                                    entity_ids.append(ids[entities.index(entity)])
                        elif isinstance(field.value, VariableNode):
                            for state in variables[field.value.name.value]:
                                if f"{entity}_id" in state:
                                    entity_ids.append(state[f"{entity}_id"])
            elif isinstance(arg.value, VariableNode):
                if "states" in variables[arg.value.name.value]:
                    for state in variables[arg.value.name.value]["states"]:
                        if f"{entity}_id" in state:
                            entity_ids.append(state[f"{entity}_id"])
    return entity_ids


async def get_flow_run_ids_from_write(selection: FieldNode, variables: dict) -> List[str]:
    """Get the flow run ids from the write selection.

    Args:
        selection (FieldNode): The selection.
        variables (dict): The variables.

    Returns:
        List[str]: The flow run ids.
    """
    flow_run_ids = []
    for arg in selection.arguments:
        # Find the `input` argument.
        if arg.name.value == "input":
            # It must have a field named `logs`
            if isinstance(arg.value, ObjectValueNode):
                for field in arg.value.fields:
                    if field.name.value == "logs":
                        # This is a list of objects. Each object will have a `flow_run_id` field.
                        if isinstance(field.value, ListValueNode):
                            for object_value_node in field.value.values:
                                entities, ids = await get_entities_and_ids_from_object_value_node(
                                    object_value_node, variables
                                )
                                if "flow_run" in entities:
                                    flow_run_ids.append(ids[entities.index("flow_run")])
                        # This is a variable
                        elif isinstance(field.value, VariableNode):
                            for log in variables[field.value.name.value]:
                                if "flow_run_id" in log:
                                    flow_run_ids.append(log["flow_run_id"])
            # It can also be a variable.
            elif isinstance(arg.value, VariableNode):
                for field in variables[arg.value.name.value]:
                    if field == "logs":
                        for log in variables[arg.value.name.value][field]:
                            if "flow_run_id" in log:
                                flow_run_ids.append(log["flow_run_id"])
    return flow_run_ids


async def graphql_request(operations: dict) -> httpx.Response:
    """Make a GraphQL request to Prefect backend.

    Args:
        operations (dict): The operations to send to Prefect backend.

    Returns:
        bytes: The response from Prefect backend.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.PREFECT_API_URL,
            json=operations,
        )
    return response


async def is_tenant_query(operation: dict) -> bool:
    """Check if the operation is a tenant query.

    Args:
        operation (dict): The operation.

    Returns:
        bool: Whether the operation is a tenant query.
    """
    if "query" not in operation:
        return False
    ast = parse(operation["query"])
    for definition in ast.definitions:
        if isinstance(definition, OperationDefinitionNode):
            for selection in definition.selection_set.selections:
                if isinstance(selection, FieldNode):
                    if selection.name.value == "tenant":
                        return True
    return False


async def map_entity_name(entity_name: str) -> str:
    """Map an entity name to its GraphQL type.

    Args:
        entity_name (str): The entity name.

    Returns:
        str: The GraphQL type.
    """
    if entity_name.startswith("_task_run"):
        return "task_run"
    elif entity_name.startswith("agent"):
        return "agent"
    elif entity_name.startswith("cloud_hook"):
        return "cloud_hook"
    elif entity_name.startswith("edge"):
        return "edge"
    elif entity_name.startswith("flow"):
        if entity_name.startswith("flow_group"):
            return "flow_group"
        elif entity_name.startswith("flow_run"):
            return "flow_run"
        else:
            return "flow"
    elif entity_name.startswith("log"):
        return "log"
    elif entity_name.startswith("message"):
        return "message"
    elif entity_name.startswith("project"):
        return "project"
    elif entity_name.startswith("run"):
        return "flow_run"
    elif entity_name.startswith("schedule"):
        return "flow"
    elif entity_name.startswith("task"):
        return "task"
    elif entity_name.startswith("tenant"):
        return "tenant"
    elif entity_name.startswith("utility"):
        return "task"


async def modify_operations(operations: List[dict], tenant_id: str) -> Tuple[bool, List[dict]]:
    """Modify operations to include tenant_id argument.

    Args:
        operations (List[dict]): The list of operations to modify.
        tenant_id (str): The tenant_id to use.

    Returns:
        Tuple[bool, List[dict]]: A tuple containing a boolean indicating whether the operations
            are allowed and the modified operations.
    """
    perform_operations = True
    modified_operations = []
    for operation in operations:
        query = operation["query"] if "query" in operation else None
        variables = operation["variables"] if "variables" in operation else None
        logger.info(f"Operation:\n- Query:\n{query}\n- Variables:\n{variables}")
        if "variables" in operation and isinstance(operation["variables"], str):
            operation["variables"] = json.loads(operation["variables"])
        ast = parse(operation["query"])
        for definition in ast.definitions:
            if isinstance(definition, FragmentDefinitionNode):
                continue
            assert isinstance(definition, OperationDefinitionNode)
            # If it's a query
            if definition.operation == OperationType.QUERY:
                for selection in definition.selection_set.selections:
                    assert isinstance(selection, FieldNode)
                    selection_name = selection.name.value
                    if selection_name in ["hello", "reference_data", "api", "__schema"]:
                        # It's a public query, no need to modify
                        continue
                    elif selection_name in ["mapped_children", "get_task_run_info"]:
                        # Check if task_run_id is in tenant's task_runs
                        entity = "task_run"
                        task_run_id = await get_entity_id(entity, selection, operation["variables"])
                        belongs = await check_if_entity_belongs_to_tenant(
                            entity, task_run_id, tenant_id
                        )
                        if not belongs:
                            logger.error(
                                f"Task run {task_run_id} doesn't belong to tenant {tenant_id}"
                            )
                            perform_operations = False
                            break
                    elif selection_name.endswith("_by_pk"):
                        # Get entity name and check if it's in tenant's entities
                        second_entity = None
                        if selection_name == "flow_by_pk":
                            entity = "flow"
                            second_entity = "flow_group"
                        else:
                            entity = selection_name[: -len("_by_pk")]
                        entity_id = await get_entity_id(entity, selection, operation["variables"])
                        belongs = await check_if_entity_belongs_to_tenant(
                            entity, entity_id, tenant_id
                        )
                        if second_entity:
                            belongs = belongs or await check_if_entity_belongs_to_tenant(
                                second_entity, entity_id, tenant_id
                            )
                        if not belongs:
                            logger.debug(operation["query"])
                            logger.error(
                                f"{entity.capitalize()} {entity_id} doesn't belong to tenant "
                                f"{tenant_id}"
                            )
                            perform_operations = False
                            break
                    elif selection_name.startswith("tenant"):
                        # It's a tenant query, just make sure we have `id` in the body.
                        # We'll filter results later
                        id_exists = False
                        for selection_ in selection.selection_set.selections:
                            assert isinstance(selection_, FieldNode)
                            if selection_.name.value == "id":
                                id_exists = True
                                break
                        if not id_exists:
                            selections = list(selection.selection_set.selections)
                            selections.append(FieldNode(name=NameNode(value="id")))
                            selection.selection_set.selections = tuple(selections)
                    else:
                        # Filter by tenant_id
                        where_arg_exists = False
                        prev_arguments = selection.arguments
                        for arg in prev_arguments:
                            assert isinstance(arg, ArgumentNode)
                            if arg.name.value == "where":
                                where_arg_exists = True
                                if isinstance(arg.value, ObjectValueNode):
                                    (
                                        arg.value,
                                        operation["variables"],
                                    ) = await add_id_argument_to_where_value_node(
                                        arg.value,
                                        operation["variables"],
                                        tenant_id=tenant_id,
                                    )
                                elif isinstance(arg.value, VariableNode):
                                    operation["variables"][
                                        arg.value.name.value
                                    ] = await add_id_argument_to_where_variable(
                                        operation["variables"][arg.value.name.value],
                                        tenant_id=tenant_id,
                                    )
                                else:
                                    print(f"arg.value is {type(arg.value)}")
                        if not where_arg_exists:
                            where_arg = await build_where_argument(tenant_id=tenant_id)
                            selection.arguments = tuple(list(prev_arguments) + [where_arg])
            # If it's a mutation
            elif definition.operation == OperationType.MUTATION:
                for selection in definition.selection_set.selections:
                    assert isinstance(selection, FieldNode)
                    selection_name = selection.name.value
                    # Split into operation, entity and action
                    action, entity, mode = await split_operation_entity_mode(selection_name)
                    # Block some operations based on the entity
                    if (
                        entity.startswith("cloud_hook")
                        or entity.startswith("project_description")
                        or entity.startswith("message")
                        or "artifact" in entity
                    ):
                        logger.error(f"Operations on entity {entity} is not allowed")
                        perform_operations = False
                        break
                    # If it's a delete operation, we must get the entity id
                    elif action in ["delete", "set", "update"]:
                        entity = await map_entity_name(entity)
                        entity_ids = []
                        if selection_name.endswith("states"):
                            entity_ids = await get_entity_ids_from_input_states(
                                entity, selection, operation["variables"]
                            )
                        else:
                            entity_id = await get_entity_id(
                                entity, selection, operation["variables"], loosen=True
                            )
                            entity_ids.append(entity_id)
                        for entity_id in entity_ids:
                            belongs = await check_if_entity_belongs_to_tenant(
                                entity, entity_id, tenant_id
                            )
                            if not belongs:
                                logger.error(
                                    f"{entity.capitalize()} {entity_id} doesn't belong to tenant "
                                    f"{tenant_id}"
                                )
                                perform_operations = False
                                break
                    elif action == "insert":
                        # The argument is either `objects` or `object`. We need to collect all
                        # IDs and related entities within the objects and check if they belong
                        # to the tenant.
                        entities, ids = await get_entities_and_ids_from_insert(
                            selection, operation["variables"]
                        )
                        belongs = True
                        for entity, entity_id in zip(entities, ids):
                            belongs = await check_if_entity_belongs_to_tenant(
                                entity, entity_id, tenant_id
                            )
                            if not belongs:
                                logger.error(
                                    f"{entity.capitalize()} {entity_id} doesn't belong to tenant "
                                    f"{tenant_id}"
                                )
                                perform_operations = False
                                break
                    elif action in [
                        "archive",
                        "cancel",
                        "create",
                        "disable",
                        "enable",
                        "get",
                        "register",
                    ]:
                        # The argument `input` always has at least one ID of any entity.
                        # We extract them and, then, if we have a tenant ID, we check if it
                        # matches ours. Else, we check if the entity belongs to the tenant.
                        entities, ids = await get_entities_and_ids_from_input(
                            selection, operation["variables"]
                        )
                        entities = [await map_entity_name(entity) for entity in entities]
                        if "tenant" in entities:
                            if ids[entities.index("tenant")] != tenant_id:
                                logger.error(
                                    f"Tenant {ids[entities.index('tenant')]} doesn't match "
                                    f"{tenant_id}"
                                )
                                perform_operations = False
                                break
                        else:
                            belongs = True
                            for entity, entity_id in zip(entities, ids):
                                belongs = await check_if_entity_belongs_to_tenant(
                                    entity, entity_id, tenant_id
                                )
                                if not belongs:
                                    logger.error(
                                        f"{entity.capitalize()} {entity_id} doesn't belong to "
                                        f"tenant {tenant_id}"
                                    )
                                    perform_operations = False
                                    break
                    elif action == "get_or_create":
                        # This is very similar to "get", but we must skip the `task` entity
                        # because it might not exist yet.
                        entities, ids = await get_entities_and_ids_from_input(
                            selection, operation["variables"]
                        )
                        if "tenant" in entities:
                            if ids[entities.index("tenant")] != tenant_id:
                                logger.error(
                                    f"Tenant {ids[entities.index('tenant')]} doesn't match "
                                    f"{tenant_id}"
                                )
                                perform_operations = False
                                break
                        else:
                            belongs = True
                            for entity, entity_id in zip(entities, ids):
                                if entity == "task":
                                    continue
                                belongs = await check_if_entity_belongs_to_tenant(
                                    entity, entity_id, tenant_id
                                )
                                if not belongs:
                                    logger.error(
                                        f"{entity.capitalize()} {entity_id} doesn't belong to "
                                        f"tenant {tenant_id}"
                                    )
                                    perform_operations = False
                                    break
                    elif action == "write":
                        # This is a very special case as it has just a single mutation:
                        # `write_run_logs`. It takes an `input` argument that has a `logs`
                        # field that is a list of objects containing a `flow_run_id` field.
                        # We must extract all `flow_run_id` values and check if they belong
                        # to the tenant.
                        flow_run_ids = await get_flow_run_ids_from_write(
                            selection, operation["variables"]
                        )
                        belongs = True
                        for flow_run_id in flow_run_ids:
                            belongs = await check_if_entity_belongs_to_tenant(
                                "flow_run", flow_run_id, tenant_id
                            )
                            if not belongs:
                                logger.error(
                                    f"Flow run {flow_run_id} doesn't belong to tenant {tenant_id}"
                                )
                                perform_operations = False
                                break
                    # If it's another operation, we just block it
                    else:
                        logger.error(f"Tried to perform {action} on {entity}, not allowed")
                        perform_operations = False
                        break

            # If it's a subscription or anything else, block all operations
            else:
                logger.error(f"Operation {definition.operation} is not allowed")
                perform_operations = False
                break
        operation["query"] = print_ast(ast)
        modified_operations.append(operation)
    return perform_operations, modified_operations


async def password_hash(password: str, salt: str = None, iterations: int = None) -> str:
    """Hash a password.

    Args:
        password (str): The password to hash.

    Returns:
        str: The hashed password.
    """
    if not salt:
        salt = secrets.token_hex(16)
    if not iterations:
        iterations = config.PASSWORD_HASH_NUMBER_OF_ITERATIONS
    assert isinstance(password, str)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    b64_hash = base64.b64encode(pw_hash).decode("ascii").strip()
    return "{}${}${}${}".format(
        config.PASSWORD_HASH_ALGORITHM,
        iterations,
        salt,
        b64_hash,
    )


async def password_verify(password: str, hashed: str) -> bool:
    """Verify a password against a hash.

    Args:
        password (str): The password to verify.
        hashed (str): The hashed password to verify against.

    Returns:
        bool: True if the password matches the hash, False otherwise.
    """
    if (hashed or "").count("$") != 3:
        return False
    algorithm, iterations, salt, _ = hashed.split("$", 3)
    iterations = int(iterations)
    assert algorithm == config.PASSWORD_HASH_ALGORITHM
    compare_hash = await password_hash(password, salt, iterations)
    return secrets.compare_digest(hashed, compare_hash)


async def split_operation_entity_mode(selection_name: str) -> Tuple[str, str, str]:
    """Split a selection name into operation, entity and mode.

    Args:
        selection_name (str): The selection name to split.

    Returns:
        Tuple[str, str, str]: A tuple containing the operation, entity and mode.
    """
    parts = selection_name.split("_")
    operation = parts[0]
    entity_mode = "_".join(parts[1:])
    if operation == "get":
        tmp_parts = selection_name.split("get_or_create")
        if len(tmp_parts) == 2:
            operation = "get_or_create"
            entity_mode = tmp_parts[1]
    parts = entity_mode.split("_by_")
    entity = parts[0]
    if len(parts) == 2:
        mode = parts[1]
    else:
        mode = None
    return operation, entity, mode


def register_middlewares_profile(app: FastAPI):
    @app.middleware("http")
    async def profile_request(request: Request, call_next):
        """Profile the current request

        Taken from https://pyinstrument.readthedocs.io/en/latest/guide.html
        with small improvements.

        """
        # we map a profile type to a file extension, as well as a pyinstrument profile renderer
        profile_type_to_ext = {"html": "html", "speedscope": "speedscope.json"}
        profile_type_to_renderer = {
            "html": HTMLRenderer,
            "speedscope": SpeedscopeRenderer,
        }

        # The default profile format is speedscope
        profile_type = request.query_params.get("profile_format", "speedscope")

        # we profile the request along with all additional middlewares, by interrupting
        # the program every 1ms1 and records the entire stack at that point
        with Profiler(interval=0.001, async_mode="enabled") as profiler:
            response = await call_next(request)

        # we dump the profiling into a file
        extension = profile_type_to_ext[profile_type]
        renderer = profile_type_to_renderer[profile_type]()
        with open(f"{config.PROFILING_PATH}/{config.HOST}.profile.{extension}", "w") as out:
            out.write(profiler.output(renderer=renderer))
        return response
