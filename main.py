from __future__ import annotations

import os                  # ← 追加
import shutil
import base64
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4
from urllib.parse import quote

import filetype

from dotenv import load_dotenv  # ← 追加
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials, storage
import smtplib
from email.mime.text import MIMEText
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, create_engine, func, or_, text
from sqlalchemy.orm import Session, sessionmaker

from models import Base, Item, Trade, User, Message, Report, Rating, Notification, Block
from schemas import ItemCreate, ItemListResponse, ItemRead, ItemUpdate, TradeCreate, TradeRead, TradeStatusUpdate, UserCreate, UserRead, UserUpdate, MessageCreate, MessageRead, CatalogPair, ReportCreate, ReportRead, RatingCreate, RatingRead, BlockCreate, BlockRead, UserAdminRead, ReportAdminRead, ReportAdminUpdate, NotificationBroadcastCreate, AdminStats, AdminTradeMessageRead

load_dotenv()  # ← 追加：これで .env ファイルをこっそり読み込みます

# --- データベース接続先の決定 ---
# 環境変数 DATABASE_URL が設定されていれば本番用（PostgreSQLなど）として使用し、
# 設定されていなければ開発用としてSQLiteを使用する。
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gachagacha.db")

# Renderなどのプラットフォームが古い "postgres://" 形式で接続文字列を渡してくる場合がある。
# SQLAlchemy 1.4以降は "postgresql://" を要求するため、安全に置換する。
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

IS_SQLITE = DATABASE_URL.startswith("sqlite")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
UPLOADS_PREFIX = "/uploads"
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

# connect_args の check_same_thread はSQLite固有のオプションのため、
# SQLite接続時のみ適用する（PostgreSQL等に渡すとエラーになる）。
if IS_SQLITE:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# アプリ起動時にテーブルを自動作成します。
# PostgreSQLの場合、初回接続時にここで最新カラムを含むテーブルが生成されるため、
# 以下のSQLite向け即席マイグレーションは不要になる。
Base.metadata.create_all(bind=engine)

# 既存DBに新しいカラムがない場合は追加します。
# PRAGMA / sqlite_master はSQLite固有の構文でPostgreSQLではエラーになるため、
# SQLite接続時のみ実行する。
if IS_SQLITE:
    with engine.begin() as conn:
        result = conn.execute(text("PRAGMA table_info(items)"))
        columns = [row[1] for row in result.fetchall()]
        if 'exchange_method' not in columns:
            conn.execute(text("ALTER TABLE items ADD COLUMN exchange_method TEXT DEFAULT '手渡し'"))
        if 'handover_place' not in columns:
            conn.execute(text("ALTER TABLE items ADD COLUMN handover_place TEXT"))
        if 'image_url' not in columns:
            conn.execute(text("ALTER TABLE items ADD COLUMN image_url TEXT"))
        if 'condition' not in columns:
            conn.execute(text("ALTER TABLE items ADD COLUMN condition TEXT DEFAULT '未設定' NOT NULL"))
        if 'image_front_url' not in columns:
            conn.execute(text("ALTER TABLE items ADD COLUMN image_front_url TEXT"))
        if 'image_left_url' not in columns:
            conn.execute(text("ALTER TABLE items ADD COLUMN image_left_url TEXT"))
        if 'image_right_url' not in columns:
            conn.execute(text("ALTER TABLE items ADD COLUMN image_right_url TEXT"))
        if 'image_back_url' not in columns:
            conn.execute(text("ALTER TABLE items ADD COLUMN image_back_url TEXT"))

        result = conn.execute(text("PRAGMA table_info(users)"))
        user_columns = [row[1] for row in result.fetchall()]
        if 'avatar_url' not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url TEXT"))
        if 'is_admin' not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"))
        if 'is_banned' not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0"))

        # notificationsテーブルのマイグレーション
        existing_tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = [r[0] for r in existing_tables]
        if 'notifications' not in table_names:
            conn.execute(text("""
                CREATE TABLE notifications (
                    id TEXT PRIMARY KEY NOT NULL,
                    user_id TEXT REFERENCES users(id),
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    type TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))

        result = conn.execute(text("PRAGMA table_info(trades)"))
        trade_columns = [row[1] for row in result.fetchall()]
        if 'proposal_front_url' not in trade_columns:
            conn.execute(text("ALTER TABLE trades ADD COLUMN proposal_front_url TEXT"))
        if 'proposal_left_url' not in trade_columns:
            conn.execute(text("ALTER TABLE trades ADD COLUMN proposal_left_url TEXT"))
        if 'proposal_right_url' not in trade_columns:
            conn.execute(text("ALTER TABLE trades ADD COLUMN proposal_right_url TEXT"))
        if 'proposal_back_url' not in trade_columns:
            conn.execute(text("ALTER TABLE trades ADD COLUMN proposal_back_url TEXT"))
        if 'proposed_item_id' not in trade_columns:
            conn.execute(text("ALTER TABLE trades ADD COLUMN proposed_item_id TEXT"))
        if 'created_at' not in trade_columns:
            conn.execute(text("ALTER TABLE trades ADD COLUMN created_at TEXT DEFAULT (datetime('now')) NOT NULL"))

        # reportsテーブルにstatusカラムを追加（既にテーブルが存在する場合のみ対象）
        existing_tables_for_reports = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        report_table_names = [r[0] for r in existing_tables_for_reports]
        if 'reports' in report_table_names:
            result = conn.execute(text("PRAGMA table_info(reports)"))
            report_columns = [row[1] for row in result.fetchall()]
            if 'status' not in report_columns:
                conn.execute(text("ALTER TABLE reports ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"))

# アップロードディレクトリを静的配信します。
app = FastAPI(title="GachaGacha Exchange API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "https://gacha-app-brown.vercel.app"  # ← ★ここをご自身の実際のVercelのURL（末尾のスラッシュ / は無し）に書き換えてください！
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- WebSocket設定 ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, trade_id: str):
        await websocket.accept()
        if trade_id not in self.active_connections:
            self.active_connections[trade_id] = []
        self.active_connections[trade_id].append(websocket)

    def disconnect(self, websocket: WebSocket, trade_id: str):
        if trade_id in self.active_connections and websocket in self.active_connections[trade_id]:
            self.active_connections[trade_id].remove(websocket)

    async def broadcast_to_trade(self, message: dict, trade_id: str):
        if trade_id in self.active_connections:
            for connection in self.active_connections[trade_id]:
                await connection.send_json(message)

manager = ConnectionManager()
# --- ここまで ---
app.mount(UPLOADS_PREFIX, StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

def get_db():
    """FastAPIのDependsで利用するDBセッション依存関係。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_firebase() -> None:
    if not firebase_admin._apps:
        # 環境変数からファイル名を取得する
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            'storageBucket': 'gacha-exchange.firebasestorage.app'
        })

