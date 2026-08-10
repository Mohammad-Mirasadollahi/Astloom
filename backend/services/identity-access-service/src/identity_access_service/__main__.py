import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "identity_access_service.api:app",
        factory=True,
        port=int(os.environ.get("ASTLOOM_IDENTITY_ACCESS_PORT", "32191")),
    )
