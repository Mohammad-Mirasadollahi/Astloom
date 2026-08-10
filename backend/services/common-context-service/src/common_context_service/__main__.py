import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "common_context_service.api:app",
        factory=True,
        port=int(os.environ.get("ASTLOOM_COMMON_CONTEXT_PORT", "32195")),
    )
