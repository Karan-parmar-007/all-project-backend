# app/core/constants.py
from enum import Enum


class ProjectStatus(str, Enum):
    LIVE = "live"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ARCHIVED = "archived"


class ApMediaKind(str, Enum):
    PROJECT_COVER = "project_cover"
    PROJECT_SCREENSHOT = "project_screenshot"


AP_MEDIA_KIND_PREFIX: dict[ApMediaKind, str] = {
    ApMediaKind.PROJECT_COVER: "apps/covers",
    ApMediaKind.PROJECT_SCREENSHOT: "apps/screenshots",
}
