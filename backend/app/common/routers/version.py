"""Reports which build of the app is deployed."""

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api", tags=["version"])


class VersionResponse(BaseModel):
    """The deployed build, or None where deploys don't set one (local dev)."""

    version: str | None


@router.get("/version", response_model=VersionResponse)
def get_version(response: Response) -> VersionResponse:
    """
    Return the deployed version, which open tabs compare with their own build.

    Open to network guests because the DJ view needs it too. It reveals nothing
    private: the DJ view's footer already shows the version.

    :param response: Used to stop browsers caching the answer
    :return: The APP_VERSION the deploy set
    """
    response.headers["Cache-Control"] = "no-store"
    return VersionResponse(version=settings.app_version)
