-- Optional index for AgentTicket document kind lookups.
CREATE INDEX IF NOT EXISTS orchestration_documents_agent_ticket_scope_idx
    ON orchestration.documents (tenant_id, workspace_id, project_id, id)
    WHERE kind = 'agent_ticket';
