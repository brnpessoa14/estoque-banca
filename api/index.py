"""API serverless do Banca Fácil para Vercel e PostgreSQL Neon."""

import os
import threading
import uuid
from typing import Any, Optional, Type

import psycopg
from psycopg.rows import dict_row

from start import (
    BancaRequestHandler,
    DEMO_EMAIL,
    DEMO_PASSWORD,
    DEMO_PRODUCTS,
    PASSWORD_ITERATIONS,
    hash_password,
    utc_now,
)


POSTGRES_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        password_iterations INTEGER NOT NULL DEFAULT 600000,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at BIGINT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
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
    )
    """,
    "CREATE INDEX IF NOT EXISTS products_user_idx ON products(user_id)",
    """
    CREATE TABLE IF NOT EXISTS sales (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
        payment_method TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS sales_user_date_idx ON sales(user_id, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS sale_items (
        id BIGSERIAL PRIMARY KEY,
        sale_id TEXT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
        product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        business_name TEXT NOT NULL DEFAULT 'Minha Banca',
        merchant_name TEXT NOT NULL DEFAULT 'MINHA BANCA',
        city TEXT NOT NULL DEFAULT 'SAO PAULO',
        pix_key TEXT NOT NULL DEFAULT '',
        whatsapp TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS activity_logs (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        type TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS activity_user_date_idx ON activity_logs(user_id, created_at DESC)",
)


class PostgresDatabase:
    """Adapta a conexão Psycopg à interface SQL usada pelo servidor local."""

    dialect = "postgres"

    def __init__(self) -> None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("A variável DATABASE_URL não está configurada.")
        self.connection = psycopg.connect(
            database_url,
            row_factory=dict_row,
            connect_timeout=10,
            prepare_threshold=None,
        )

    def __enter__(self) -> "PostgresDatabase":
        return self

    def __exit__(
        self,
        exception_type: Optional[Type[BaseException]],
        exception: Optional[BaseException],
        traceback: Any,
    ) -> None:
        try:
            if exception_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> Any:
        return self.connection.execute(query.replace("?", "%s"), parameters)

    def commit(self) -> None:
        self.connection.commit()


_initialized = False
_initialization_lock = threading.Lock()


def initialize_postgres() -> None:
    """Cria o schema e a conta de demonstração uma vez por instância ativa."""

    global _initialized
    if _initialized:
        return
    with _initialization_lock:
        if _initialized:
            return
        with PostgresDatabase() as database:
            database.execute("SELECT pg_advisory_xact_lock(74202201)")
            for statement in POSTGRES_SCHEMA:
                database.execute(statement)

            now = utc_now()
            demo = database.execute(
                "SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)
            ).fetchone()
            if not demo:
                salt, digest = hash_password(DEMO_PASSWORD)
                database.execute(
                    """
                    INSERT INTO users(
                        id, name, email, password_salt, password_hash,
                        password_iterations, created_at
                    ) VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(email) DO NOTHING
                    """,
                    (
                        str(uuid.uuid4()),
                        "Cliente Demonstração",
                        DEMO_EMAIL,
                        salt,
                        digest,
                        PASSWORD_ITERATIONS,
                        now,
                    ),
                )
                demo = database.execute(
                    "SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)
                ).fetchone()
            user_id = demo["id"]
            database.execute(
                """
                INSERT INTO settings(
                    user_id, business_name, merchant_name, city,
                    pix_key, whatsapp, updated_at
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (
                    user_id,
                    "Banca Central",
                    "BANCA CENTRAL",
                    "SAO PAULO",
                    DEMO_EMAIL,
                    "",
                    now,
                ),
            )
            product_count = database.execute(
                "SELECT COUNT(*) AS total FROM products WHERE user_id = ?", (user_id,)
            ).fetchone()["total"]
            if product_count == 0:
                for name, category, price, stock, minimum, barcode in DEMO_PRODUCTS:
                    database.execute(
                        """
                        INSERT INTO products(
                            id, user_id, name, category, price_cents, stock,
                            min_stock, barcode, created_at, updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            str(uuid.uuid4()),
                            user_id,
                            name,
                            category,
                            price,
                            stock,
                            minimum,
                            barcode,
                            now,
                            now,
                        ),
                    )
            has_activity = database.execute(
                "SELECT 1 FROM activity_logs WHERE user_id = ? LIMIT 1", (user_id,)
            ).fetchone()
            if not has_activity:
                database.execute(
                    """
                    INSERT INTO activity_logs(user_id, type, message, created_at)
                    VALUES(?,?,?,?)
                    """,
                    (user_id, "account_created", "Conta de demonstração preparada.", now),
                )
        _initialized = True


class handler(BancaRequestHandler):
    """Entrypoint reconhecido pelo runtime Python da Vercel."""

    def _database(self) -> PostgresDatabase:
        initialize_postgres()
        return PostgresDatabase()

    @staticmethod
    def _is_integrity_error(error: Exception) -> bool:
        return isinstance(error, psycopg.IntegrityError)

    def _cookie_is_secure(self) -> bool:
        return True
