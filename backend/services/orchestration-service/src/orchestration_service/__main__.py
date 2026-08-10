import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "orchestration_service.api:app",
        factory=True,
        port=int(os.environ.get("ASTLOOM_ORCHESTRATION_PORT", "32192")),
    )
