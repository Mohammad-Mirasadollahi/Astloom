import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "project_profile_service.api:app",
        factory=True,
        port=int(os.environ.get("ASTLOOM_PROJECT_PROFILE_PORT", "32194")),
    )
