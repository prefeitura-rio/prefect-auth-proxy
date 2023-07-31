# -*- coding: utf-8 -*-
from tortoise import fields
from tortoise.models import Model


class Tenant(Model):
    id = fields.UUIDField(pk=True)
    slug = fields.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"{self.slug} - {self.id}"


class User(Model):
    id = fields.BigIntField(pk=True)
    username = fields.CharField(max_length=100, unique=True)
    password = fields.CharField(max_length=1024)
    is_active = fields.BooleanField(default=True)
    token = fields.UUIDField()
    token_expiry = fields.DatetimeField(null=True)
    scopes = fields.TextField(null=True)
    tenants: fields.ManyToManyRelation[Tenant] = fields.ManyToManyField(
        "auth_proxy.Tenant",
        related_name="users",
        through="user_tenant",
        backward_key="user_id",
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} - {self.tenants}"
