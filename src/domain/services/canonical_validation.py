from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class CanonicalValidationError(RuntimeError):
    pass


class Spec(Protocol):
    def validate(self, filename: str, payload: dict[str, Any]) -> list[str]: ...


@dataclass(slots=True)
class UniqueIdsSpec:
    def validate(self, filename: str, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        paths = {
            "tickets.queues": payload.get("tickets", {}).get("queues", []),
            "projects.projects": payload.get("projects", {}).get("projects", []),
            "dashboard.dashboards": payload.get("dashboard", {}).get("dashboards", []),
            "kpi.kpis": payload.get("kpi", {}).get("kpis", []),
            "hr_hub.request_types": payload.get("hr_hub", {}).get("request_types", []),
            "hr_hub.employees": payload.get("hr_hub", {}).get("employees", []),
        }
        for path, items in paths.items():
            if not isinstance(items, list):
                continue
            ids: list[object] = [i.get("id") for i in items if isinstance(i, dict)]
            dupes = {x for x in ids if x is not None and ids.count(x) > 1}
            if dupes:
                errors.append(f"{filename}: duplicate IDs in {path}: {sorted(dupes)}")
        return errors


@dataclass(slots=True)
class ReferentialIntegritySpec:
    def validate(self, filename: str, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        required_paths = (
            ("tickets", "queues"),
            ("projects", "projects"),
            ("dashboard", "dashboards"),
            ("kpi", "kpis"),
            ("hr_hub", "employees"),
            ("hr_hub", "request_types"),
        )
        for parent, child in required_paths:
            node = payload.get(parent)
            if not isinstance(node, dict) or not isinstance(node.get(child), list):
                errors.append(f"{filename}: {parent}.{child} must be a list")

        employees = payload.get("hr_hub", {}).get("employees", [])
        for idx, emp in enumerate(employees):
            if not isinstance(emp, dict):
                errors.append(f"{filename}: hr_hub.employees[{idx}] must be object")
                continue
            if "id" not in emp:
                errors.append(f"{filename}: hr_hub.employees[{idx}] missing id")
        return errors


@dataclass(slots=True)
class EmployeeMutableFieldsSpec:
    _allowed = {
        "id",
        "position",
        "team",
        "department",
        "job_title",
        "job_type",
        "job_level",
    }

    def validate(self, filename: str, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        employees = payload.get("hr_hub", {}).get("employees", [])
        for idx, emp in enumerate(employees):
            if not isinstance(emp, dict):
                continue
            extra_keys = sorted(set(emp.keys()) - self._allowed)
            if extra_keys:
                errors.append(
                    f"{filename}: hr_hub.employees[{idx}] has unsupported fields: {extra_keys}"
                )
            for key in self._allowed - {"id"}:
                value = emp.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"{filename}: hr_hub.employees[{idx}].{key} must be non-empty string"
                    )
        return errors


@dataclass(slots=True)
class ValidationChain:
    specs: tuple[Spec, ...]

    def validate_all(self, manifests: dict[str, dict[str, Any]]) -> None:
        errors: list[str] = []
        for filename, payload in manifests.items():
            for spec in self.specs:
                errors.extend(spec.validate(filename, payload))
        if errors:
            raise CanonicalValidationError("\n".join(errors))