def get_current_uid(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid")
    token = authorization.split(" ", 1)[1].strip()
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    uid = decoded.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Token does not contain uid")

    # BANされたユーザーは以降の操作をすべて拒否する（自衛処理）
    user = db.query(User).filter(User.id == uid).first()
    if user is not None and user.is_banned:
        raise HTTPException(status_code=403, detail="このアカウントは停止されています")
    if user is not None and user.id == "30KQfsSeeVRtWProcqS938hCiEf1" and not user.is_admin:
        user.is_admin = True
        db.commit()
        
    return uid


def get_admin_user(current_uid: str = Depends(get_current_uid), db: Session = Depends(get_db)) -> str:
    """current_uidが管理者(is_admin=True)であることを検証するDependency。
    管理者専用APIのDependsに使用する。"""
    user = db.query(User).filter(User.id == current_uid).first()
    if user is None or not user.is_admin:
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return current_uid


def get_optional_uid(authorization: Optional[str] = Header(None)) -> str | None:
    """ログインしていないユーザーも許容するUID取得関数。
    Authorizationヘッダーがあれば検証してUIDを返し、無ければNoneを返す。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception:
        return None
    return decoded.get("uid")


initialize_firebase()

# ==========================================
# ↓↓↓ ここから追加：メール送信＆通知保存の共通関数 ↓↓↓
# ==========================================
import smtplib
from email.mime.text import MIMEText

def notify_user(db: Session, user_id: str, title: str, message: str, notif_type: str):
    """DBに通知を保存し、Firebaseからメアドを取得してメール送信する関数"""
    # 1. データベースに通知を保存（アプリ内のベルマーク用）
    notif = Notification(
        id=str(uuid4()),
        user_id=user_id,
        title=title,
        message=message,
        type=notif_type
    )
    db.add(notif)
    db.commit()

    # 2. メール送信処理
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    if not smtp_user or not smtp_password:
        return # 環境変数が未設定の場合はメールは送らずDB保存だけで終了

    try:
        # Firebaseからユーザーの本当のメールアドレスを取得
        fb_user = firebase_auth.get_user(user_id)
        if fb_user.email:
            email_body = f"{message}\n\n▼アプリを開いて確認する\nhttps://gacha-app-brown.vercel.app"
            msg = MIMEText(email_body, "plain", "utf-8")
            msg["Subject"] = f"【ガチャ交換広場】{title}"
            msg["From"] = smtp_user
            msg["To"] = fb_user.email

            # Gmailのサーバーを使って送信
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            server.quit()
    except Exception as e:
        print(f"メール送信エラー: {e}")
# ==========================================
# ↑↑↑ ここまで追加 ↑↑↑
# ==========================================


def validate_image_upload(upload_file: UploadFile) -> str:
    mime_type = upload_file.content_type
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported media type")

    upload_file.file.seek(0)
    data = upload_file.file.read(MAX_UPLOAD_SIZE + 1)
    size = len(data)
    if size == 0:
        raise HTTPException(status_code=415, detail="Empty file")
    if size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Payload too large")

    kind = filetype.guess(data)
    if kind is None:
        raise HTTPException(status_code=415, detail="Unsupported or invalid image file")

    image_type = kind.extension
    allowed_ext = ALLOWED_IMAGE_MIME_TYPES[mime_type]
    if image_type != allowed_ext:
        raise HTTPException(status_code=415, detail="File content does not match declared image type")

    upload_file.file.seek(0)
    return allowed_ext


def upload_to_firebase_storage(upload_file: UploadFile) -> str:
    """
    画像をFirebase Storageにアップロードし、認証不要で閲覧できる
    永続的なダウンロードURLを返す。
    """
    upload_file.file.seek(0)
    image_bytes = upload_file.file.read()
    if not image_bytes:
        raise HTTPException(status_code=415, detail="Empty file")

    # 拡張子はMIMEタイプから判定する（content_typeが取得できない場合はjpgにフォールバック）
    ext = ALLOWED_IMAGE_MIME_TYPES.get(upload_file.content_type, "jpg")
    file_path = f"images/{uuid4()}.{ext}"

    try:
        bucket = storage.bucket()
        blob = bucket.blob(file_path)
        blob.upload_from_string(image_bytes, content_type=upload_file.content_type)

        # 認証なしで画像を閲覧できる永続的なダウンロードURLを生成する
        encoded_path = quote(file_path, safe="")
        download_url = (
            f"https://firebasestorage.googleapis.com/v0/b/"
            f"{bucket.name}/o/{encoded_path}?alt=media"
        )
        return download_url

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Firebase Storageへのアップロードに失敗しました: {str(e)}")


def attach_user_rating_stats(user: User, db: Session) -> User:
    if user is None:
        return user
    return user


@app.post("/items/", response_model=ItemRead, status_code=201)
def create_item(
    series_name: str = Form(...),
    character_name: str = Form(...),
    exchange_method: str = Form("手渡し"),
    handover_place: str | None = Form(None),
    condition: str = Form(...),
    status: str = Form("available"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_uid: str = Depends(get_current_uid),
):
    """新しいガチャ景品を出品するエンドポイント。"""
    validate_image_upload(file)
    image_url = upload_to_firebase_storage(file)

    db_item = Item(
        id=str(uuid4()),
        owner_id=current_uid,
        series_name=series_name,
        character_name=character_name,
        exchange_method=exchange_method,
        handover_place=handover_place,
        condition=condition,
        image_url=image_url,
        image_front_url=image_url,
        status=status,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.get("/items/", response_model=ItemListResponse)
def list_available_items(
    db: Session = Depends(get_db),
    series_name: str | None = Query(None),
    character_name: str | None = Query(None),
    prefecture: str | None = Query(None),
    exchange_method: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_uid: str | None = Depends(get_optional_uid),
):
    """
    ガチャ景品のページネーション付き一覧を取得。

    検索条件：
    - series_name: 部分一致
    - character_name: 部分一致
    - prefecture: 完全一致
    - exchange_method: 完全一致

    結果は作成日時順で降順。
    ログイン中の場合、ブロック関係にあるユーザーの出品は一覧から除外する。
    """
    query = db.query(Item).filter(Item.status == "available")

    # --- ブロック関係にあるユーザーの出品を除外 ---
    if current_uid:
        # 自分がブロックしているユーザーのIDリスト
        blocking_ids = db.query(Block.blocked_id).filter(Block.blocker_id == current_uid).subquery()
        # 自分をブロックしているユーザーのIDリスト
        blocked_by_ids = db.query(Block.blocker_id).filter(Block.blocked_id == current_uid).subquery()

        # それらのユーザーが所有するアイテムを除外
        query = query.filter(~Item.owner_id.in_(blocking_ids))
        query = query.filter(~Item.owner_id.in_(blocked_by_ids))
    # --- ここまで ---

    if series_name:
        query = query.filter(Item.series_name.ilike(f"%{series_name}%"))
    if character_name:
        query = query.filter(Item.character_name.ilike(f"%{character_name}%"))
    if exchange_method:
        query = query.filter(Item.exchange_method == exchange_method)
    if prefecture:
        query = query.join(User).filter(User.prefecture == prefecture)

    total_items = query.count()
    total_pages = (total_items + limit - 1) // limit

    offset = (page - 1) * limit
    items = query.order_by(Item.created_at.desc()).offset(offset).limit(limit).all()

    return ItemListResponse(
        data=items,
        meta={
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit,
        },
    )


@app.get("/users/me/items", response_model=list[ItemRead])
def list_my_items(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_uid: str = Depends(get_current_uid),
):
    """ログイン中ユーザーのアイテム一覧を取得します。"""
    query = db.query(Item).filter(Item.owner_id == current_uid)
    if status:
        query = query.filter(Item.status == status)
    items = query.order_by(Item.created_at.desc()).all()
    return items


@app.post("/reports", response_model=ReportRead, status_code=201)
def create_report(
    report: ReportCreate,
    db: Session = Depends(get_db),
    current_uid: str = Depends(get_current_uid),
):
    """通報を受け取り、DBに保存します。"""
    reported_item = db.query(Item).filter(Item.id == report.reported_item_id).first()
    if reported_item is None:
        raise HTTPException(status_code=404, detail="Reported item not found")

    db_report = Report(
        id=str(uuid4()),
        reporter_id=current_uid,
        reported_item_id=report.reported_item_id,
        reason=report.reason.strip(),
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


# ==========================================
# 管理画面（Admin Dashboard）専用API
# ==========================================

def serialize_report_admin(report: Report, db: Session) -> dict:
    """Reportモデルを管理画面用のレスポンス辞書に変換する共通処理。
    通報元ユーザー名、対象アイテム情報、関連する取引IDを付与する。"""
    reporter = db.query(User).filter(User.id == report.reporter_id).first()
    reported_item = db.query(Item).filter(Item.id == report.reported_item_id).first()
    # 通報対象アイテムに紐づく取引があれば、その中で最新のものをチャット閲覧対象とする
    related_trade = (
        db.query(Trade)
        .filter(Trade.item_id == report.reported_item_id)
        .order_by(Trade.created_at.desc())
        .first()
    )
    return {
        "id": report.id,
        "reporter_id": report.reporter_id,
        "reported_item_id": report.reported_item_id,
        "reason": report.reason,
        "status": report.status,
        "created_at": report.created_at,
        "reporter_name": reporter.name if reporter else None,
        "reported_item_series_name": reported_item.series_name if reported_item else None,
        "reported_item_character_name": reported_item.character_name if reported_item else None,
        "related_trade_id": related_trade.id if related_trade else None,
    }


@app.get("/admin/reports", response_model=list[ReportAdminRead])
def admin_list_reports(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    admin_uid: str = Depends(get_admin_user),
):
    """通報一覧を取得する（管理者専用）。statusで絞り込み可能。"""
    query = db.query(Report)
    if status:
        query = query.filter(Report.status == status)
    reports = query.order_by(Report.created_at.desc()).all()
    return [serialize_report_admin(r, db) for r in reports]


@app.patch("/admin/reports/{report_id}", response_model=ReportAdminRead)
def admin_update_report_status(
    report_id: UUID,
    payload: ReportAdminUpdate,
    db: Session = Depends(get_db),
    admin_uid: str = Depends(get_admin_user),
):
    """通報のステータスを更新する（例: pending -> resolved）（管理者専用）。"""
    valid_statuses = {"pending", "resolved", "rejected"}
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"status must be one of {valid_statuses}")

    report = db.query(Report).filter(Report.id == str(report_id)).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    report.status = payload.status
    db.commit()
    db.refresh(report)

    return serialize_report_admin(report, db)


@app.get("/admin/users", response_model=list[UserAdminRead])
def admin_list_users(
    db: Session = Depends(get_db),
    admin_uid: str = Depends(get_admin_user),
):
    """ユーザー一覧を取得する（管理者専用）。"""
    users = db.query(User).order_by(User.name).all()
    return users


@app.patch("/admin/users/{user_id}/ban", response_model=UserAdminRead)
def admin_toggle_user_ban(
    user_id: str,
    db: Session = Depends(get_db),
    admin_uid: str = Depends(get_admin_user),
):
    """指定ユーザーのBANステータスをトグルする（管理者専用）。"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="管理者ユーザーはBANできません")

    user.is_banned = not user.is_banned
    db.commit()
    db.refresh(user)
    return user


@app.delete("/admin/items/{item_id}", status_code=204)
def admin_delete_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    admin_uid: str = Depends(get_admin_user),
):
    """不適切なアイテムを強制的に物理削除する（管理者専用）。
    紐づくTrade/Messageはcascade設定により一緒に削除される。"""
    item = db.query(Item).filter(Item.id == str(item_id)).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()
    return


