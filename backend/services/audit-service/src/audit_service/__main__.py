import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "audit_service.api:app",
        factory=True,
        port=int(os.environ.get("ASTLOOM_AUDIT_PORT", "32190")),
    )
