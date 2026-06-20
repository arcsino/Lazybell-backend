import base64
import hashlib
import logging
import re
import threading
from zoneinfo import ZoneInfo

import requests
from cryptography.fernet import Fernet
from django.conf import settings

logger = logging.getLogger(__name__)

DISCORD_WEBHOOK_RE = re.compile(
    r"^https://discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$"
)
APP_NAME = "Lazybell"
JST = ZoneInfo("Asia/Tokyo")


def _fernet() -> Fernet:
    material = getattr(settings, "WEBHOOK_ENCRYPT_KEY", settings.SECRET_KEY).encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(material).digest())
    return Fernet(key)


def validate_discord_url(url: str) -> bool:
    return bool(DISCORD_WEBHOOK_RE.match(url))


def encrypt_url(url: str) -> str:
    return _fernet().encrypt(url.encode()).decode()


def decrypt_url(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()


def _send_discord(url: str, payload: dict) -> bool:
    """POST payload to Discord webhook. Returns True on 2xx."""
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.error("Discord webhook send error: %s", e)
        return False


def _site_author() -> dict:
    base = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    icon_url = getattr(settings, "SITE_ICON_URL", "")
    author: dict = {"name": APP_NAME, "url": base}
    if icon_url:
        author["icon_url"] = icon_url
    return author


def test_webhook(url: str) -> bool:
    """Send a test embed to verify the webhook URL is reachable."""
    embed = {
        "author": _site_author(),
        "title": "Webhook 接続テスト",
        "description": f"**{APP_NAME}** との Webhook 接続が正常に確立されました。",
        "color": 0x57F287,
        "footer": {"text": APP_NAME},
    }
    return _send_discord(url, {"username": APP_NAME, "embeds": [embed]})


def _truncate(text: str | None, max_len: int = 300) -> str:
    if not text:
        return ""
    return text[:max_len] + "..." if len(text) > max_len else text


def _schedule_url(schedule) -> str:
    base = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    return f"{base}/groups/{schedule.group_id}/schedules/{schedule.id}"


def _format_deadline(schedule) -> str:
    if not schedule.deadline:
        return "期限なし"
    dt_jst = schedule.deadline.astimezone(JST)
    if schedule.is_all_day:
        return dt_jst.strftime("%Y年%m月%d日（終日）")
    return dt_jst.strftime("%Y年%m月%d日 %H:%M")


def _first_tag_color(schedule, default: int) -> int:
    try:
        relations = list(schedule.tag_relations.all())
        if relations:
            return int(relations[0].tag.color.lstrip("#"), 16)
    except (ValueError, AttributeError):
        pass
    return default


def _build_description(schedule) -> str:
    parts = []
    detail = _truncate(schedule.detail)
    if detail:
        parts.append(detail)

    tags = [tr.tag for tr in schedule.tag_relations.all()]
    if tags:
        parts.append("タグ: " + " ".join(f"`{t.name}`" for t in tags))

    if schedule.subject:
        parts.append(f"科目: `{schedule.subject.name}`")

    if schedule.deadline:
        parts.append(f"**締め切り: {_format_deadline(schedule)}**")

    return "\n".join(parts)


def build_remind_embed(schedule) -> dict:
    return {
        "author": _site_author(),
        "title": schedule.title,
        "url": _schedule_url(schedule),
        "description": _build_description(schedule),
        "color": _first_tag_color(schedule, 0xFFA500),
        "footer": {"text": f"作成者: {schedule.created_by.nickname}"},
    }


def build_created_log_embed(schedule) -> dict:
    return {
        "author": _site_author(),
        "title": schedule.title,
        "url": _schedule_url(schedule),
        "description": _build_description(schedule),
        "color": _first_tag_color(schedule, 0x3498DB),
        "footer": {"text": f"作成者: {schedule.created_by.nickname}"},
    }


def _do_notify_created_log(schedule_id: str) -> None:
    from groups.models import GroupWebhook
    from schedules.models import Schedule

    try:
        schedule = (
            Schedule.objects.filter(id=schedule_id, is_deleted=False)
            .select_related("group", "subject", "created_by")
            .prefetch_related("tag_relations__tag")
            .first()
        )
        if not schedule:
            return

        hooks = GroupWebhook.objects.filter(
            group=schedule.group,
            webhook_type=GroupWebhook.WebhookType.CREATED_LOG,
        )
        if not hooks.exists():
            return

        embed = build_created_log_embed(schedule)
        for hook in hooks:
            try:
                url = decrypt_url(hook.encrypted_url)
                _send_discord(url, {"username": APP_NAME, "embeds": [embed]})
            except Exception as e:
                logger.error(
                    "notify_created_log send error for hook %s: %s", hook.id, e
                )
    except Exception as e:
        logger.error("notify_created_log error for schedule %s: %s", schedule_id, e)


def notify_created_log(schedule) -> None:
    """Fire-and-forget: send created-log webhook in a background thread."""
    threading.Thread(
        target=_do_notify_created_log,
        args=(str(schedule.id),),
        daemon=True,
    ).start()
