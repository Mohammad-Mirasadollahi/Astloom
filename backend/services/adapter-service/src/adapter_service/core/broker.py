from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from .constants import ALLOWED_INTENTS, REQUIRED_MESSAGE_FIELDS
from .enums import ConnectorState, DeliveryState, MappingState, SubscriptionState
from .errors import ConflictError, ValidationError
from .helpers import channel_for, nested, now, sanitize
from .models import (
    AdapterMapping,
    BrokerEvent,
    Connector,
    DeadLetterRecord,
    Delivery,
    Scope,
    Subscription,
)


class BrokerCommands:
    def subscribe(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> Subscription:
        self._require_key(key)
        payload = sanitize(payload)
        missing = [field for field in ("channel", "subscriber_type", "endpoint") if not payload.get(field)]
        if missing:
            raise ValidationError("missing required fields: " + ", ".join(missing))
        command_payload = {
            "channel": payload["channel"],
            "subscriber_type": payload["subscriber_type"],
            "endpoint": payload["endpoint"],
            "filter_intents": sorted(set(payload.get("filter_intents") or [])),
            "filter_domains": sorted(set(payload.get("filter_domains") or [])),
            "fail_mode": payload.get("fail_mode") or "none",
        }
        prior = self.store.idempotent(scope, "subscribe", key, command_payload)
        if prior:
            return self.store.get_subscription(prior, scope)
        timestamp = now()
        subscription = Subscription(
            str(uuid4()),
            scope,
            actor,
            correlation_id,
            command_payload["channel"],
            command_payload["subscriber_type"],
            command_payload["endpoint"],
            command_payload["filter_intents"],
            command_payload["filter_domains"],
            SubscriptionState.ACTIVE,
            command_payload["fail_mode"],
            timestamp,
            timestamp,
        )
        self.store.put_subscription(subscription)
        self.store.remember(scope, "subscribe", key, command_payload, subscription.id)
        return subscription
    
    def normalize_vendor_event(self, scope: Scope, actor: str, correlation_id: str, key: str, connector_id: str, vendor_payload: dict[str, Any]) -> dict[str, Any]:
        self._require_key(key)
        connector = self.store.get_connector(connector_id, scope)
        if connector.status != ConnectorState.READY:
            raise ConflictError("connector is not ready")
        mappings = self.store.list_mappings(scope, connector_id)
        mapping = next((item for item in mappings if item.status == MappingState.ACTIVE), None)
        if mapping is None:
            raise ValidationError("active adapter mapping is required")
        vendor_payload = sanitize(vendor_payload)
        command_payload = {"connector_id": connector_id, "vendor_payload": vendor_payload}
        prior = self.store.idempotent(scope, "normalize_vendor_event", key, command_payload)
        if prior:
            return {"message": json.loads(prior), "connector_id": connector_id}
        message = self._vendor_to_universal(scope, connector, mapping, vendor_payload, correlation_id)
        self.validate_message(message, scope)
        self.store.remember(scope, "normalize_vendor_event", key, command_payload, json.dumps(message, sort_keys=True))
        self.emit("AdapterNormalizedOutput", {"connector_id": connector_id, "message": message}, scope, actor, correlation_id, key, message["message_id"], message.get("refs") or [])
        return {"message": message, "connector_id": connector_id}
    
    def publish_agent_event(self, scope: Scope, actor: str, correlation_id: str, key: str, message: dict[str, Any]) -> dict[str, Any]:
        self._require_key(key)
        message = sanitize(message)
        command_payload = {"message": message}
        prior = self.store.idempotent(scope, "publish_agent_event", key, command_payload)
        if prior:
            event = self.store.get_event(prior, scope)
            return self._publish_result(event)
        validated = self.validate_message(message, scope)
        channel = channel_for(validated["intent"], validated["domain"])
        timestamp = now()
        event = BrokerEvent(str(uuid4()), scope, channel, validated, timestamp)
        self.store.put_event(event)
        self.store.remember(scope, "publish_agent_event", key, command_payload, event.id)
        self.emit("AgentEventReceived", event.public(), scope, actor, correlation_id, key, event.id, validated.get("refs") or [])
        self.emit("BrokerEventPublished", event.public(), scope, actor, correlation_id, key, event.id, validated.get("refs") or [])
        deliveries = self._deliver(scope, event)
        department_tasks = self._trigger_department_workflows(scope, validated, event.id)
        result = self._publish_result(event)
        result["deliveries"] = [item.public() for item in deliveries]
        result["department_tasks"] = [item.public() for item in department_tasks]
        return result
    
    def replay(self, scope: Scope, actor: str, correlation_id: str, key: str, channel: str | None = None) -> dict[str, Any]:
        self._require_key(key)
        payload = {"channel": channel}
        prior = self.store.idempotent(scope, "replay", key, payload)
        if prior:
            return json.loads(prior)
        events = self.store.list_events(scope, channel)
        replayed = []
        for event in events:
            deliveries = self._deliver(scope, event, replay=True)
            replayed.append({"event_id": event.id, "deliveries": [item.public() for item in deliveries]})
        result = {"replayed_count": len(replayed), "items": replayed}
        self.store.remember(scope, "replay", key, payload, json.dumps(result, sort_keys=True))
        return result
    
    def validate_message(self, message: dict[str, Any], scope: Scope) -> dict[str, Any]:
        if not isinstance(message, dict):
            raise ValidationError("message must be an object")
        missing = [field for field in REQUIRED_MESSAGE_FIELDS if field not in message]
        if missing:
            raise ValidationError("missing required fields: " + ", ".join(missing))
        if message["schema_version"] != "1.0.0":
            raise ValidationError("unsupported schema_version")
        if message["intent"] not in ALLOWED_INTENTS:
            raise ValidationError("unsupported intent")
        if message["tenant_id"] != scope.tenant_id or message["project_id"] != scope.project_id:
            raise ValidationError("message scope does not match request scope")
        if not isinstance(message["payload"], dict):
            raise ValidationError("payload must be an object")
        if not isinstance(message["refs"], list):
            raise ValidationError("refs must be a list")
        if message.get("sender_type") not in {"agent", "ide", "human", "adapter", "system"}:
            raise ValidationError("invalid sender_type")
        return message
    
    def list_subscriptions(self, scope: Scope) -> list[Subscription]:
        return self.store.list_subscriptions(scope)
    
    def get_dead_letter_queue(self, scope: Scope) -> list[DeadLetterRecord]:
        return self.store.list_dead_letters(scope)
    
    def _vendor_to_universal(
        self,
        scope: Scope,
        connector: Connector,
        mapping: AdapterMapping,
        vendor_payload: dict[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]:
        status = vendor_payload.get(mapping.field_map.get("status", "status")) or vendor_payload.get("status") or "in_progress"
        task_id = vendor_payload.get("task_id") or nested(vendor_payload, mapping.field_map.get("task_id", "task_id"))
        intent = str(vendor_payload.get("intent") or "TASK_STARTED")
        return {
            "message_id": str(vendor_payload.get("id") or uuid4()),
            "schema_version": "1.0.0",
            "sender": connector.vendor,
            "sender_type": "adapter",
            "tenant_id": scope.tenant_id,
            "project_id": scope.project_id,
            "intent": intent,
            "domain": str(vendor_payload.get("domain") or "engineering"),
            "payload": {
                "vendor": connector.vendor,
                "raw_status": status,
                "summary": vendor_payload.get("summary") or vendor_payload.get("message") or "",
                "normalized_by": mapping.id,
            },
            "status": str(status),
            "refs": [value for value in [task_id, connector.id] if value],
            "correlation_id": str(vendor_payload.get("correlation_id") or correlation_id),
            "created_at": now(),
            "idempotency_key": vendor_payload.get("idempotency_key"),
        }
    
    def _deliver(self, scope: Scope, event: BrokerEvent, replay: bool = False) -> list[Delivery]:
        deliveries: list[Delivery] = []
        timestamp = now()
        for subscription in self.store.list_subscriptions(scope):
            if subscription.status != SubscriptionState.ACTIVE:
                continue
            if subscription.channel != event.channel and subscription.channel != "*":
                continue
            intent = event.message["intent"]
            domain = event.message["domain"]
            if subscription.filter_intents and intent not in subscription.filter_intents:
                continue
            if subscription.filter_domains and domain not in subscription.filter_domains:
                continue
            # fail_mode=unauthorized denies without a schema ACL column; upgrade to ACL table if needed.
            if subscription.fail_mode == "unauthorized":
                continue
            delivery = Delivery(str(uuid4()), scope, event.id, subscription.id, DeliveryState.PENDING, 1, None, timestamp, timestamp)
            if subscription.fail_mode == "always" and not replay:
                delivery.status = DeliveryState.RETRYING
                delivery.attempts = self.max_delivery_attempts
                delivery.last_error = "subscriber endpoint failed"
                delivery.status = DeliveryState.DEAD_LETTERED
                delivery.updated_at = now()
                self.store.put_delivery(delivery)
                dead = DeadLetterRecord(str(uuid4()), scope, event.id, subscription.id, delivery.last_error, event.message, now())
                self.store.put_dead_letter(dead)
                self.emit("BrokerDeliveryFailed", dead.public(), scope, "broker", event.message.get("correlation_id") or "", "", dead.id, event.message.get("refs") or [])
                self.emit("DeadLetterCreated", dead.public(), scope, "broker", event.message.get("correlation_id") or "", "", dead.id, event.message.get("refs") or [])
            else:
                delivery.status = DeliveryState.DELIVERED
                delivery.updated_at = now()
                self.store.put_delivery(delivery)
                if subscription.subscriber_type == "ide":
                    self.emit("IdeNotificationSent", {"subscription_id": subscription.id, "event_id": event.id, "endpoint": subscription.endpoint}, scope, "broker", event.message.get("correlation_id") or "", "", delivery.id, event.message.get("refs") or [])
            deliveries.append(delivery)
        return deliveries
    
    def _publish_result(self, event: BrokerEvent) -> dict[str, Any]:
        return {"event": event.public(), "channel": event.channel}
