from __future__ import annotations

from typing import Any
from uuid import uuid4

from .enums import ConnectorState, MappingState, TicketState
from .errors import ConflictError, ValidationError
from .helpers import digest, normalize_status_map, now, sanitize
from .models import AdapterMapping, Connector, Scope


class ConnectorCommands:
    def register_connector(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> Connector:
        self._require_key(key)
        payload = sanitize(payload)
        missing = [field for field in ("vendor", "name", "capabilities", "auth_profile") if not payload.get(field)]
        if missing:
            raise ValidationError("missing required fields: " + ", ".join(missing))
        command_payload = {
            "vendor": payload["vendor"],
            "name": payload["name"],
            "capabilities": sorted(set(payload.get("capabilities") or [])),
            "auth_profile": payload["auth_profile"],
            "trust_level": payload.get("trust_level") or "standard",
            "credential": payload.get("credential") or "unset",
        }
        allowed_trust = {"untrusted", "standard", "elevated", "privileged", "local"}
        if command_payload["trust_level"] not in allowed_trust:
            raise ValidationError(
                "trust_level must be one of: " + ", ".join(sorted(allowed_trust))
            )
        role_list = [str(r) for r in (payload.get("actor_roles") or [])]
        perm_list = [str(p) for p in (payload.get("actor_permissions") or [])]
        enforce = str(__import__("os").environ.get("ASTLOOM_ENFORCE_ADMIN_MATRIX", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if enforce or role_list or perm_list:
            try:
                from architecture_governance import admin_action_allowed
    
                if not admin_action_allowed(
                    "adapter.install",
                    roles=role_list,
                    permissions=perm_list,
                ):
                    raise ValidationError("adapter.install denied by admin permission matrix")
            except ImportError as exc:
                raise ValidationError(
                    "adapter.install requires architecture_governance when "
                    "ASTLOOM_ENFORCE_ADMIN_MATRIX is enabled or actor roles/permissions "
                    "are supplied"
                ) from exc
        prior = self.store.idempotent(scope, "register_connector", key, command_payload)
        if prior:
            return self.store.get_connector(prior, scope)
        timestamp = now()
        connector = Connector(
            str(uuid4()),
            scope,
            actor,
            correlation_id,
            command_payload["vendor"],
            command_payload["name"],
            command_payload["capabilities"],
            command_payload["auth_profile"],
            command_payload["trust_level"],
            ConnectorState.PENDING,
            digest(command_payload["credential"]),
            timestamp,
            timestamp,
        )
        self.store.put_connector(connector)
        status_map = normalize_status_map(payload.get("status_map"))
        reopen_policy = str(payload.get("reopen_policy") or "allow_remote").strip()
        if reopen_policy not in {"allow_remote", "deny"}:
            raise ValidationError("reopen_policy must be allow_remote or deny")
        unknown_status_policy = str(payload.get("unknown_status_policy") or "reject").strip()
        if unknown_status_policy not in {"reject", "fallback"}:
            raise ValidationError("unknown_status_policy must be reject or fallback")
        fallback_status = str(payload.get("fallback_status") or "open").strip()
        try:
            TicketState(fallback_status)
        except ValueError as exc:
            raise ValidationError("fallback_status must be a portable ticket status") from exc
        mapping_version = int(payload.get("mapping_version") or 1)
        if mapping_version < 1:
            raise ValidationError("mapping_version must be a positive integer")
        mapping = AdapterMapping(
            str(uuid4()),
            scope,
            connector.id,
            str(payload.get("vendor_schema_version") or "1.0.0"),
            dict(payload.get("field_map") or {"status": "status", "task_id": "refs.task_id"}),
            MappingState.ACTIVE,
            timestamp,
            timestamp,
            status_map=status_map,
            reopen_policy=reopen_policy,
            unknown_status_policy=unknown_status_policy,
            fallback_status=fallback_status,
            mapping_version=mapping_version,
        )
        self.store.put_mapping(mapping)
        self.store.remember(scope, "register_connector", key, command_payload, connector.id)
        self.emit("ConnectorRegistered", connector.public(), scope, actor, correlation_id, key, connector.id, [])
        return connector
    
    def validate_connector(self, scope: Scope, actor: str, correlation_id: str, key: str, connector_id: str) -> Connector:
        self._require_key(key)
        payload = {"connector_id": connector_id}
        prior = self.store.idempotent(scope, "validate_connector", key, payload)
        if prior:
            return self.store.get_connector(prior, scope)
        connector = self.store.get_connector(connector_id, scope)
        connector.status = ConnectorState.VALIDATING
        connector.updated_at = now()
        if not connector.capabilities:
            connector.status = ConnectorState.FAILED
            self.store.put_connector(connector)
            raise ValidationError("connector has no capabilities")
        if not connector.credential_fingerprint:
            connector.status = ConnectorState.FAILED
            self.store.put_connector(connector)
            raise ValidationError("connector credential is missing")
        connector.status = ConnectorState.READY
        connector.version += 1
        connector.updated_at = now()
        self.store.put_connector(connector)
        self.store.remember(scope, "validate_connector", key, payload, connector.id)
        self.emit("ConnectorValidated", connector.public(), scope, actor, correlation_id, key, connector.id, [])
        self.emit("CapabilityChanged", {"connector_id": connector.id, "capabilities": connector.capabilities}, scope, actor, correlation_id, key, connector.id, [])
        return connector
    
    def rotate_credential(self, scope: Scope, actor: str, correlation_id: str, key: str, connector_id: str, credential: str) -> Connector:
        self._require_key(key)
        if not credential:
            raise ValidationError("credential is required")
        payload = {"connector_id": connector_id, "credential": digest(credential)}
        prior = self.store.idempotent(scope, "rotate_credential", key, payload)
        if prior:
            return self.store.get_connector(prior, scope)
        connector = self.store.get_connector(connector_id, scope)
        connector.credential_fingerprint = payload["credential"]
        connector.version += 1
        connector.updated_at = now()
        if connector.status == ConnectorState.REVOKED:
            raise ConflictError("revoked connector cannot rotate credentials")
        self.store.put_connector(connector)
        self.store.remember(scope, "rotate_credential", key, payload, connector.id)
        return connector
    
    def _active_mapping(self, scope: Scope, connector_id: str) -> AdapterMapping | None:
        mappings = self.store.list_mappings(scope, connector_id)
        return next((item for item in mappings if item.status == MappingState.ACTIVE), None)
    
    def discover_capabilities(self, scope: Scope) -> list[dict[str, Any]]:
        return [
            {
                "connector_id": connector.id,
                "vendor": connector.vendor,
                "capabilities": connector.capabilities,
                "status": connector.status.value,
                "trust_level": connector.trust_level,
            }
            for connector in self.store.list_connectors(scope)
            if connector.status == ConnectorState.READY
        ]
    
    def get_connector_health(self, scope: Scope, connector_id: str) -> dict[str, Any]:
        connector = self.store.get_connector(connector_id, scope)
        return {
            "connector": connector.public(),
            "ready": connector.status == ConnectorState.READY,
            "delivery_count": len(self.store.list_deliveries(scope)),
            "dead_letter_count": len(self.store.list_dead_letters(scope)),
        }
    
    def list_subscriptions(self, scope: Scope) -> list[Subscription]:
        return self.store.list_subscriptions(scope)
    
    def get_dead_letter_queue(self, scope: Scope) -> list[DeadLetterRecord]:
        return self.store.list_dead_letters(scope)
    
    def get_adapter_mapping(self, scope: Scope, connector_id: str) -> list[AdapterMapping]:
        self.store.get_connector(connector_id, scope)
        return self.store.list_mappings(scope, connector_id)
