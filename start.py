#!/usr/bin/env python3
"""Servidor local do Banca Fácil: API HTTP, autenticação e banco SQLite."""

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "banca.sqlite3"
COOKIE_NAME = "banca_session"
SESSION_SECONDS = 60 * 60 * 24 * 7
MAX_BODY_SIZE = 1_000_000
DEMO_EMAIL = "cliente@bancafacil.com.br"
DEMO_PASSWORD = "Cliente@123"
PASSWORD_ITERATIONS = 600_000
LEGACY_PASSWORD_ITERATIONS = 310_000


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def hash_password(
    password: str,
    salt: Optional[bytes] = None,
    iterations: int = PASSWORD_ITERATIONS,
) -> Tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return base64.b64encode(salt).decode("ascii"), base64.b64encode(digest).decode("ascii")


def verify_password(
    password: str,
    salt_text: str,
    digest_text: str,
    iterations: int = PASSWORD_ITERATIONS,
) -> bool:
    salt = base64.b64decode(salt_text)
    expected = base64.b64decode(digest_text)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def connect_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_iterations INTEGER NOT NULL DEFAULT 600000,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
    stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
    min_stock INTEGER NOT NULL DEFAULT 0 CHECK(min_stock >= 0),
    barcode TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS products_user_idx ON products(user_id);

CREATE TABLE IF NOT EXISTS sales (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
    payment_method TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS sales_user_date_idx ON sales(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id TEXT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0)
);

