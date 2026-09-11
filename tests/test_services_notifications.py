from app.models import Notification
from app.services import notifications


def test_notify_creates_unread_in_app_notification(db_session, user_factory):
    user = user_factory()

    notifications.notify(db_session, user, "Actividad publicada")
    db_session.commit()

    notification = db_session.query(Notification).one()
    assert notification.user_id == user.id
    assert notification.mensaje == "Actividad publicada"
    assert notification.leido is False


def test_notify_sends_email_only_when_subject_is_provided(
    db_session, user_factory, monkeypatch
):
    user = user_factory(email="ana@example.com")
    sent = []
    monkeypatch.setattr(
        notifications,
        "send_email",
        lambda to, subject, body: sent.append((to, subject, body)),
    )

    notifications.notify(db_session, user, "Recordatorio", email_subject="Actividad próxima")
    db_session.commit()

    assert sent == [("ana@example.com", "Actividad próxima", "Recordatorio")]


def test_unread_count_excludes_read_notifications(db_session, user_factory):
    user = user_factory()
    db_session.add_all(
        [
            Notification(user_id=user.id, mensaje="No leída"),
            Notification(user_id=user.id, mensaje="Leída", leido=True),
        ]
    )
    db_session.commit()

    assert notifications.unread_count(db_session, user.id) == 1