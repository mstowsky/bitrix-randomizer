"""Pydantic schemas for Bitrix24 application lifecycle events."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Bitrix24EventAuth(BaseModel):
    """Authorization and portal data included in Bitrix24 events."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    domain: str
    member_id: str
    application_token: str
    client_endpoint: str
    server_endpoint: str

    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    scope: str | None = None
    status: str | None = None


class AppInstallData(BaseModel):
    """Data included in the ONAPPINSTALL event."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    version: str = Field(alias="VERSION")
    language_id: str = Field(alias="LANGUAGE_ID")


class AppUninstallData(BaseModel):
    """Data included in the ONAPPUNINSTALL event."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    language_id: str = Field(alias="LANGUAGE_ID")
    clean: int = Field(alias="CLEAN")


class AppInstallEvent(BaseModel):
    """ONAPPINSTALL event payload."""

    model_config = ConfigDict(extra="ignore")

    event: Literal["ONAPPINSTALL"]
    data: AppInstallData
    auth: Bitrix24EventAuth
    ts: int
    event_handler_id: int | None = None


class AppUninstallEvent(BaseModel):
    """ONAPPUNINSTALL event payload."""

    model_config = ConfigDict(extra="ignore")

    event: Literal["ONAPPUNINSTALL"]
    data: AppUninstallData
    auth: Bitrix24EventAuth
    ts: int
    event_handler_id: int | None = None