CREATE TABLE IF NOT EXISTS settings (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    business_name TEXT NOT NULL DEFAULT 'Minha Banca',
    merchant_name TEXT NOT NULL DEFAULT 'MINHA BANCA',
    city TEXT NOT NULL DEFAULT 'SAO PAULO',
    pix_key TEXT NOT NULL DEFAULT '',
    whatsapp TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS activity_user_date_idx ON activity_logs(user_id, created_at DESC);
"""


DEMO_PRODUCTS = [
    ("Jornal do Dia", "Jornais", 750, 18, 5, "789100000001"),
    ("Revista Atual", "Revistas", 1890, 9, 3, "789100000002"),
    ("Água mineral 500ml", "Bebidas", 450, 24, 8, "789100000003"),
    ("Refrigerante lata", "Bebidas", 650, 14, 6, "789100000004"),
    ("Chocolate ao leite", "Conveniência", 700, 11, 5, "789100000005"),
    ("Carregador USB-C", "Acessórios", 3990, 2, 3, "789100000006"),
]


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect_db(path) as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript(SCHEMA)
        user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
        if "password_iterations" not in user_columns:
            db.execute(
                "ALTER TABLE users ADD COLUMN password_iterations INTEGER NOT NULL DEFAULT %d"
                % LEGACY_PASSWORD_ITERATIONS
            )
        demo = db.execute("SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
        if demo:
            return
        user_id = str(uuid.uuid4())
        salt, digest = hash_password(DEMO_PASSWORD)
        now = utc_now()
        db.execute(
            "INSERT INTO users(id, name, email, password_salt, password_hash, password_iterations, created_at) VALUES(?,?,?,?,?,?,?)",
            (user_id, "Cliente Demonstração", DEMO_EMAIL, salt, digest, PASSWORD_ITERATIONS, now),
        )
        db.execute(
            "INSERT INTO settings(user_id, business_name, merchant_name, city, pix_key, whatsapp, updated_at) VALUES(?,?,?,?,?,?,?)",
            (user_id, "Banca Central", "BANCA CENTRAL", "SAO PAULO", "cliente@bancafacil.com.br", "", now),
        )
        for name, category, price, stock, minimum, barcode in DEMO_PRODUCTS:
            db.execute(
                "INSERT INTO products(id, user_id, name, category, price_cents, stock, min_stock, barcode, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), user_id, name, category, price, stock, minimum, barcode, now, now),
            )
        db.execute(
            "INSERT INTO activity_logs(user_id, type, message, created_at) VALUES(?,?,?,?)",
            (user_id, "account_created", "Conta de demonstração preparada.", now),
        )


def parse_money_to_cents(value: Any) -> int:
    try:
        cents = round(float(value) * 100)
    except (TypeError, ValueError):
        raise ApiError(400, "Informe um preço válido.")
    if cents < 0 or cents > 100_000_000:
        raise ApiError(400, "O preço informado está fora do limite permitido.")
    return cents


def clean_product_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    name = str(data.get("name") or "").strip()
    category = str(data.get("category") or "").strip()
    barcode = str(data.get("barcode") or "").strip()
    if len(name) < 2 or len(name) > 100:
        raise ApiError(400, "O nome do produto deve ter entre 2 e 100 caracteres.")
    if len(category) < 2 or len(category) > 50:
        raise ApiError(400, "A categoria deve ter entre 2 e 50 caracteres.")
    if len(barcode) > 40:
        raise ApiError(400, "O código de barras é muito longo.")
    try:
        stock = int(data.get("stock", 0))
        minimum = int(data.get("minStock", 0))
    except (TypeError, ValueError):
        raise ApiError(400, "Estoque e estoque mínimo devem ser números inteiros.")
    if stock < 0 or minimum < 0 or stock > 1_000_000 or minimum > 1_000_000:
        raise ApiError(400, "O estoque informado está fora do limite permitido.")
    return {
        "name": name,
        "category": category,
        "barcode": barcode,
        "price_cents": parse_money_to_cents(data.get("price")),
        "stock": stock,
        "min_stock": minimum,
    }


def product_json(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "price": row["price_cents"] / 100,
        "stock": row["stock"],
        "minStock": row["min_stock"],
        "barcode": row["barcode"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def log_activity(db: sqlite3.Connection, user_id: str, kind: str, message: str) -> None:
    db.execute(
        "INSERT INTO activity_logs(user_id, type, message, created_at) VALUES(?,?,?,?)",
        (user_id, kind, message, utc_now()),
    )


class BancaServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: Tuple[str, int], db_path: Path):
        self.db_path = db_path
        super().__init__(address, BancaRequestHandler)


class BancaRequestHandler(SimpleHTTPRequestHandler):
    server: BancaServer
    PUBLIC_FILES = {"/index.html", "/styles.css", "/app.js"}
    server_version = "BancaFacil/1.0"
    sys_version = ""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, message: str, *args: Any) -> None:
        print("[%s] %s" % (self.log_date_time_string(), message % args))

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        super().end_headers()

    def do_GET(self) -> None:
        if self._is_api():
            self._handle_api("GET")
            return
        requested = urlparse(self.path).path
        if requested == "/":
            requested = "/index.html"
        if requested not in self.PUBLIC_FILES:
            self.send_error(404, "Arquivo não encontrado")
            return
        self.path = requested
        super().do_GET()

    def do_HEAD(self) -> None:
        requested = urlparse(self.path).path
        if requested == "/":
            requested = "/index.html"
        if requested not in self.PUBLIC_FILES:
            self.send_error(404, "Arquivo não encontrado")
            return
        self.path = requested
        super().do_HEAD()

    def do_POST(self) -> None:
        self._handle_api("POST")

    def do_PUT(self) -> None:
        self._handle_api("PUT")

    def do_PATCH(self) -> None:
        self._handle_api("PATCH")

    def do_DELETE(self) -> None:
        self._handle_api("DELETE")

    def _is_api(self) -> bool:
        return urlparse(self.path).path.startswith("/api/")

    def _json(self, status: int, payload: Dict[str, Any], extra_headers: Optional[List[Tuple[str, str]]] = None) -> None:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        for name, value in extra_headers or []:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> Dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0]
        if content_type != "application/json":
            raise ApiError(415, "Envie os dados no formato JSON.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ApiError(400, "Tamanho da requisição inválido.")
        if length <= 0 or length > MAX_BODY_SIZE:
            raise ApiError(400, "Corpo da requisição vazio ou muito grande.")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "JSON inválido.")
        if not isinstance(data, dict):
            raise ApiError(400, "O corpo da requisição deve ser um objeto.")
        return data

    def _same_origin(self) -> None:
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if origin and urlparse(origin).netloc != host:
            raise ApiError(403, "Origem da requisição não autorizada.")

    def _session_cookie(self, token: str) -> str:
        jar = cookies.SimpleCookie()
        jar[COOKIE_NAME] = token
        jar[COOKIE_NAME]["path"] = "/"
        jar[COOKIE_NAME]["httponly"] = True
        jar[COOKIE_NAME]["samesite"] = "Strict"
        jar[COOKIE_NAME]["max-age"] = SESSION_SECONDS
        return jar.output(header="").strip()

    def _clear_cookie(self) -> str:
        jar = cookies.SimpleCookie()
        jar[COOKIE_NAME] = ""
        jar[COOKIE_NAME]["path"] = "/"
        jar[COOKIE_NAME]["httponly"] = True
        jar[COOKIE_NAME]["samesite"] = "Strict"
        jar[COOKIE_NAME]["max-age"] = 0
        return jar.output(header="").strip()

    def _current_user(self, db: sqlite3.Connection) -> sqlite3.Row:
        raw_cookie = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie()
        try:
            jar.load(raw_cookie)
        except cookies.CookieError:
            raise ApiError(401, "Sessão inválida. Entre novamente.")
        morsel = jar.get(COOKIE_NAME)
        if not morsel or not morsel.value:
            raise ApiError(401, "Faça login para continuar.")
        token_hash = hashlib.sha256(morsel.value.encode("utf-8")).hexdigest()
        row = db.execute(
            "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
            (token_hash, int(time.time())),
        ).fetchone()
        if not row:
            raise ApiError(401, "Sua sessão expirou. Entre novamente.")
        return row

    def _create_session(self, db: sqlite3.Connection, user_id: str) -> str:
        token = secrets.token_urlsafe(40)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
        db.execute(
            "INSERT INTO sessions(token_hash, user_id, expires_at, created_at) VALUES(?,?,?,?)",
            (token_hash, user_id, int(time.time()) + SESSION_SECONDS, utc_now()),
        )
        return token

    def _handle_api(self, method: str) -> None:
        try:
            if not self._is_api():
                raise ApiError(404, "Rota não encontrada.")
            if method != "GET":
                self._same_origin()
            path = urlparse(self.path).path.rstrip("/") or "/"
            with connect_db(self.server.db_path) as db:
                if path == "/api/health" and method == "GET":
                    self._json(200, {"ok": True, "database": "connected"})
                    return
                if path == "/api/auth/register" and method == "POST":
                    self._register(db)
                    return
                if path == "/api/auth/login" and method == "POST":
                    self._login(db)
                    return
                if path == "/api/auth/logout" and method == "POST":
                    self._logout(db)
                    return

                user = self._current_user(db)
                if path == "/api/auth/me" and method == "GET":
                    self._json(200, {"user": self._user_json(user)})
                elif path == "/api/bootstrap" and method == "GET":
                    self._bootstrap(db, user)
                elif path == "/api/products" and method == "POST":
                    self._create_product(db, user)
                elif re.fullmatch(r"/api/products/[0-9a-f-]+", path) and method == "PATCH":
                    self._update_product(db, user, path.rsplit("/", 1)[1])
                elif re.fullmatch(r"/api/products/[0-9a-f-]+", path) and method == "DELETE":
                    self._delete_product(db, user, path.rsplit("/", 1)[1])
                elif path == "/api/sales" and method == "POST":
                    self._create_sale(db, user)
                elif path == "/api/settings" and method == "PUT":
                    self._update_settings(db, user)
                elif path == "/api/account/password" and method == "PUT":
                    self._change_password(db, user)
                else:
                    raise ApiError(404, "Rota não encontrada.")
        except ApiError as error:
            self._json(error.status, {"error": error.message})
        except sqlite3.IntegrityError:
            self._json(409, {"error": "Não foi possível concluir: já existe um registro com esses dados."})
        except Exception as error:
            print("Erro interno:", repr(error))
            self._json(500, {"error": "Ocorreu um erro interno. Tente novamente."})

    @staticmethod
    def _user_json(row: sqlite3.Row) -> Dict[str, Any]:
        return {"id": row["id"], "name": row["name"], "email": row["email"], "createdAt": row["created_at"]}

    def _register(self, db: sqlite3.Connection) -> None:
        data = self._body()
        name = str(data.get("name") or "").strip()
        email = normalize_email(data.get("email"))
        password = str(data.get("password") or "")
        if len(name) < 2 or len(name) > 80:
            raise ApiError(400, "Informe um nome entre 2 e 80 caracteres.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 160:
            raise ApiError(400, "Informe um e-mail válido.")
        if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise ApiError(400, "A senha deve ter ao menos 8 caracteres, uma letra e um número.")
        if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise ApiError(409, "Já existe uma conta com este e-mail.")
        user_id = str(uuid.uuid4())
        salt, digest = hash_password(password)
        now = utc_now()
        db.execute(
            "INSERT INTO users(id, name, email, password_salt, password_hash, password_iterations, created_at) VALUES(?,?,?,?,?,?,?)",
            (user_id, name, email, salt, digest, PASSWORD_ITERATIONS, now),
        )
        db.execute(
            "INSERT INTO settings(user_id, business_name, merchant_name, city, pix_key, whatsapp, updated_at) VALUES(?,?,?,?,?,?,?)",
            (user_id, "Minha Banca", name.upper()[:25], "SAO PAULO", "", "", now),
        )
        log_activity(db, user_id, "account_created", "Conta criada com sucesso.")
        token = self._create_session(db, user_id)
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        db.commit()
        self._json(201, {"user": self._user_json(user)}, [("Set-Cookie", self._session_cookie(token))])

    def _login(self, db: sqlite3.Connection) -> None:
        data = self._body()
        email = normalize_email(data.get("email"))
        password = str(data.get("password") or "")
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not verify_password(
            password,
            user["password_salt"],
            user["password_hash"],
            user["password_iterations"],
        ):
            time.sleep(0.15)
            raise ApiError(401, "E-mail ou senha incorretos.")
        token = self._create_session(db, user["id"])
        log_activity(db, user["id"], "login", "Acesso realizado.")
        db.commit()
        self._json(200, {"user": self._user_json(user)}, [("Set-Cookie", self._session_cookie(token))])

    def _logout(self, db: sqlite3.Connection) -> None:
        raw_cookie = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie(raw_cookie)
        morsel = jar.get(COOKIE_NAME)
        if morsel and morsel.value:
            token_hash = hashlib.sha256(morsel.value.encode("utf-8")).hexdigest()
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        db.commit()
        self._json(200, {"ok": True}, [("Set-Cookie", self._clear_cookie())])

    def _bootstrap(self, db: sqlite3.Connection, user: sqlite3.Row) -> None:
        user_id = user["id"]
        products = [product_json(row) for row in db.execute("SELECT * FROM products WHERE user_id = ? ORDER BY name", (user_id,))]
        sale_rows = db.execute("SELECT * FROM sales WHERE user_id = ? ORDER BY created_at DESC LIMIT 500", (user_id,)).fetchall()
        sales: List[Dict[str, Any]] = []
        for sale in sale_rows:
            items = db.execute(
                "SELECT product_id, product_name, quantity, unit_price_cents FROM sale_items WHERE sale_id = ? ORDER BY id",
                (sale["id"],),
            ).fetchall()
            sales.append({
                "id": sale["id"],
                "total": sale["total_cents"] / 100,
                "paymentMethod": sale["payment_method"],
                "createdAt": sale["created_at"],
                "items": [{
                    "productId": item["product_id"],
                    "name": item["product_name"],
                    "quantity": item["quantity"],
                    "price": item["unit_price_cents"] / 100,
                } for item in items],
            })
        setting = db.execute("SELECT * FROM settings WHERE user_id = ?", (user_id,)).fetchone()
        activities = db.execute(
            "SELECT type, message, created_at FROM activity_logs WHERE user_id = ? ORDER BY id DESC LIMIT 30",
            (user_id,),
        ).fetchall()
        today = datetime.now().astimezone().date().isoformat()
        today_sales = [sale for sale in sales if str(sale["createdAt"])[:10] == today]
        self._json(200, {
            "user": self._user_json(user),
            "products": products,
            "sales": sales,
            "settings": {
                "businessName": setting["business_name"],
                "merchantName": setting["merchant_name"],
                "city": setting["city"],
                "pixKey": setting["pix_key"],
                "whatsapp": setting["whatsapp"],
            },
            "activities": [{"type": row["type"], "message": row["message"], "createdAt": row["created_at"]} for row in activities],
            "summary": {
                "todayRevenue": round(sum(sale["total"] for sale in today_sales), 2),
                "todaySales": len(today_sales),
                "lowStock": sum(1 for product in products if product["stock"] <= product["minStock"]),
                "itemsInStock": sum(product["stock"] for product in products),
            },
        })

    def _create_product(self, db: sqlite3.Connection, user: sqlite3.Row) -> None:
        payload = clean_product_payload(self._body())
        product_id = str(uuid.uuid4())
        now = utc_now()
        db.execute(
            "INSERT INTO products(id, user_id, name, category, price_cents, stock, min_stock, barcode, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (product_id, user["id"], payload["name"], payload["category"], payload["price_cents"], payload["stock"], payload["min_stock"], payload["barcode"], now, now),
        )
        log_activity(db, user["id"], "product_created", "Produto adicionado: %s." % payload["name"])
        row = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        db.commit()
        self._json(201, {"product": product_json(row)})

    def _find_product(self, db: sqlite3.Connection, user_id: str, product_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, user_id)).fetchone()
        if not row:
            raise ApiError(404, "Produto não encontrado.")
        return row

    def _update_product(self, db: sqlite3.Connection, user: sqlite3.Row, product_id: str) -> None:
        previous = self._find_product(db, user["id"], product_id)
        data = self._body()
        merged = {
            "name": data.get("name", previous["name"]),
            "category": data.get("category", previous["category"]),
            "price": data.get("price", previous["price_cents"] / 100),
            "stock": data.get("stock", previous["stock"]),
            "minStock": data.get("minStock", previous["min_stock"]),
            "barcode": data.get("barcode", previous["barcode"]),
        }
        payload = clean_product_payload(merged)
        db.execute(
            "UPDATE products SET name=?, category=?, price_cents=?, stock=?, min_stock=?, barcode=?, updated_at=? WHERE id=? AND user_id=?",
            (payload["name"], payload["category"], payload["price_cents"], payload["stock"], payload["min_stock"], payload["barcode"], utc_now(), product_id, user["id"]),
        )
        log_activity(db, user["id"], "product_updated", "Produto atualizado: %s." % payload["name"])
        row = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        db.commit()
        self._json(200, {"product": product_json(row)})

    def _delete_product(self, db: sqlite3.Connection, user: sqlite3.Row, product_id: str) -> None:
        product = self._find_product(db, user["id"], product_id)
        db.execute("DELETE FROM products WHERE id = ? AND user_id = ?", (product_id, user["id"]))
        log_activity(db, user["id"], "product_deleted", "Produto removido: %s." % product["name"])
        db.commit()
        self._json(200, {"ok": True})

    def _create_sale(self, db: sqlite3.Connection, user: sqlite3.Row) -> None:
        data = self._body()
        items = data.get("items")
        payment = str(data.get("paymentMethod") or "").lower()
        if payment not in {"pix", "dinheiro", "debito", "credito"}:
            raise ApiError(400, "Selecione uma forma de pagamento válida.")
        if not isinstance(items, list) or not items or len(items) > 100:
            raise ApiError(400, "Adicione ao menos um produto à venda.")
        normalized: Dict[str, int] = {}
        for item in items:
            if not isinstance(item, dict):
                raise ApiError(400, "Item da venda inválido.")
            product_id = str(item.get("productId") or "")
            try:
                quantity = int(item.get("quantity"))
            except (TypeError, ValueError):
                raise ApiError(400, "Quantidade inválida.")
            if quantity <= 0 or quantity > 10_000:
                raise ApiError(400, "Quantidade inválida.")
            normalized[product_id] = normalized.get(product_id, 0) + quantity
        db.execute("BEGIN IMMEDIATE")
        resolved: List[Tuple[sqlite3.Row, int]] = []
        total_cents = 0
        for product_id, quantity in normalized.items():
            product = self._find_product(db, user["id"], product_id)
            if product["stock"] < quantity:
                raise ApiError(409, "Estoque insuficiente para %s." % product["name"])
            total_cents += product["price_cents"] * quantity
            resolved.append((product, quantity))
        sale_id = str(uuid.uuid4())
        now = utc_now()
        db.execute(
            "INSERT INTO sales(id, user_id, total_cents, payment_method, created_at) VALUES(?,?,?,?,?)",
            (sale_id, user["id"], total_cents, payment, now),
        )
        for product, quantity in resolved:
            db.execute(
                "INSERT INTO sale_items(sale_id, product_id, product_name, quantity, unit_price_cents) VALUES(?,?,?,?,?)",
                (sale_id, product["id"], product["name"], quantity, product["price_cents"]),
            )
            db.execute(
                "UPDATE products SET stock = stock - ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (quantity, now, product["id"], user["id"]),
            )
        log_activity(db, user["id"], "sale_created", "Venda registrada no valor de R$ %.2f." % (total_cents / 100))
        db.commit()
        self._json(201, {"sale": {"id": sale_id, "total": total_cents / 100, "paymentMethod": payment, "createdAt": now}})

    def _update_settings(self, db: sqlite3.Connection, user: sqlite3.Row) -> None:
        data = self._body()
        business_name = str(data.get("businessName") or "").strip()
        merchant_name = str(data.get("merchantName") or "").strip().upper()
        city = str(data.get("city") or "").strip().upper()
        pix_key = str(data.get("pixKey") or "").strip()
        whatsapp = re.sub(r"\D", "", str(data.get("whatsapp") or ""))
        if not (2 <= len(business_name) <= 80):
            raise ApiError(400, "Informe um nome de banca válido.")
        if not (2 <= len(merchant_name) <= 25):
            raise ApiError(400, "O recebedor PIX deve ter entre 2 e 25 caracteres.")
        if not (2 <= len(city) <= 15):
            raise ApiError(400, "A cidade deve ter entre 2 e 15 caracteres.")
        if len(pix_key) > 77 or len(whatsapp) > 15:
            raise ApiError(400, "Revise a chave PIX e o WhatsApp informados.")
        db.execute(
            "UPDATE settings SET business_name=?, merchant_name=?, city=?, pix_key=?, whatsapp=?, updated_at=? WHERE user_id=?",
            (business_name, merchant_name, city, pix_key, whatsapp, utc_now(), user["id"]),
        )
        log_activity(db, user["id"], "settings_updated", "Configurações da banca atualizadas.")
        db.commit()
        self._json(200, {"ok": True})

    def _change_password(self, db: sqlite3.Connection, user: sqlite3.Row) -> None:
        data = self._body()
        current = str(data.get("currentPassword") or "")
        new = str(data.get("newPassword") or "")
        if not verify_password(
            current,
            user["password_salt"],
            user["password_hash"],
            user["password_iterations"],
        ):
            raise ApiError(401, "A senha atual está incorreta.")
        if len(new) < 8 or not re.search(r"[A-Za-z]", new) or not re.search(r"\d", new):
            raise ApiError(400, "A nova senha deve ter ao menos 8 caracteres, uma letra e um número.")
        salt, digest = hash_password(new)
        db.execute(
            "UPDATE users SET password_salt=?, password_hash=?, password_iterations=? WHERE id=?",
            (salt, digest, PASSWORD_ITERATIONS, user["id"]),
        )
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        current_session = jar.get(COOKIE_NAME)
        if current_session and current_session.value:
            current_hash = hashlib.sha256(current_session.value.encode("utf-8")).hexdigest()
            db.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user["id"], current_hash))
        log_activity(db, user["id"], "password_changed", "Senha da conta atualizada.")
        db.commit()
        self._json(200, {"ok": True})


def create_server(host: str, port: int, db_path: Path) -> BancaServer:
    init_db(db_path)
    return BancaServer((host, port), db_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicia o Banca Fácil")
    parser.add_argument("--host", default=os.environ.get("PDV_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PDV_PORT", "8000")))
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("PDV_DB_PATH", str(DEFAULT_DB))))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.db.resolve())
    url = "http://%s:%d" % (args.host, server.server_address[1])
    print("\nBanca Fácil disponível em %s" % url)
    print("Banco de dados: %s" % args.db.resolve())
    print("Conta demo: %s / %s" % (DEMO_EMAIL, DEMO_PASSWORD))
    print("Pressione Ctrl+C para encerrar.\n")
    if not args.no_browser and os.environ.get("PDV_OPEN_BROWSER", "1") != "0":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
