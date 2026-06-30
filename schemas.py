from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel
from uuid import UUID
from typing import Optional # Import Optional for ItemRead

class ItemBase(BaseModel):
    """Item作成・共通の基本スキーマ。"""
    series_name: str
    character_name: str
    exchange_method: str | None = "手渡し"
    handover_place: str | None = None
    condition: str | None = None
    image_url: str | None = None
    image_front_url: str | None = None
    image_left_url: str | None = None
    image_right_url: str | None = None
    image_back_url: str | None = None

class ItemCreate(ItemBase):
    """POST /items/ で受け取るリクエストボディ。"""
    status: str = "available"
    condition: str

class ItemUpdate(BaseModel):
    """アイテム編集用の更新スキーマ。"""
    series_name: str | None = None
    character_name: str | None = None
    exchange_method: str | None = None
    handover_place: str | None = None

class ItemRead(ItemBase):
    """レスポンス用のItemスキーマ。"""
    id: str
    owner_id: str
    status: str
    exchange_method: str | None = None
    handover_place: str | None = None
    condition: Optional[str] = None
    image_url: str | None = None
    image_front_url: str | None = None
    image_left_url: str | None = None
    image_right_url: str | None = None
    image_back_url: str | None = None

    class Config:
        from_attributes = True  # Pydantic V2用に orm_mode から変更

# ==========================================
# ページネーション（一覧取得）用のスキーマを追加
# ==========================================
class ItemMetadata(BaseModel):
    total_items: int
    total_pages: int
    current_page: int
    limit: int

class ItemListResponse(BaseModel):
    data: list[ItemRead]
    meta: ItemMetadata

# ==========================================

class TradeBase(BaseModel):
    """Trade作成・共通の基本スキーマ。"""
    item_id: str
    applicant_id: str
    proposal_front_url: str | None = None
    proposal_left_url: str | None = None
    proposal_right_url: str | None = None
    proposal_back_url: str | None = None
    proposed_item_id: str | None = None

class TradeCreate(TradeBase):
    """POST /items/{item_id}/trade で受け取るリクエストボディ。"""
    pass

class TradeStatusUpdate(BaseModel):
    status: str

class TradeRead(TradeBase):
    """レスポンス用のTradeスキーマ。"""
    id: str
    status: str
    applicant_name: str | None = None
    proposal_front_url: str | None = None
    proposal_left_url: str | None = None
    proposal_right_url: str | None = None
    proposal_back_url: str | None = None
    proposed_item_id: str | None = None
    created_at: datetime | None = None
    target_series_name: str | None = None
    target_character_name: str | None = None
    proposed_series_name: str | None = None
    proposed_character_name: str | None = None
    class Config:
        from_attributes = True  # Pydantic V2用に変更

class UserBase(BaseModel):
    """Userの基本スキーマ。"""
    name: str
    prefecture: str

class UserCreate(UserBase):
    """POST /users/ で受け取るリクエストボディ。"""
    email: str | None = None
    avatar_url: str | None = None

class UserUpdate(UserBase):
    """PUT /users/me で受け取るプロフィール更新用のスキーマ。"""
    pass

class UserRead(UserBase):
    id: str
    avatar_url: str | None = None
    average_rating: float | None = None
    rating_count: int = 0

    class Config:
        from_attributes = True  # Pydantic V2用に変更


class MessageBase(BaseModel):
    """Tradeに紐づくメッセージの共通スキーマ。"""
    trade_id: str
    sender_id: str
    text: str

class MessageCreate(BaseModel):
    """POST /messages などで受け取るリクエストボディ。"""
    trade_id: str
    text: str

class MessageRead(MessageBase):
    id: str
    sent_at: datetime
    sender_name: str | None = None

    class Config:
        from_attributes = True  # Pydantic V2用に変更


class ReportBase(BaseModel):
    reported_item_id: str
    reason: str

class ReportCreate(ReportBase):
    """POST /reports で受け取る通報データ。"""
    pass

class ReportRead(ReportBase):
    id: str
    reporter_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class RatingBase(BaseModel):
    trade_id: str
    score: int
    comment: str | None = None


class RatingCreate(RatingBase):
    """POST /ratings で受け取る評価データ。"""
    pass


class RatingRead(RatingBase):
    id: str
    reviewer_id: str
    rated_user_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class CatalogPair(BaseModel):
    """シリーズ名とキャラクター名のペアを返すスキーマ。"""
    series_name: str
    character_name: str


class NotificationBase(BaseModel):
    title: str
    message: str
    type: str


class NotificationCreate(NotificationBase):
    user_id: str | None = None


class NotificationRead(NotificationBase):
    id: str
    user_id: str | None = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BlockBase(BaseModel):
    blocked_id: str


class BlockCreate(BlockBase):
    """POST /blocks で受け取るブロック作成データ。"""
    pass


class BlockRead(BlockBase):
    id: str
    blocker_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# 管理画面（Admin Dashboard）用スキーマ
# ==========================================

class UserAdminRead(BaseModel):
    """管理画面のユーザー一覧で使用する、is_admin / is_banned を含むスキーマ。"""
    id: str
    name: str
    prefecture: str
    avatar_url: str | None = None
    is_admin: bool = False
    is_banned: bool = False

    class Config:
        from_attributes = True


class ReportAdminRead(BaseModel):
    """管理画面の通報一覧で使用するスキーマ。通報元・対象アイテム・関連取引の情報も含む。"""
    id: str
    reporter_id: str
    reported_item_id: str
    reason: str
    status: str
    created_at: datetime
    reporter_name: str | None = None
    reported_item_series_name: str | None = None
    reported_item_character_name: str | None = None
    related_trade_id: str | None = None  # 通報対象アイテムに紐づく取引があればそのID

    class Config:
        from_attributes = True


class ReportAdminUpdate(BaseModel):
    """PATCH /admin/reports/{report_id} で受け取る通報ステータス更新スキーマ。"""
    status: str


class NotificationBroadcastCreate(BaseModel):
    """POST /admin/notifications で受け取る全体お知らせ配信用スキーマ。"""
    title: str
    message: str


class AdminStats(BaseModel):
    """GET /admin/stats のレスポンススキーマ。"""
    total_users: int
    total_active_items: int
    reports_today: int
    completed_trades: int


class AdminTradeMessageRead(BaseModel):
    """GET /admin/trades/{trade_id}/messages のレスポンススキーマ。"""
    id: str
    trade_id: str
    sender_id: str
    sender_name: str | None = None
    text: str
    sent_at: datetime

    class Config:
        from_attributes = True
