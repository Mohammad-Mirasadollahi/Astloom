-- Persist LLM Judge reproducibility metadata on evaluations (GAP-T05).
ALTER TABLE rule_engine.evaluations
    ADD COLUMN IF NOT EXISTS judge_replay jsonb NOT NULL DEFAULT '{}'::jsonb;
