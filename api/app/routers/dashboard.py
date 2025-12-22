import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.dual_auth import get_dual_auth_user
from ..config.database import get_db
from ..utils.s3_utils import (
    load_documents_metadata,
    load_videos_metadata,
)
from ..utils.db_utils import get_notes_by_user_id

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
)


def _parse_timestamp(value: str | None) -> float:
    """Parse a timestamp string into a sortable float.

    Falls back to 0 on any error so items without dates naturally sink to the end.
    """

    if not value:
        return 0.0
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).timestamp()
        except Exception:
            continue
    return 0.0


@router.get("/summary")
async def get_dashboard_summary(
    auth_result: dict = Depends(get_dual_auth_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Fast summary endpoint for dashboard stats and recent items.

    This avoids multiple heavy list endpoints on the frontend by:
    - Loading documents, videos, and notes metadata directly from S3
    - Computing aggregate stats and small recent lists server‑side
    """

    try:
        user_id = auth_result.get("user_data", {}).get("sub", "anonymous")

        documents = load_documents_metadata()
        videos = load_videos_metadata()

        # Notes are stored per-user in the database; count only this user's notes
        try:
            user_notes = get_notes_by_user_id(db, user_id)
            notes_count = len(user_notes)
        except Exception as notes_exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to load notes for user %s: %s", user_id, notes_exc)
            notes_count = 0

        documents_total = len(documents)
        documents_processed = sum(1 for d in documents if d.get("processed"))
        documents_unprocessed = documents_total - documents_processed

        # Recent documents
        sorted_docs = sorted(
            documents,
            key=lambda d: _parse_timestamp(d.get("uploadDate")),
            reverse=True,
        )[:5]

        recent_documents: List[Dict[str, Any]] = []
        for doc in sorted_docs:
            folder = doc.get("folderStructure", {}) or {}
            subject = folder.get("subjectName") or "Unknown Subject"
            unit = folder.get("unitName")
            subject_label = f"{subject} - {unit}" if unit else subject

            status: str
            if doc.get("processed"):
                status = "processed"
            elif doc.get("processing"):
                status = "processing"
            else:
                status = "pending"

            recent_documents.append(
                {
                    "title": doc.get("fileName") or "Untitled Document",
                    "subject": subject_label,
                    "status": status,
                }
            )

        # Recent videos
        sorted_videos = sorted(
            videos,
            key=lambda v: _parse_timestamp(v.get("dateAdded")),
            reverse=True,
        )[:5]

        recent_videos: List[Dict[str, Any]] = []
        for video in sorted_videos:
            folder = video.get("folderStructure", {}) or {}
            subject = folder.get("subjectName") or "Unknown Subject"
            topic = folder.get("topic")
            title = topic or "Untitled Video"

            recent_videos.append(
                {
                    "title": title,
                    "subject": subject,
                    "platform": video.get("platform") or "Unknown",
                }
            )

        summary = {
            "stats": {
                "documentsTotal": documents_total,
                "documentsProcessed": documents_processed,
                "documentsUnprocessed": documents_unprocessed,
                "videos": len(videos),
                "notes": notes_count,
                # Placeholder for now – adjust when you have a source for this
                "universityContent": 0,
            },
            "recentDocuments": recent_documents,
            "recentVideos": recent_videos,
            "user": {
                "id": user_id,
            },
        }

        return summary

    except HTTPException:
        # Let FastAPI handle already created HTTPExceptions
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to build dashboard summary: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load dashboard summary") from exc
