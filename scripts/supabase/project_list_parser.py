#!/usr/bin/env python3
"""Valida la salida JSON de `supabase projects list` sin exponerla."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


class ProjectListFormatError(ValueError):
    """La salida JSON no tiene una estructura compatible conocida."""


class ProjectVerificationError(ValueError):
    """La estructura es válida, pero no identifica el proyecto esperado."""


def extract_projects(payload: Any) -> list[dict[str, Any]]:
    """Normaliza los formatos de salida compatibles del CLI de Supabase.

    CLI 3.0.0 emite:
    - `--output json`: una lista de proyectos;
    - `--output-format json`: `{\"projects\": [...], \"message\": \"\"}`;
    - salida estructurada/evento: `{\"data\": {\"projects\": [...]}, ...}`.
    """

    projects: Any
    source: str
    if isinstance(payload, list):
        projects = payload
        source = "raíz"
    elif isinstance(payload, dict):
        if "projects" in payload:
            projects = payload["projects"]
            source = "projects"
        elif "data" in payload:
            data = payload["data"]
            if not isinstance(data, dict):
                raise ProjectListFormatError(
                    "el campo 'data' debe ser un objeto cuando está presente"
                )
            if "projects" not in data:
                raise ProjectListFormatError("el objeto 'data' no contiene el campo 'projects'")
            projects = data["projects"]
            source = "data.projects"
        else:
            keys = ", ".join(sorted(str(key) for key in payload)) or "ninguna"
            raise ProjectListFormatError(
                "la raíz JSON es un objeto sin 'projects' ni 'data.projects' "
                f"(campos recibidos: {keys})"
            )
    else:
        raise ProjectListFormatError(
            f"la raíz JSON debe ser una lista o un objeto; se recibió {type(payload).__name__}"
        )

    if not isinstance(projects, list):
        raise ProjectListFormatError(
            f"el campo '{source}' debe ser una lista; se recibió {type(projects).__name__}"
        )

    normalized: list[dict[str, Any]] = []
    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            raise ProjectListFormatError(
                f"el proyecto en índice {index} debe ser un objeto; "
                f"se recibió {type(project).__name__}"
            )
        for field in ("id", "ref", "name", "status"):
            value = project.get(field)
            if value is not None and not isinstance(value, str):
                raise ProjectListFormatError(
                    f"el campo '{field}' del proyecto en índice {index} debe ser texto"
                )
        identifiers = [project.get(field) for field in ("id", "ref")]
        identifiers = [value for value in identifiers if isinstance(value, str) and value]
        if not identifiers:
            raise ProjectListFormatError(
                f"el proyecto en índice {index} no contiene 'id' o 'ref' textual"
            )
        if not isinstance(project.get("name"), str) or not project["name"]:
            raise ProjectListFormatError(
                f"el proyecto en índice {index} no contiene un 'name' textual"
            )
        normalized.append(project)
    return normalized


def verify_project(payload: Any, *, expected_ref: str, expected_name: str) -> dict[str, Any]:
    projects = extract_projects(payload)
    matches: list[dict[str, Any]] = []
    for project in projects:
        identifiers = {project.get("id"), project.get("ref")}
        if expected_ref in identifiers:
            matches.append(project)

    if not matches:
        raise ProjectVerificationError(
            f"el listado no contiene el project ref esperado {expected_ref}"
        )
    if len(matches) != 1:
        raise ProjectVerificationError(
            f"el project ref esperado aparece {len(matches)} veces; se requiere una coincidencia"
        )

    project = matches[0]
    if project["name"] != expected_name:
        raise ProjectVerificationError(
            "el project ref esperado pertenece a un nombre distinto del aprobado"
        )

    identifiers = {
        value
        for value in (project.get("id"), project.get("ref"))
        if isinstance(value, str) and value
    }
    if len(identifiers) > 1:
        raise ProjectVerificationError(
            "el proyecto esperado contiene valores 'id' y 'ref' contradictorios"
        )

    status = project.get("status")
    if not isinstance(status, str) or not status:
        raise ProjectVerificationError("el proyecto esperado no informa un estado textual")
    if status != "ACTIVE_HEALTHY":
        raise ProjectVerificationError(f"el proyecto no está ACTIVE_HEALTHY; estado={status}")
    return project


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--expected-ref", required=True)
    parser.add_argument("--expected-name", required=True)
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
        project = verify_project(
            payload,
            expected_ref=args.expected_ref,
            expected_name=args.expected_name,
        )
    except json.JSONDecodeError as exc:
        print(
            "FALLO: projects list no devolvió JSON válido "
            f"(línea {exc.lineno}, columna {exc.colno})",
            file=sys.stderr,
        )
        return 1
    except (ProjectListFormatError, ProjectVerificationError) as exc:
        print(f"FALLO: formato de projects list incompatible: {exc}", file=sys.stderr)
        return 1

    print(
        f"Proyecto verificado: {args.expected_name} ({args.expected_ref}); "
        f"estado={project['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
