from __future__ import annotations

REQUIRED_MESSAGE_FIELDS = (
    "message_id",
    "schema_version",
    "sender",
    "sender_type",
    "tenant_id",
    "project_id",
    "intent",
    "domain",
    "payload",
    "status",
    "refs",
    "correlation_id",
    "created_at",
)

ALLOWED_INTENTS = {
    "TASK_STARTED",
    "TASK_COMPLETED",
    "TASK_BLOCKED",
    "API_READY",
    "DOC_DRIFT_FOUND",
    "TEST_FAILURE_DETECTED",
    "HUMAN_APPROVAL_REQUIRED",
    "APPROVAL_RESOLVED",
    "DEPLOYMENT_COMPLETED",
    "DOWNSTREAM_TASK_REQUESTED",
    "CODE_RELEASED",
}

DEPARTMENT_TRIGGERS = {
    "CODE_RELEASED": ("marketing", "support", "devops"),
    "DEPLOYMENT_COMPLETED": ("support", "devops"),
    "API_READY": ("frontend", "docs"),
}

CLEARANCE_RANK = {"public": 0, "internal": 1, "restricted": 2}
