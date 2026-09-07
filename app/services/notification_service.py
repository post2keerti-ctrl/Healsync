"""
Notification service — layer 10 of the architecture (Firebase Cloud Messaging).

Production: sends a real push notification via FCM to the user's registered
device token (collected by the Flutter app and stored on the user's profile).

Local/sandbox fallback: when Firebase isn't configured, or the user has no
device token registered yet, the notification is written to the
`notifications` collection instead so you can still see and demo the
alert/notification flow end-to-end.
"""
from datetime import datetime
from typing import Dict

from .. import config
from .. import database as db


def send(user_id: str, title: str, body: str, device_token: str = "") -> Dict:
    record = {
        "user_id": user_id, "title": title, "body": body,
        "sent_at": datetime.utcnow(), "channel": "fcm" if config.USE_REAL_FIREBASE and device_token else "local-log",
    }

    if config.USE_REAL_FIREBASE and device_token:
        try:
            from firebase_admin import messaging
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=device_token,
            )
            messaging.send(message)
            record["status"] = "sent"
        except Exception as exc:
            record["status"] = f"failed: {exc}"
    else:
        record["status"] = "logged (no FCM device token / Firebase not configured)"
        print(f"[notification_service] {title} — {body} (user={user_id})")

    db.notifications.insert_one(record)
    return record
