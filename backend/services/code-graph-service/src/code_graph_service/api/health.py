"""Process health HTTP route."""

from fastapi import FastAPI


def register(api: FastAPI) -> None:
    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "code-graph-service"}
