from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, delete, desc, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from sqlalchemy.pool import StaticPool

from .config import AppConfig
from .models import PanelEvent, RawAlarmMessage


class Base(DeclarativeBase):
    pass


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    data_json: Mapped[str] = mapped_column(Text, default="{}")


class RawMessageRecord(Base):
    __tablename__ = "raw_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    raw: Mapped[str] = mapped_column(Text)


class ZoneRecord(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AppSettingRecord(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class NotificationSettingRecord(Base):
    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}")


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(32), default="viewer", index=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditLogRecord(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    actor: Mapped[str] = mapped_column(String(128), default="system")
    action: Mapped[str] = mapped_column(String(120), index=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")


class CustomButtonRecord(Base):
    __tablename__ = "custom_buttons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_username: Mapped[str] = mapped_column(String(128), index=True)
    label: Mapped[str] = mapped_column(String(80))
    command_value: Mapped[str] = mapped_column(Text)
    dangerous: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ApiTokenRecord(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    token_prefix: Mapped[str] = mapped_column(String(16), index=True)
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasskeyCredentialRecord(Base):
    __tablename__ = "passkey_credentials"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    username: Mapped[str] = mapped_column(String(128), ForeignKey("users.username", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="Passkey")
    public_key: Mapped[str] = mapped_column(Text)
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    aaguid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)



class Database:
    def __init__(self, config: AppConfig) -> None:
        connect_args = {"check_same_thread": False, "timeout": 10} if config.database_url.startswith("sqlite") else {}
        engine_args = {"connect_args": connect_args}
        if config.database_url == "sqlite:///:memory:":
            engine_args["poolclass"] = StaticPool
        self.engine = create_engine(config.database_url, **engine_args)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.config = config

    def init(self) -> None:
        Base.metadata.create_all(self.engine)
        if self.config.database_url.startswith("sqlite") and self.config.database_url != "sqlite:///:memory:":
            with self.engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL;"))
                conn.execute(text("PRAGMA synchronous=NORMAL;"))

    def get_setting(self, key: str) -> str | None:
        with self.session_factory() as session:
            record = session.get(AppSettingRecord, key)
            return record.value if record else None

    def session(self) -> Generator[Session, None, None]:
        with self.session_factory() as session:
            yield session


    def append_event(self, event: PanelEvent) -> None:
        import json

        with self.session_factory() as session:
            session.merge(
                EventRecord(
                    id=event.id,
                    timestamp=event.timestamp,
                    type=str(event.type),
                    message=event.message,
                    data_json=json.dumps(event.data, default=str),
                )
            )
            session.commit()

    def append_raw_message(self, message: RawAlarmMessage) -> None:
        with self.session_factory() as session:
            session.merge(RawMessageRecord(id=message.id, timestamp=message.timestamp, raw=message.raw))
            session.commit()

    def audit(self, actor: str, action: str, details: dict[str, object] | None = None) -> None:
        import json

        with self.session_factory() as session:
            session.add(
                AuditLogRecord(
                    actor=actor,
                    action=action,
                    details_json=json.dumps(details or {}, default=str),
                )
            )
            session.commit()

    def prune_retention(self) -> None:
        now = datetime.now(timezone.utc)
        raw_cutoff = now - timedelta(days=self.config.raw_retention_days)
        event_cutoff = now - timedelta(days=self.config.event_retention_days)
        with self.session_factory() as session:
            session.execute(delete(RawMessageRecord).where(RawMessageRecord.timestamp < raw_cutoff))
            session.execute(delete(EventRecord).where(EventRecord.timestamp < event_cutoff))
            session.commit()

    def list_events(self, limit: int = 50, offset: int = 0, type: str | None = None) -> list[EventRecord]:
        with self.session_factory() as session:
            query = select(EventRecord).order_by(desc(EventRecord.timestamp)).offset(offset).limit(limit)
            if type:
                query = query.where(EventRecord.type == type)
            return list(session.scalars(query).all())

    def list_raw_messages(self, limit: int = 50, offset: int = 0) -> list[RawMessageRecord]:
        with self.session_factory() as session:
            query = select(RawMessageRecord).order_by(desc(RawMessageRecord.timestamp)).offset(offset).limit(limit)
            return list(session.scalars(query).all())

    def list_audit(self, limit: int = 100, offset: int = 0) -> list[AuditLogRecord]:
        with self.session_factory() as session:
            query = select(AuditLogRecord).order_by(desc(AuditLogRecord.timestamp)).offset(offset).limit(limit)
            return list(session.scalars(query).all())

    def list_settings(self) -> list[AppSettingRecord]:
        with self.session_factory() as session:
            return list(session.scalars(select(AppSettingRecord).order_by(AppSettingRecord.key)).all())

    def upsert_settings(self, values: dict[str, str]) -> list[AppSettingRecord]:
        with self.session_factory() as session:
            for key, value in values.items():
                session.merge(AppSettingRecord(key=key, value=value))
            session.commit()
            return list(session.scalars(select(AppSettingRecord).order_by(AppSettingRecord.key)).all())

    def list_zones(self) -> list[ZoneRecord]:
        with self.session_factory() as session:
            return list(session.scalars(select(ZoneRecord).order_by(ZoneRecord.id)).all())

    def upsert_zones(self, zones: list[dict[str, object]]) -> list[ZoneRecord]:
        with self.session_factory() as session:
            for zone in zones:
                session.merge(
                    ZoneRecord(
                        id=int(zone["id"]),
                        name=str(zone.get("name", "")),
                        enabled=bool(zone.get("enabled", True)),
                    )
                )
            session.commit()
            return list(session.scalars(select(ZoneRecord).order_by(ZoneRecord.id)).all())

    def ensure_zone(self, zone_id: int) -> None:
        with self.session_factory() as session:
            if session.get(ZoneRecord, zone_id) is None:
                session.add(ZoneRecord(id=zone_id, name="", enabled=True))
                session.commit()

    def delete_zone(self, zone_id: int) -> bool:
        with self.session_factory() as session:
            record = session.get(ZoneRecord, zone_id)
            if record is not None:
                session.delete(record)
                session.commit()
                return True
            return False

    def list_notifications(self) -> list[NotificationSettingRecord]:
        with self.session_factory() as session:
            return list(session.scalars(select(NotificationSettingRecord).order_by(NotificationSettingRecord.id)).all())

    def replace_notifications(self, values: list[dict[str, object]]) -> list[NotificationSettingRecord]:
        with self.session_factory() as session:
            session.query(NotificationSettingRecord).delete()
            for value in values:
                session.add(
                    NotificationSettingRecord(
                        provider=str(value.get("provider", "webhook")),
                        enabled=bool(value.get("enabled", False)),
                        config_json=str(value.get("config_json", "{}")),
                    )
                )
            session.commit()
            return list(session.scalars(select(NotificationSettingRecord).order_by(NotificationSettingRecord.id)).all())

    def users_exist(self) -> bool:
        with self.session_factory() as session:
            return session.scalar(select(UserRecord.id).limit(1)) is not None

    def list_custom_buttons(self, username: str) -> list[CustomButtonRecord]:
        with self.session_factory() as session:
            query = (
                select(CustomButtonRecord)
                .where(CustomButtonRecord.owner_username == username)
                .order_by(CustomButtonRecord.sort_order, CustomButtonRecord.label)
            )
            return list(session.scalars(query).all())

    def get_custom_button(self, button_id: int) -> CustomButtonRecord | None:
        with self.session_factory() as session:
            return session.get(CustomButtonRecord, button_id)

    def upsert_custom_button(
        self,
        username: str,
        label: str,
        command_value: str,
        dangerous: bool,
        enabled: bool,
        sort_order: int = 0,
        button_id: int | None = None,
    ) -> CustomButtonRecord:
        with self.session_factory() as session:
            record = session.get(CustomButtonRecord, button_id) if button_id is not None else None
            if record is None:
                record = CustomButtonRecord(owner_username=username, label=label, command_value=command_value)
                session.add(record)
            record.owner_username = username
            record.label = label
            record.command_value = command_value
            record.dangerous = dangerous
            record.enabled = enabled
            record.sort_order = sort_order
            session.commit()
            session.refresh(record)
            return record

    def delete_custom_button(self, button_id: int) -> bool:
        with self.session_factory() as session:
            record = session.get(CustomButtonRecord, button_id)
            if record is None:
                return False
            session.delete(record)
            session.commit()
            return True

    def list_passkeys(self, username: str) -> list[PasskeyCredentialRecord]:
        with self.session_factory() as session:
            return list(session.scalars(select(PasskeyCredentialRecord).where(PasskeyCredentialRecord.username == username).order_by(desc(PasskeyCredentialRecord.created_at))).all())

    def get_passkey(self, credential_id: str) -> PasskeyCredentialRecord | None:
        with self.session_factory() as session:
            return session.get(PasskeyCredentialRecord, credential_id)

    def add_passkey(self, credential_id: str, username: str, name: str, public_key: str, aaguid: str | None = None) -> PasskeyCredentialRecord:
        with self.session_factory() as session:
            cred = PasskeyCredentialRecord(
                id=credential_id,
                username=username,
                name=name,
                public_key=public_key,
                aaguid=aaguid,
            )
            session.add(cred)
            session.commit()
            return cred

    def delete_passkey(self, credential_id: str, username: str) -> bool:
        with self.session_factory() as session:
            cred = session.get(PasskeyCredentialRecord, credential_id)
            if cred and cred.username == username:
                session.delete(cred)
                session.commit()
                return True
            return False

    def update_passkey_usage(self, credential_id: str, sign_count: int) -> None:
        with self.session_factory() as session:
            cred = session.get(PasskeyCredentialRecord, credential_id)
            if cred:
                cred.sign_count = sign_count
                cred.last_used_at = datetime.now(timezone.utc)
                session.commit()

