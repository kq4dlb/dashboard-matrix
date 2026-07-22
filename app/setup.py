from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.auth import change_password
from app.database import connection, get_setting, is_setup_complete, set_setting
from app.starter_templates import install_template, template_summaries
from app.websocket import manager

router = APIRouter(prefix="/api/setup", tags=["setup"])


class SetupRequest(BaseModel):
    display_name: str = Field(default="Dashboard Matrix", min_length=1, max_length=120)
    callsign: str = Field(default="N0CALL", min_length=3, max_length=12)
    grid_square: str = Field(default="AA00aa", min_length=6, max_length=6)
    template: Literal["blank", "amateur-radio", "home-lab"] = "blank"
    password: str = Field(min_length=8, max_length=128)
    theme: Literal["matrix-dark", "matrix-light"] = "matrix-dark"
    release_channel: Literal["stable", "beta", "nightly"] = "beta"

    @field_validator("callsign")
    @classmethod
    def normalize_callsign(cls, value: str) -> str:
        value = value.strip().upper()
        if not all(character.isalnum() or character == "/" for character in value):
            raise ValueError("Callsign may contain only letters, numbers, and slash")
        return value

    @field_validator("grid_square")
    @classmethod
    def normalize_grid(cls, value: str) -> str:
        value = value.strip()
        if len(value) != 6:
            raise ValueError("Grid square must contain six characters")
        normalized = value[:2].upper() + value[2:4] + value[4:].lower()
        import re

        if not re.fullmatch(r"[A-R]{2}[0-9]{2}[a-x]{2}", normalized):
            raise ValueError("Invalid six-character Maidenhead grid square")
        return normalized


@router.get("/status")
def setup_status() -> dict:
    return {
        "complete": is_setup_complete(),
        "templates": template_summaries(),
    }


@router.post("")
async def complete_setup(item: SetupRequest, request: Request) -> dict:
    if is_setup_complete():
        raise HTTPException(409, "First-run setup has already been completed")

    with connection() as conn:
        install_template(conn, item.template, replace_existing=True)
        values = {
            "display_name": item.display_name.strip(),
            "callsign": item.callsign,
            "grid_square": item.grid_square,
            "default_theme": item.theme,
            "release_channel": item.release_channel,
            "setup_template": item.template,
            "setup_complete": "1",
        }
        for key, value in values.items():
            set_setting(conn, key, value)

    change_password(item.password)
    request.session["admin_authenticated"] = True
    await manager.broadcast({"event": "configuration_changed"})
    return {
        "status": "configured",
        "template": item.template,
        "redirect": "/admin",
    }


def setup_gate_required() -> bool:
    return not is_setup_complete()
