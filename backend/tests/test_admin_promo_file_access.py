from pathlib import Path
from urllib.parse import unquote

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, UserShareTaskSubmission


def test_admin_can_download_like_submission_screenshot(client, db_session: Session, admin_override) -> None:
    settings = get_settings()
    promo_dir = settings.upload_dir / "promo" / "like"
    promo_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = promo_dir / "admin-review-proof.png"
    screenshot_path.write_bytes(b"promo-image-binary")

    user = User(phone="13800003001", nickname="proof-user", credits=0, source="web", is_banned=False)
    db_session.add(user)
    db_session.flush()
    row = UserShareTaskSubmission(
        user_id=user.id,
        platform="wechat",
        screenshot_path="uploads/promo/like/admin-review-proof.png",
        original_filename="proof.png",
        share_text="审核截图",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    resp = client.get(f"/api/v1/admin/promo/like-submissions/{row.id}/screenshot")
    assert resp.status_code == 200
    assert resp.content == b"promo-image-binary"
    assert "proof.png" in unquote(resp.headers.get("content-disposition", ""))


def test_admin_cannot_download_untrusted_like_submission_screenshot(client, db_session: Session, admin_override, tmp_path: Path) -> None:
    rogue_file = tmp_path / "rogue.png"
    rogue_file.write_bytes(b"rogue")

    user = User(phone="13800003002", nickname="rogue-user", credits=0, source="web", is_banned=False)
    db_session.add(user)
    db_session.flush()
    row = UserShareTaskSubmission(
        user_id=user.id,
        platform="wechat",
        screenshot_path=str(rogue_file),
        original_filename="rogue.png",
        share_text="不可信路径",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    resp = client.get(f"/api/v1/admin/promo/like-submissions/{row.id}/screenshot")
    assert resp.status_code == 403
