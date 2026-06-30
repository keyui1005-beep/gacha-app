from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemyのベースクラス。すべてのモデルはこのクラスを継承します。"""


class User(Base):
    """ユーザー情報を保存するテーブル。"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    prefecture: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_users_prefecture", "prefecture"),
    )

    # UserとItemのリレーション。1人のユーザーが複数の出品アイテムを持てます。
    items: Mapped[list[Item]] = relationship(
        "Item",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # UserとMessageのリレーション。1人のユーザーが複数のメッセージを送信できます。
    messages_sent: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="sender",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Userが受け取った評価と送信した評価を取得するためのリレーション。
    ratings_given: Mapped[list[Rating]] = relationship(
        "Rating",
        foreign_keys="Rating.reviewer_id",
        back_populates="reviewer",
        lazy="selectin",
    )
    ratings_received: Mapped[list[Rating]] = relationship(
        "Rating",
        foreign_keys="Rating.rated_user_id",
        back_populates="rated_user",
        lazy="selectin",
    )

    @property
    def average_rating(self) -> float | None:
        if not getattr(self, 'ratings_received', None):
            return None
        scores = [rating.score for rating in self.ratings_received if rating.score is not None]
        if not scores:
            return None
        return sum(scores) / len(scores)

    @property
    def rating_count(self) -> int:
        if not getattr(self, 'ratings_received', None):
            return 0
        return len([rating for rating in self.ratings_received if rating.score is not None])


class Item(Base):
    """ガチャ景品の出品情報を保存するテーブル。"""

    __tablename__ = "items"
    
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    series_name: Mapped[str] = mapped_column(String, nullable=False)
    character_name: Mapped[str] = mapped_column(String, nullable=False)
    exchange_method: Mapped[str | None] = mapped_column(String, nullable=True)
    handover_place: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    image_front_url: Mapped[str | None] = mapped_column(String, nullable=True)
    image_left_url: Mapped[str | None] = mapped_column(String, nullable=True)
    image_right_url: Mapped[str | None] = mapped_column(String, nullable=True)
    image_back_url: Mapped[str | None] = mapped_column(String, nullable=True)
    condition: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="available")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_items_status", "status"),
        Index("idx_items_created_at", "created_at"),
    )

    # ItemからUserへアクセスできるようにするリレーション。
    owner: Mapped[User] = relationship("User", back_populates="items")

    # ItemとTradeのリレーション。1つのアイテムが複数の取引申請を持つ場合があります。
    trades: Mapped[list[Trade]] = relationship(
        "Trade",
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Trade(Base):
    """ユーザー間のアイテム交換申請情報を保存するテーブル。"""

    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False
    )
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("items.id"), nullable=False
    )
    applicant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    proposed_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    proposal_front_url: Mapped[str | None] = mapped_column(String, nullable=True)
    proposal_left_url: Mapped[str | None] = mapped_column(String, nullable=True)
    proposal_right_url: Mapped[str | None] = mapped_column(String, nullable=True)
    proposal_back_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # TradeからItemへアクセスするリレーション。
    item: Mapped[Item] = relationship("Item", back_populates="trades")

    # Tradeからapplicantユーザーへアクセスするリレーション。
    applicant: Mapped[User] = relationship("User", foreign_keys=[applicant_id])

    # Tradeに紐づくチャットメッセージ。
    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="trade",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Message(Base):
    """トレードに紐づくチャットメッセージを保存するテーブル。"""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False
    )
    trade_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trades.id"), nullable=False
    )
    sender_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(String, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    trade: Mapped[Trade] = relationship("Trade", back_populates="messages")
    sender: Mapped[User] = relationship("User", back_populates="messages_sent")


class Report(Base):
    """ユーザーによる通報内容を保存するテーブル。"""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False
    )
    reporter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    reported_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("items.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    reporter: Mapped[User] = relationship("User")
    reported_item: Mapped[Item] = relationship("Item")


class Rating(Base):
    """完了した取引に対する星評価を保存するテーブル。"""

    __tablename__ = "ratings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False
    )
    trade_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trades.id"), nullable=False
    )
    reviewer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    rated_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    trade: Mapped[Trade] = relationship("Trade")
    reviewer: Mapped[User] = relationship("User", foreign_keys=[reviewer_id], back_populates="ratings_given")
    rated_user: Mapped[User] = relationship("User", foreign_keys=[rated_user_id], back_populates="ratings_received")


class Notification(Base):
    """通知情報を保存するテーブル。"""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # 例: "trade_request", "trade_update", "info"
    is_read: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)  # SQLiteではBoolean型をIntegerで表現
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship("User", backref="notifications")


class Block(Base):
    """ユーザー間のブロック情報を保存するテーブル。"""

    __tablename__ = "blocks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False
    )
    # ブロックした側のユーザーID
    blocker_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    # ブロックされた側のユーザーID
    blocked_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # 同じペアを重複してブロックできないようにユニーク制約とインデックスを設定
    __table_args__ = (
        Index("idx_blocks_blocker_blocked", "blocker_id", "blocked_id", unique=True),
    )