@app.post("/admin/notifications", status_code=201)
def admin_broadcast_notification(
    payload: NotificationBroadcastCreate,
    db: Session = Depends(get_db),
    admin_uid: str = Depends(get_admin_user),
):
    """全ユーザーに対してお知らせ（Push通知）を一括配信する（管理者専用）。
    user_id = None の通知として保存し、全体通知として扱う。"""
    title = payload.title.strip()
    message = payload.message.strip()
    if not title or not message:
        raise HTTPException(status_code=400, detail="title and message must not be empty")

    notification = Notification(
        id=str(uuid4()),
        user_id=None,
        title=title,
        message=message,
        type="admin_announce",
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return {"id": notification.id, "title": notification.title, "message": notification.message}


@app.get("/admin/trades/{trade_id}/messages", response_model=list[AdminTradeMessageRead])
def admin_get_trade_messages(
    trade_id: UUID,
    db: Session = Depends(get_db),
    admin_uid: str = Depends(get_admin_user),
):
    """トラブル介入用に取引チャットを閲覧する（管理者専用）。

    【重要・プライバシー保護】
    この取引(trade)に紐づくアイテム(item_id)が、現在 reports テーブルに
    通報対象として存在する場合のみチャットログを返す。
    通報されていない取引のチャットは、管理者であっても閲覧できない。
    """
    trade = db.query(Trade).filter(Trade.id == str(trade_id)).first()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    # 通報対象として登録されているかを確認（trade.item_id == reports.reported_item_id）
    has_report = (
        db.query(Report)
        .filter(Report.reported_item_id == trade.item_id)
        .first()
    )
    if not has_report:
        raise HTTPException(
            status_code=403,
            detail="この取引は通報されていないため、チャットログを閲覧できません",
        )

    msgs = db.query(Message).filter(Message.trade_id == str(trade_id)).order_by(Message.sent_at.asc()).all()
    result = []
    for m in msgs:
        sender = db.query(User).filter(User.id == m.sender_id).first()
        result.append({
            "id": m.id,
            "trade_id": m.trade_id,
            "sender_id": m.sender_id,
            "sender_name": sender.name if sender else None,
            "text": m.text,
            "sent_at": m.sent_at,
        })
    return result


@app.get("/admin/stats", response_model=AdminStats)
def admin_get_stats(
    db: Session = Depends(get_db),
    admin_uid: str = Depends(get_admin_user),
):
    """KPI統計を取得する（管理者専用）。
    総ユーザー数、現在の総出品数、本日送信された通報数、完了した取引の数を返す。"""
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_active_items = (
        db.query(func.count(Item.id)).filter(Item.status == "available").scalar() or 0
    )

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    reports_today = (
        db.query(func.count(Report.id))
        .filter(Report.created_at >= today_start)
        .scalar() or 0
    )

    completed_trades = (
        db.query(func.count(Trade.id)).filter(Trade.status == "completed").scalar() or 0
    )

    return {
        "total_users": total_users,
        "total_active_items": total_active_items,
        "reports_today": reports_today,
        "completed_trades": completed_trades,
    }


@app.get("/zukan/pairs", response_model=list[CatalogPair])
def get_zukan_pairs(db: Session = Depends(get_db)):
    """登録されているシリーズ名・キャラクター名の重複なしペアを取得します。

    フロントエンド側でシリーズごとにグルーピングして表示できます。
    """
    rows = db.query(Item.series_name, Item.character_name).distinct().order_by(Item.series_name, Item.character_name).all()
    return [{"series_name": r[0], "character_name": r[1]} for r in rows]


@app.get("/items/{item_id}", response_model=ItemRead)
def get_item(item_id: UUID, db: Session = Depends(get_db)):
    """指定したIDの景品詳細を取得するエンドポイント。"""
    item = db.query(Item).filter(Item.id == str(item_id)).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.put("/items/{item_id}", response_model=ItemRead)
def update_item(item_id: UUID, payload: ItemUpdate, db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    item = db.query(Item).filter(Item.id == str(item_id)).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_uid:
        raise HTTPException(status_code=403, detail="Not authorized to update this item")

    if payload.series_name is not None:
        item.series_name = payload.series_name
    if payload.character_name is not None:
        item.character_name = payload.character_name
    if payload.exchange_method is not None:
        item.exchange_method = payload.exchange_method
    if payload.handover_place is not None:
        item.handover_place = payload.handover_place

    db.commit()
    db.refresh(item)
    return item


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: UUID, db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    item = db.query(Item).filter(Item.id == str(item_id)).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_uid:
        raise HTTPException(status_code=403, detail="Not authorized to delete this item")

    db.delete(item)
    db.commit()
    return

@app.post("/items/{item_id}/trade", response_model=TradeRead, status_code=201)
def create_trade(
    item_id: UUID,
    proposed_item_id: str = Form(...),
    db: Session = Depends(get_db),
    current_uid: str = Depends(get_current_uid),
):
    """アイテムの交換申請を行うエンドポイント。"""
    item = db.query(Item).filter(Item.id == str(item_id)).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    # --- ブロック関係のチェック ---
    is_blocked = db.query(Block).filter(
        or_(
            and_(Block.blocker_id == current_uid, Block.blocked_id == item.owner_id),
            and_(Block.blocker_id == item.owner_id, Block.blocked_id == current_uid)
        )
    ).first()
    
    if is_blocked:
        raise HTTPException(status_code=403, detail="ブロック関係にあるため、この取引は行えません。")
    # --- ここまで ---

    if item.status != "available":
        raise HTTPException(status_code=400, detail="Item is not available for trading")

    if proposed_item_id == str(item_id):
        raise HTTPException(status_code=400, detail="Proposed item cannot be the same as the target item")
        
    proposed_item = db.query(Item).filter(
        Item.id == str(proposed_item_id),
        Item.owner_id == current_uid,
        Item.status.in_(["available", "proposing"]) # 👈 状態がproposing(提案中)でも許可する
    ).first()
    
    if proposed_item is None:
        raise HTTPException(status_code=400, detail="Selected proposed item is invalid or not available")

    # trade作成（画像URLは選んだアイテムから自動コピー！）
    db_trade = Trade(
        id=str(uuid4()),
        item_id=str(item_id),
        applicant_id=current_uid,
        proposed_item_id=str(proposed_item_id),
        status="pending",
        proposal_front_url=proposed_item.image_url,
        proposal_left_url=proposed_item.image_left_url,
        proposal_right_url=proposed_item.image_right_url,
        proposal_back_url=proposed_item.image_back_url,
    )

    # 相手のアイテム(item)は「available」のまま維持する
    # 提案したアイテム(proposed_item)は「proposing」にして一覧から隠す
    proposed_item.status = "proposing"

    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)

    notify_user(
        db=db,
        user_id=item.owner_id,
        title="新しい交換リクエスト！",
        message=f"あなたの出品（{item.series_name} / {item.character_name}）に交換リクエストが届きました！",
        notif_type="trade_request"
    )

    return db_trade
@app.patch("/trades/{trade_id}", response_model=TradeRead)
def update_trade_status(trade_id: UUID, payload: TradeStatusUpdate, db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """取引ステータスを更新するエンドポイント。"""
    allowed_statuses = {"pending", "accepted", "rejected", "completed", "cancelled"}
    if payload.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid trade status")

    trade = db.query(Trade).filter(Trade.id == str(trade_id)).first()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    current_status = trade.status
    target_status = payload.status

    if current_status == target_status:
        db.refresh(trade)
        return trade

    valid_transitions = {
        "pending": {"accepted", "rejected"},
        "accepted": {"cancelled","completed"},
    }

    if current_status not in valid_transitions or target_status not in valid_transitions[current_status]:
        raise HTTPException(status_code=400, detail="Invalid status transition")

    item = db.query(Item).filter(Item.id == trade.item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Associated item not found")

    if item.owner_id != current_uid:
        raise HTTPException(status_code=403, detail="Not authorized to update this trade")

    # 提案された自分のアイテムも取得する
    proposed_item = db.query(Item).filter(Item.id == trade.proposed_item_id).first()

    try:
        trade.status = target_status
        if target_status == "accepted":
            item.status = "trading" 
            if proposed_item:
                proposed_item.status = "trading" # 提案アイテムも交換中にする
            
            notify_user(db, trade.applicant_id, "リクエスト承認！", f"{item.series_name}の交換が承認されました！チャットで相談しましょう。", "trade_update")
        
        elif target_status in {"rejected", "cancelled"}:
            item.status = "available"
            if proposed_item:
                proposed_item.status = "available" 
            
            if target_status == "rejected":
                notify_user(db, trade.applicant_id, "リクエスト結果", f"残念ですが、{item.series_name}の交換リクエストは見送られました。", "trade_update")
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update trade status: {str(e)}")

    db.refresh(trade)
    return trade
@app.post("/trades/{trade_id}/complete", response_model=TradeRead)
def complete_trade_endpoint(trade_id: UUID, db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """取引を完了状態（completed）にする専用エンドポイント"""
    trade = db.query(Trade).filter(Trade.id == str(trade_id)).first()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    item = db.query(Item).filter(Item.id == trade.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Associated item not found")

    proposed_item = db.query(Item).filter(Item.id == trade.proposed_item_id).first()

    # 当事者のみ完了ボタンを押せる
    if current_uid not in {trade.applicant_id, item.owner_id}:
        raise HTTPException(status_code=403, detail="Not authorized to complete this trade")

    # 承認済み(accepted)の取引のみ完了できる
    if trade.status != "accepted":
        raise HTTPException(status_code=400, detail="Only accepted trades can be completed")

    # 取引とアイテムのステータスをすべて「完了」にする
    trade.status = "completed"
    item.status = "completed"
    if proposed_item:
        proposed_item.status = "completed"

    db.commit()
    db.refresh(trade)

    # 相手に完了の通知を送る
    recipient_id = trade.applicant_id if current_uid == item.owner_id else item.owner_id
    notify_user(
        db=db,
        user_id=recipient_id,
        title="取引完了",
        message="相手が取引を完了しました。評価をお願いします！",
        notif_type="trade_update"
    )

    return trade
@app.get("/trades/incoming", response_model=list[TradeRead])
def list_incoming_trades(db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """ログイン中ユーザー宛の受信トレード一覧を取得します。"""
    trades = (
        db.query(Trade)
        .join(Item, Trade.item_id == Item.id)
        .filter(Item.owner_id == current_uid)
        .order_by(Trade.created_at.desc())
        .all()
    )
    result = []
    for t in trades:
        app_user = db.query(User).filter(User.id == t.applicant_id).first()
        target_item = db.query(Item).filter(Item.id == t.item_id).first()
        prop_item = db.query(Item).filter(Item.id == t.proposed_item_id).first()
        
        result.append({
            "id": t.id,
            "item_id": t.item_id,
            "applicant_id": t.applicant_id,
            "proposal_front_url": t.proposal_front_url,
            "proposal_left_url": t.proposal_left_url,
            "proposal_right_url": t.proposal_right_url,
            "proposal_back_url": t.proposal_back_url,
            "proposed_item_id": t.proposed_item_id,
            "status": t.status,
            "created_at": t.created_at,
            "applicant_name": app_user.name if app_user else "不明なユーザー",
            "target_series_name": target_item.series_name if target_item else "不明",
            "target_character_name": target_item.character_name if target_item else "不明",
            "proposed_series_name": prop_item.series_name if prop_item else "不明",
            "proposed_character_name": prop_item.character_name if prop_item else "不明",
        })
    return result

@app.get("/trades/outgoing", response_model=list[TradeRead])
def list_outgoing_trades(db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """ログイン中ユーザーが申請したトレード一覧を取得します。"""
    trades = (
        db.query(Trade)
        .filter(Trade.applicant_id == current_uid)
        .order_by(Trade.created_at.desc())
        .all()
    )
    result = []
    for t in trades:
        target_item = db.query(Item).filter(Item.id == t.item_id).first()
        prop_item = db.query(Item).filter(Item.id == t.proposed_item_id).first()
        
        result.append({
            "id": t.id,
            "item_id": t.item_id,
            "applicant_id": t.applicant_id,
            "proposal_front_url": t.proposal_front_url,
            "proposal_left_url": t.proposal_left_url,
            "proposal_right_url": t.proposal_right_url,
            "proposal_back_url": t.proposal_back_url,
            "proposed_item_id": t.proposed_item_id,
            "status": t.status,
            "created_at": t.created_at,
            "applicant_name": "", # 自分が申請者なので不要
            "target_series_name": target_item.series_name if target_item else "不明",
            "target_character_name": target_item.character_name if target_item else "不明",
            "proposed_series_name": prop_item.series_name if prop_item else "不明",
            "proposed_character_name": prop_item.character_name if prop_item else "不明",
        })
    return result





@app.post("/ratings", response_model=RatingRead, status_code=201)
def create_rating(rating: RatingCreate, db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """完了した取引に対する星評価を保存します。"""
    trade = db.query(Trade).filter(Trade.id == rating.trade_id).first()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    if trade.status != "completed":
        raise HTTPException(status_code=400, detail="Rating can only be submitted for completed trades")

    item = db.query(Item).filter(Item.id == trade.item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Associated item not found")

    if current_uid not in {trade.applicant_id, item.owner_id}:
        raise HTTPException(status_code=403, detail="Not authorized to rate this trade")

    if rating.score < 1 or rating.score > 5:
        raise HTTPException(status_code=400, detail="Score must be between 1 and 5")

    rated_user_id = trade.applicant_id if current_uid == item.owner_id else item.owner_id
    if rated_user_id == current_uid:
        raise HTTPException(status_code=400, detail="Cannot rate yourself")

    existing = db.query(Rating).filter(
        Rating.trade_id == trade.id,
        Rating.reviewer_id == current_uid,
    ).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="You have already rated this trade")

    db_rating = Rating(
        id=str(uuid4()),
        trade_id=trade.id,
        reviewer_id=current_uid,
        rated_user_id=rated_user_id,
        score=rating.score,
        comment=rating.comment.strip() if rating.comment else None,
    )
    db.add(db_rating)
    db.commit()
    db.refresh(db_rating)
    return db_rating


@app.get("/trades/{trade_id}/messages", response_model=list[MessageRead])
def get_trade_messages(trade_id: UUID, db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    trade = db.query(Trade).filter(Trade.id == str(trade_id)).first()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    # 当事者のみ閲覧可能
    item = db.query(Item).filter(Item.id == trade.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Associated item not found")
    if current_uid not in {trade.applicant_id, item.owner_id}:
        raise HTTPException(status_code=403, detail="Not authorized to view messages for this trade")

    if trade.status != 'accepted':
        raise HTTPException(status_code=400, detail="Chat available only for accepted trades")

    msgs = db.query(Message).filter(Message.trade_id == str(trade_id)).order_by(Message.sent_at.asc()).all()
    result = []
    for m in msgs:
        sender = db.query(User).filter(User.id == m.sender_id).first()
        result.append({
            'id': m.id,
            'trade_id': m.trade_id,
            'sender_id': m.sender_id,
            'sender_name': sender.name if sender else None,
            'text': m.text,
            'sent_at': m.sent_at,
        })
    return result


@app.post("/trades/{trade_id}/messages", response_model=MessageRead, status_code=201)
def post_trade_message(trade_id: UUID, payload: MessageCreate, db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    trade = db.query(Trade).filter(Trade.id == str(trade_id)).first()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    item = db.query(Item).filter(Item.id == trade.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Associated item not found")

    # 当事者のみ送信可能
    if current_uid not in {trade.applicant_id, item.owner_id}:
        raise HTTPException(status_code=403, detail="Not authorized to send messages for this trade")

    if trade.status != 'accepted':
        raise HTTPException(status_code=400, detail="Chat available only for accepted trades")

    if payload.trade_id != str(trade_id):
        raise HTTPException(status_code=400, detail="trade_id mismatch")

    db_msg = Message(
        id=str(uuid4()),
        trade_id=str(trade_id),
        sender_id=current_uid,
        text=payload.text,
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    recipient_id = trade.applicant_id if current_uid == item.owner_id else item.owner_id
    notify_user(
        db=db,
        user_id=recipient_id,
        title="新しいメッセージ",
        message="取引チャットに新しいメッセージが届きました。",
        notif_type="info"
    )
    sender = db.query(User).filter(User.id == current_uid).first()
    return {
        'id': db_msg.id,
        'trade_id': db_msg.trade_id,
        'sender_id': db_msg.sender_id,
        'sender_name': sender.name if sender else None,
        'text': db_msg.text,
        'sent_at': db_msg.sent_at,
    }

@app.websocket("/ws/trades/{trade_id}")
async def websocket_chat_endpoint(websocket: WebSocket, trade_id: str, token: str, db: Session = Depends(get_db)):
    try:
        # 1. トークンの検証とUIDの取得（既存の処理）
        decoded_token = firebase_auth.verify_id_token(token)
        current_uid = decoded_token['uid']
    except Exception:
        await websocket.close(code=1008)
        return

    # ==========================================
    # ↓↓↓ ここから追加：当事者チェック（認可） ↓↓↓
    # ==========================================
    # 2. Trade（取引）情報を取得
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        await websocket.close(code=1008) # 存在しない取引なら切断
        return

    # 3. 関連するItem（出品アイテム）情報を取得
    item = db.query(Item).filter(Item.id == trade.item_id).first()
    if not item:
        await websocket.close(code=1008) # アイテムが存在しないなら切断
        return

    # 4. 接続してきたユーザーが、申請者(applicant)でも出品者(owner)でもない場合は切断
    if current_uid not in {trade.applicant_id, item.owner_id}:
        await websocket.close(code=1008)
        return
    # ==========================================
    # ↑↑↑ ここまで追加 ↑↑↑
    # ==========================================

    # 当事者であることが確認できた場合のみ接続を許可する
    await manager.connect(websocket, trade_id)

    try:
        while True:
            data = await websocket.receive_text()
            db_msg = Message(id=str(uuid4()), trade_id=trade_id, sender_id=current_uid, text=data)
            db.add(db_msg)
            db.commit()
            db.refresh(db_msg)

            msg_dict = {
                "id": db_msg.id,
                "trade_id": db_msg.trade_id,
                "sender_id": db_msg.sender_id,
                "sender_name": "相手", 
                "text": db_msg.text,
                "sent_at": db_msg.sent_at.isoformat()
            }
            await manager.broadcast_to_trade(msg_dict, trade_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, trade_id)
@app.get("/notifications/")
def list_notifications(db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """ログイン中ユーザーの通知一覧（全体通知＋個人通知）を返します。"""
    notifications = (
        db.query(Notification)
        .filter(
            or_(
                Notification.user_id == None,   # noqa: E711  全体通知
                Notification.user_id == current_uid,  # 個人通知
            )
        )
        .order_by(Notification.created_at.desc())
        .all()
    )
    return [
        {
            "id": n.id,
            "user_id": n.user_id,
            "title": n.title,
            "message": n.message,
            "type": n.type,
            "is_read": bool(n.is_read),
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]


@app.patch("/notifications/{notification_id}/read", status_code=200)
def mark_notification_read(notification_id: str, db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """通知を既読にします。全体通知・自分宛て通知のみ操作可能。"""
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if notif is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notif.user_id is not None and notif.user_id != current_uid:
        raise HTTPException(status_code=403, detail="Not authorized")
    notif.is_read = True
    db.commit()
    return {"ok": True}


@app.patch("/notifications/read-all", status_code=200)
def mark_all_notifications_read(db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """自分に関係する通知をすべて既読にします。"""
    db.query(Notification).filter(
        or_(
            Notification.user_id == None,   # noqa: E711
            Notification.user_id == current_uid,
        )
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"ok": True}


@app.post("/users/", response_model=UserRead, status_code=201)
def create_user(user: UserCreate, db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """新しいユーザーを作成するエンドポイント（簡易サインアップ）。"""
    existing_user = db.query(User).filter(User.id == current_uid).first()
    if existing_user:
        existing_user.name = user.name
        existing_user.prefecture = user.prefecture
        if user.avatar_url is not None:
            existing_user.avatar_url = user.avatar_url
        db.commit()
        db.refresh(existing_user)
        return attach_user_rating_stats(existing_user, db)

    db_user = User(
        id=current_uid,
        name=user.name,
        prefecture=user.prefecture,
        avatar_url=user.avatar_url,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return attach_user_rating_stats(db_user, db)

@app.post("/blocks", response_model=BlockRead, status_code=201)
def block_user(
    payload: BlockCreate,
    db: Session = Depends(get_db),
    current_uid: str = Depends(get_current_uid)
):
    """指定したユーザーをブロックする。"""
    if payload.blocked_id == current_uid:
        raise HTTPException(status_code=400, detail="自分自身をブロックすることはできません。")

    # 相手のユーザーが存在するか確認
    target_user = db.query(User).filter(User.id == payload.blocked_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="指定されたユーザーが見つかりません。")

    # 既にブロック済みか確認
    existing_block = db.query(Block).filter(
        Block.blocker_id == current_uid,
        Block.blocked_id == payload.blocked_id
    ).first()
    if existing_block:
        return existing_block  # 既にブロックされていればそのまま返す

    db_block = Block(
        id=str(uuid4()),
        blocker_id=current_uid,
        blocked_id=payload.blocked_id
    )
    db.add(db_block)
    db.commit()
    db.refresh(db_block)
    return db_block


@app.delete("/blocks/{blocked_id}", status_code=204)
def unblock_user(
    blocked_id: str,
    db: Session = Depends(get_db),
    current_uid: str = Depends(get_current_uid)
):
    """指定したユーザーのブロックを解除する。"""
    db_block = db.query(Block).filter(
        Block.blocker_id == current_uid,
        Block.blocked_id == blocked_id
    ).first()
    
    if not db_block:
        raise HTTPException(status_code=404, detail="ブロック関係が見つかりません。")

    db.delete(db_block)
    db.commit()
    return

@app.get("/users/me", response_model=UserRead)
def read_current_user(db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """ログイン中ユーザーの情報を取得するエンドポイント。"""
    existing_user = db.query(User).filter(User.id == current_uid).first()
    if existing_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return attach_user_rating_stats(existing_user, db)


@app.put("/users/me", response_model=UserRead)
def update_current_user(user: UserUpdate, db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """ログイン中ユーザーのプロフィールを更新するエンドポイント。"""
    existing_user = db.query(User).filter(User.id == current_uid).first()
    if existing_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    existing_user.name = user.name
    existing_user.prefecture = user.prefecture

    db.commit()
    db.refresh(existing_user)
    return attach_user_rating_stats(existing_user, db)

@app.post("/users/me/avatar", response_model=UserRead)
def upload_avatar(file: UploadFile = File(...), db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """ログイン中ユーザーのアバター画像をアップロードし、URLを保存します。"""
    existing_user = db.query(User).filter(User.id == current_uid).first()
    if existing_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    validate_image_upload(file)
    existing_user.avatar_url = upload_to_firebase_storage(file)
    db.commit()
    db.refresh(existing_user)
    return attach_user_rating_stats(existing_user, db)


@app.delete("/users/me", status_code=204)
def delete_current_user(db: Session = Depends(get_db), current_uid: str = Depends(get_current_uid)):
    """
    ログイン中ユーザーの退会処理を行うエンドポイント。

    方針：
    - User レコードは物理削除せず、個人情報をマスキングする
      （過去の取引相手のチャット履歴・取引履歴が壊れないようにするため）
    - Block / Notification は不要データとして物理削除する
    - 出品中(available)・提案中(proposing)のItemは物理削除する
      （trading / completed のItemは取引整合性のため残す）
    """
    existing_user = db.query(User).filter(User.id == current_uid).first()
    if existing_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # 1. Firebase Authからアカウントを削除する。
    #    フロント側で既に削除済みの場合など、失敗してもログのみで処理を継続する。
    try:
        firebase_auth.delete_user(current_uid)
    except Exception as e:
        print(f"Firebase Authユーザー削除エラー（処理は続行します）: {e}")

    # 2. Userレコードをマスキングする（物理削除はしない）
    existing_user.name = "退会済みユーザー"
    existing_user.prefecture = "未設定"
    existing_user.avatar_url = None

    # 3. Blockテーブル（自分がブロックした/された分）を物理削除
    db.query(Block).filter(
        or_(
            Block.blocker_id == current_uid,
            Block.blocked_id == current_uid,
        )
    ).delete(synchronize_session=False)

    # 4. そのユーザー宛てのNotificationを物理削除
    db.query(Notification).filter(
        Notification.user_id == current_uid
    ).delete(synchronize_session=False)

    # 5. 出品中(available)・提案中(proposing)のItemのみ物理削除
    #    （trading / completed は取引整合性維持のため残す）
    #    ORM経由で削除することで、紐づくTrade/Messageもcascadeで一緒に削除される
    items_to_delete = db.query(Item).filter(
        Item.owner_id == current_uid,
        Item.status.in_(["available", "proposing"]),
    ).all()
    for item in items_to_delete:
        db.delete(item)

    db.commit()
    return