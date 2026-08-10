import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "rule_engine_service.api:app",
        factory=True,
        port=int(os.environ.get("ASTLOOM_RULE_ENGINE_PORT", "32150")),
    )
