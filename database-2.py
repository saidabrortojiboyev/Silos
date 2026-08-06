import sqlite3
import math
from datetime import datetime, timedelta

DB_NAME = "yem_xashak.db"


def init_db():
    """Ma'lumotlar bazasi va jadvallarni yaratish"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            unit TEXT NOT NULL,
            price INTEGER NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS catalog_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            company TEXT,
            description TEXT,
            price INTEGER,
            unit TEXT DEFAULT 'dona',
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    ci_cols = [row[1] for row in cur.execute("PRAGMA table_info(catalog_items)").fetchall()]
    if "unit" not in ci_cols:
        cur.execute("ALTER TABLE catalog_items ADD COLUMN unit TEXT DEFAULT 'dona'")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            product_name TEXT,
            quantity REAL,
            unit TEXT,
            price INTEGER,
            total_price INTEGER,
            region TEXT,
            address TEXT,
            status TEXT DEFAULT 'yangi',
            seller_id INTEGER,
            driver_id INTEGER,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            phone TEXT,
            vehicle_type TEXT,
            vehicle_number TEXT,
            capacity_tons REAL,
            region TEXT,
            status TEXT DEFAULT 'kutilmoqda',
            created_at TEXT
        )
    """)

    drv_cols = [row[1] for row in cur.execute("PRAGMA table_info(drivers)").fetchall()]
    if "vehicle_number" not in drv_cols:
        cur.execute("ALTER TABLE drivers ADD COLUMN vehicle_number TEXT")
    if "latitude" not in drv_cols:
        cur.execute("ALTER TABLE drivers ADD COLUMN latitude REAL")
    if "longitude" not in drv_cols:
        cur.execute("ALTER TABLE drivers ADD COLUMN longitude REAL")
    if "tuman" not in drv_cols:
        cur.execute("ALTER TABLE drivers ADD COLUMN tuman TEXT")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sellers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL UNIQUE,
            shop_name TEXT NOT NULL,
            phone TEXT,
            region TEXT,
            status TEXT DEFAULT 'kutilmoqda',
            vehicle_type TEXT,
            capacity_tons REAL,
            delivers_self INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    # Eski bazalarda (yangi ustunlar qo'shilishidan oldin yaratilgan) migratsiya
    existing_cols = [row[1] for row in cur.execute("PRAGMA table_info(sellers)").fetchall()]
    if "vehicle_type" not in existing_cols:
        cur.execute("ALTER TABLE sellers ADD COLUMN vehicle_type TEXT")
    if "capacity_tons" not in existing_cols:
        cur.execute("ALTER TABLE sellers ADD COLUMN capacity_tons REAL")
    if "delivers_self" not in existing_cols:
        cur.execute("ALTER TABLE sellers ADD COLUMN delivers_self INTEGER DEFAULT 0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS seller_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            unit TEXT NOT NULL,
            price INTEGER NOT NULL,
            quantity_available REAL DEFAULT 0,
            pickup_address TEXT,
            claimed INTEGER DEFAULT 0,
            package_type TEXT DEFAULT 'naval',
            photo_file_id TEXT,
            FOREIGN KEY (seller_id) REFERENCES sellers (id)
        )
    """)

    sp_cols = [row[1] for row in cur.execute("PRAGMA table_info(seller_products)").fetchall()]
    if "pickup_address" not in sp_cols:
        cur.execute("ALTER TABLE seller_products ADD COLUMN pickup_address TEXT")
    if "claimed" not in sp_cols:
        cur.execute("ALTER TABLE seller_products ADD COLUMN claimed INTEGER DEFAULT 0")
    if "package_type" not in sp_cols:
        cur.execute("ALTER TABLE seller_products ADD COLUMN package_type TEXT DEFAULT 'naval'")
    if "photo_file_id" not in sp_cols:
        cur.execute("ALTER TABLE seller_products ADD COLUMN photo_file_id TEXT")
    if "description" not in sp_cols:
        cur.execute("ALTER TABLE seller_products ADD COLUMN description TEXT")
    if "created_at" not in sp_cols:
        cur.execute("ALTER TABLE seller_products ADD COLUMN created_at TEXT")
    if "latitude" not in sp_cols:
        cur.execute("ALTER TABLE seller_products ADD COLUMN latitude REAL")
    if "longitude" not in sp_cols:
        cur.execute("ALTER TABLE seller_products ADD COLUMN longitude REAL")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS driver_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            seller_product_id INTEGER,
            product_name TEXT NOT NULL,
            unit TEXT NOT NULL,
            quantity REAL,
            estimated_quantity REAL,
            actual_weight REAL,
            weight_status TEXT DEFAULT 'kutilmoqda',
            base_price INTEGER,
            sell_price INTEGER,
            farmer_payment INTEGER,
            payment_confirmed INTEGER DEFAULT 0,
            region TEXT,
            pickup_address TEXT,
            package_type TEXT DEFAULT 'naval',
            photo_file_id TEXT,
            status TEXT DEFAULT 'faol',
            created_at TEXT,
            FOREIGN KEY (driver_id) REFERENCES drivers (id),
            FOREIGN KEY (seller_id) REFERENCES sellers (id)
        )
    """)

    dl_cols = [row[1] for row in cur.execute("PRAGMA table_info(driver_listings)").fetchall()]
    if "photo_file_id" not in dl_cols:
        cur.execute("ALTER TABLE driver_listings ADD COLUMN photo_file_id TEXT")
    if "weight_photo_file_id" not in dl_cols:
        cur.execute("ALTER TABLE driver_listings ADD COLUMN weight_photo_file_id TEXT")
    if "package_type" not in dl_cols:
        cur.execute("ALTER TABLE driver_listings ADD COLUMN package_type TEXT DEFAULT 'naval'")
    if "estimated_quantity" not in dl_cols:
        cur.execute("ALTER TABLE driver_listings ADD COLUMN estimated_quantity REAL")
    if "actual_weight" not in dl_cols:
        cur.execute("ALTER TABLE driver_listings ADD COLUMN actual_weight REAL")
    if "weight_status" not in dl_cols:
        cur.execute("ALTER TABLE driver_listings ADD COLUMN weight_status TEXT DEFAULT 'kutilmoqda'")
    if "farmer_payment" not in dl_cols:
        cur.execute("ALTER TABLE driver_listings ADD COLUMN farmer_payment INTEGER")
    if "payment_confirmed" not in dl_cols:
        cur.execute("ALTER TABLE driver_listings ADD COLUMN payment_confirmed INTEGER DEFAULT 0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            referred_by INTEGER,
            discount_percent INTEGER DEFAULT 0,
            referral_rewarded INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS combine_owners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            phone TEXT,
            region TEXT,
            status TEXT DEFAULT 'kutilmoqda',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS combine_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            price_per_gektar INTEGER NOT NULL,
            photo_file_id TEXT,
            address TEXT,
            region TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT,
            FOREIGN KEY (owner_id) REFERENCES combine_owners (id)
        )
    """)

    cl_cols = [row[1] for row in cur.execute("PRAGMA table_info(combine_listings)").fetchall()]
    if "coverage" not in cl_cols:
        cur.execute("ALTER TABLE combine_listings ADD COLUMN coverage TEXT DEFAULT 'vodiy'")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS combine_silos_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            price_per_kg INTEGER NOT NULL,
            quantity_available REAL,
            photo_file_id TEXT,
            address TEXT,
            region TEXT,
            latitude REAL,
            longitude REAL,
            active INTEGER DEFAULT 1,
            created_at TEXT,
            FOREIGN KEY (owner_id) REFERENCES combine_owners (id)
        )
    """)

    csl_cols = [row[1] for row in cur.execute("PRAGMA table_info(combine_silos_listings)").fetchall()]
    if "latitude" not in csl_cols:
        cur.execute("ALTER TABLE combine_silos_listings ADD COLUMN latitude REAL")
    if "longitude" not in csl_cols:
        cur.execute("ALTER TABLE combine_silos_listings ADD COLUMN longitude REAL")
    if "description" not in csl_cols:
        cur.execute("ALTER TABLE combine_silos_listings ADD COLUMN description TEXT")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS driver_silos_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            price_per_kg INTEGER NOT NULL,
            quantity_available REAL,
            photo_file_id TEXT,
            address TEXT,
            region TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT,
            FOREIGN KEY (driver_id) REFERENCES drivers (id)
        )
    """)

    dsl_cols = [row[1] for row in cur.execute("PRAGMA table_info(driver_silos_listings)").fetchall()]
    if "description" not in dsl_cols:
        cur.execute("ALTER TABLE driver_silos_listings ADD COLUMN description TEXT")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS manual_ledger_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            vehicle_number TEXT,
            phone TEXT,
            price_per_kg INTEGER NOT NULL,
            kg REAL,
            total_sum INTEGER,
            paid INTEGER DEFAULT 0,
            region TEXT,
            created_at TEXT,
            FOREIGN KEY (seller_id) REFERENCES sellers (id)
        )
    """)

    # Eski sxemalarni (avval tonna NOT NULL, keyin price_per_ton/tonna) yangi kg-asosidagi sxemaga ko'chirish
    mle_cols = cur.execute("PRAGMA table_info(manual_ledger_entries)").fetchall()
    mle_col_names = [c[1] for c in mle_cols]
    if "price_per_ton" in mle_col_names or "tonna" in mle_col_names:
        cur.execute("ALTER TABLE manual_ledger_entries RENAME TO manual_ledger_entries_old")
        cur.execute("""
            CREATE TABLE manual_ledger_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER NOT NULL,
                vehicle_number TEXT,
                phone TEXT,
                price_per_kg INTEGER NOT NULL,
                kg REAL,
                total_sum INTEGER,
                paid INTEGER DEFAULT 0,
                region TEXT,
                created_at TEXT,
                FOREIGN KEY (seller_id) REFERENCES sellers (id)
            )
        """)
        cur.execute("""
            INSERT INTO manual_ledger_entries (id, seller_id, vehicle_number, phone, price_per_kg,
                                                kg, total_sum, paid, region, created_at)
            SELECT id, seller_id, vehicle_number, phone,
                   CAST(price_per_ton AS REAL) / 1000.0,
                   tonna * 1000.0,
                   total_sum, paid, region, created_at
            FROM manual_ledger_entries_old
        """)
        cur.execute("DROP TABLE manual_ledger_entries_old")

    # Boshlang'ich mahsulotlar (agar mavjud bo'lmasa)
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        default_products = [
            ("Silos", "tonna", 350000),
            ("Somon", "tonna", 400000),
            ("Beda (yonchqa)", "tonna", 900000),
        ]
        cur.executemany(
            "INSERT INTO products (name, unit, price) VALUES (?, ?, ?)",
            default_products
        )

    conn.commit()
    conn.close()


def get_active_products():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, unit, price FROM products WHERE active = 1")
    rows = cur.fetchall()
    conn.close()
    return rows


# ----------------- Katalog (urug'lar, vetapteka, mineral o'g'itlar) -----------------

def add_catalog_item(category, name, company, description, price, unit="dona"):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO catalog_items (category, name, company, description, price, unit, active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
    """, (category, name, company, description, price, unit, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    item_id = cur.lastrowid
    conn.close()
    return item_id


def get_catalog_items(category):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, company, description, price, unit
        FROM catalog_items WHERE category = ? AND active = 1
        ORDER BY id DESC
    """, (category,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_orderable_catalog_items():
    """Buyurtma katalogi uchun: narxi belgilangan barcha faol elementlar (barcha bo'limlardan)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, category, name, company, price, unit
        FROM catalog_items WHERE active = 1 AND price IS NOT NULL
        ORDER BY category, id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_catalog_item_by_id(item_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, category, name, company, description, price, unit
        FROM catalog_items WHERE id = ?
    """, (item_id,))
    row = cur.fetchone()
    conn.close()
    return row


def deactivate_catalog_item(item_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE catalog_items SET active = 0 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def get_product_by_id(product_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, unit, price FROM products WHERE id = ?", (product_id,))
    row = cur.fetchone()
    conn.close()
    return row


def create_order(user_id, username, full_name, phone, product_name,
                  quantity, unit, price, total_price, region, address,
                  seller_id=None, driver_id=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders (user_id, username, full_name, phone, product_name,
                             quantity, unit, price, total_price, region, address,
                             status, seller_id, driver_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, full_name, phone, product_name, quantity, unit,
          price, total_price, region, address, "yangi", seller_id, driver_id,
          datetime.now().strftime("%Y-%m-%d %H:%M")))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


def get_user_orders(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, product_name, quantity, unit, total_price, status, created_at
        FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_orders(limit=20):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, full_name, phone, product_name, quantity, unit,
               total_price, region, address, status, created_at
        FROM orders ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def update_order_status(order_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


def assign_order_seller(order_id, seller_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE orders SET seller_id = ? WHERE id = ?", (seller_id, order_id))
    conn.commit()
    conn.close()


# ----------------- Sotuvchilar (sellers) -----------------

def register_seller(telegram_id, shop_name, phone, region, vehicle_type=None, capacity_tons=None, delivers_self=0):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sellers (telegram_id, shop_name, phone, region, status,
                              vehicle_type, capacity_tons, delivers_self, created_at)
        VALUES (?, ?, ?, ?, 'tasdiqlangan', ?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            shop_name=excluded.shop_name, phone=excluded.phone,
            region=excluded.region, status='tasdiqlangan',
            vehicle_type=excluded.vehicle_type, capacity_tons=excluded.capacity_tons,
            delivers_self=excluded.delivers_self
    """, (telegram_id, shop_name, phone, region, vehicle_type, capacity_tons, delivers_self,
          datetime.now().strftime("%Y-%m-%d %H:%M")))
    seller_id = cur.lastrowid
    conn.commit()
    conn.close()
    return seller_id


def get_seller_by_telegram_id(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, telegram_id, shop_name, phone, region, status,
               vehicle_type, capacity_tons, delivers_self
        FROM sellers WHERE telegram_id = ?
    """, (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_pending_sellers():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, telegram_id, shop_name, phone, region
        FROM sellers WHERE status = 'kutilmoqda'
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def set_seller_status(seller_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE sellers SET status = ? WHERE id = ?", (status, seller_id))
    conn.commit()
    conn.close()


def update_seller_phone(seller_id, phone):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE sellers SET phone = ? WHERE id = ?", (phone, seller_id))
    conn.commit()
    conn.close()


def get_seller_by_id(seller_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, telegram_id, shop_name, phone, region, status,
               vehicle_type, capacity_tons, delivers_self
        FROM sellers WHERE id = ?
    """, (seller_id,))
    row = cur.fetchone()
    conn.close()
    return row


def add_seller_product(seller_id, product_name, unit, price, quantity_available, pickup_address=None, package_type="naval", photo_file_id=None, latitude=None, longitude=None, description=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO seller_products (seller_id, product_name, unit, price, quantity_available, pickup_address, claimed, package_type, photo_file_id, latitude, longitude, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
    """, (seller_id, product_name, unit, price, quantity_available, pickup_address, package_type, photo_file_id, latitude, longitude, description,
          datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    sp_id = cur.lastrowid
    conn.close()
    return sp_id


def get_seller_products(seller_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, product_name, unit, price, quantity_available, pickup_address, claimed, package_type, photo_file_id
        FROM seller_products WHERE seller_id = ?
    """, (seller_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def find_sellers_by_region_and_product(region, product_name):
    """Berilgan hududda shu mahsulotni sotadigan (hali haydovchi olmagan) tasdiqlangan sotuvchilarni topish"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.telegram_id, s.shop_name, s.phone, sp.price, sp.quantity_available,
               s.delivers_self, s.vehicle_type, s.capacity_tons
        FROM sellers s
        JOIN seller_products sp ON sp.seller_id = s.id
        WHERE s.status = 'tasdiqlangan' AND s.region = ? AND sp.product_name = ?
              AND sp.quantity_available > 0 AND sp.claimed = 0
    """, (region, product_name))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_active_qopli_listings(region=None):
    """'Qopli silos' bo'limi uchun: barcha faol qopli (respublika bo'ylab yetkaziladigan) e'lonlar,
    do'kon/sotuvchilar tomonidan qo'yilgan, eng arzonidan boshlab.
    Agar `region` berilsa, faqat shu viloyatdagi sotuvchilar qaytariladi."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if region:
        cur.execute("""
            SELECT sp.id, s.id, s.telegram_id, s.shop_name, sp.product_name, sp.unit,
                   sp.price, sp.quantity_available, s.region, sp.pickup_address,
                   sp.photo_file_id, s.phone, sp.description
            FROM seller_products sp
            JOIN sellers s ON s.id = sp.seller_id
            WHERE s.status = 'tasdiqlangan' AND sp.package_type = 'qopli'
                  AND sp.quantity_available > 0 AND sp.claimed = 0 AND s.region = ?
            ORDER BY sp.price ASC
        """, (region,))
    else:
        cur.execute("""
            SELECT sp.id, s.id, s.telegram_id, s.shop_name, sp.product_name, sp.unit,
                   sp.price, sp.quantity_available, s.region, sp.pickup_address,
                   sp.photo_file_id, s.phone, sp.description
            FROM seller_products sp
            JOIN sellers s ON s.id = sp.seller_id
            WHERE s.status = 'tasdiqlangan' AND sp.package_type = 'qopli'
                  AND sp.quantity_available > 0 AND sp.claimed = 0
            ORDER BY sp.price ASC
        """)
    rows = cur.fetchall()
    conn.close()
    return rows


def find_direct_sellers_by_product(product_name, package_type=None):
    """O'zi yetkazib beradigan (delivers_self=1) sotuvchilarning mahsulotini nomi bo'yicha qidirish
    (hudud tanlanmasdan oldin, buyurtma katalogi uchun) — eng arzonidan boshlab qaytaradi"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if package_type:
        cur.execute("""
            SELECT sp.id, s.id, s.telegram_id, s.shop_name, sp.product_name, sp.unit,
                   sp.price, sp.quantity_available, s.region, sp.package_type, sp.photo_file_id
            FROM seller_products sp
            JOIN sellers s ON s.id = sp.seller_id
            WHERE s.status = 'tasdiqlangan' AND s.delivers_self = 1
                  AND sp.quantity_available > 0 AND sp.claimed = 0
                  AND sp.product_name LIKE ? AND sp.package_type = ?
            ORDER BY sp.price ASC
        """, (f"%{product_name}%", package_type))
    else:
        cur.execute("""
            SELECT sp.id, s.id, s.telegram_id, s.shop_name, sp.product_name, sp.unit,
                   sp.price, sp.quantity_available, s.region, sp.package_type, sp.photo_file_id
            FROM seller_products sp
            JOIN sellers s ON s.id = sp.seller_id
            WHERE s.status = 'tasdiqlangan' AND s.delivers_self = 1
                  AND sp.quantity_available > 0 AND sp.claimed = 0
                  AND sp.product_name LIKE ?
            ORDER BY sp.price ASC
        """, (f"%{product_name}%",))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_available_farmer_loads(region=None):
    """Haydovchilar uchun: hali hech kim olmagan, tasdiqlangan fermer/sotuvchi yuklari.
    Agar `region` berilsa, faqat shu viloyatdagi yuklar qaytariladi."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if region:
        cur.execute("""
            SELECT sp.id, s.shop_name, s.phone, s.region, sp.product_name, sp.unit,
                   sp.price, sp.quantity_available, sp.pickup_address, sp.package_type, sp.photo_file_id,
                   sp.description
            FROM seller_products sp
            JOIN sellers s ON s.id = sp.seller_id
            WHERE s.status = 'tasdiqlangan' AND sp.quantity_available > 0 AND sp.claimed = 0
                  AND s.region = ?
            ORDER BY sp.id DESC
        """, (region,))
    else:
        cur.execute("""
            SELECT sp.id, s.shop_name, s.phone, s.region, sp.product_name, sp.unit,
                   sp.price, sp.quantity_available, sp.pickup_address, sp.package_type, sp.photo_file_id,
                   sp.description
            FROM seller_products sp
            JOIN sellers s ON s.id = sp.seller_id
            WHERE s.status = 'tasdiqlangan' AND sp.quantity_available > 0 AND sp.claimed = 0
            ORDER BY sp.id DESC
        """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_seller_product_by_id(sp_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT sp.id, sp.seller_id, sp.product_name, sp.unit, sp.price,
               sp.quantity_available, sp.pickup_address, sp.claimed,
               s.telegram_id, s.shop_name, s.region, sp.package_type, sp.photo_file_id
        FROM seller_products sp JOIN sellers s ON s.id = sp.seller_id
        WHERE sp.id = ?
    """, (sp_id,))
    row = cur.fetchone()
    conn.close()
    return row


def reduce_seller_product_quantity(sp_id, sold_qty):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT quantity_available FROM seller_products WHERE id = ?", (sp_id,))
    row = cur.fetchone()
    if not row or row[0] is None:
        conn.close()
        return
    new_qty = max(0, row[0] - sold_qty)
    cur.execute("UPDATE seller_products SET quantity_available = ? WHERE id = ?", (new_qty, sp_id))
    conn.commit()
    conn.close()


def claim_farm_load(seller_product_id, driver_id, farmer_quantity, sell_price,
                     resale_quantity=None, resale_unit=None, photo_file_id=None):
    """
    Haydovchi fermer yukidan ma'lum miqdorni oladi (masalan necha gektar) va o'zi sotadigan
    miqdor/birlikni (masalan necha kg) alohida belgilaydi. Agar resale_quantity/resale_unit
    berilmasa, fermerning o'zi bergan miqdor/birlik ishlatiladi (gektar bo'lmagan holatlar uchun).
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT sp.seller_id, sp.product_name, sp.unit, sp.price, sp.quantity_available,
               sp.pickup_address, sp.claimed, s.region, sp.package_type
        FROM seller_products sp JOIN sellers s ON s.id = sp.seller_id
        WHERE sp.id = ?
    """, (seller_product_id,))
    row = cur.fetchone()
    if not row or row[6] == 1:
        conn.close()
        return None

    seller_id, product_name, farmer_unit, base_price, available_qty, pickup_address, _, region, package_type = row

    if farmer_quantity <= 0 or farmer_quantity > available_qty:
        conn.close()
        return None

    remaining = round(available_qty - farmer_quantity, 3)
    new_claimed = 1 if remaining <= 0 else 0
    cur.execute(
        "UPDATE seller_products SET quantity_available = ?, claimed = ? WHERE id = ?",
        (remaining, new_claimed, seller_product_id)
    )

    final_quantity = resale_quantity if resale_quantity is not None else farmer_quantity
    final_unit = resale_unit if resale_unit else farmer_unit
    # Fermer narxi har doim "1 kg uchun" deb belgilanadi (gektar faqat yer maydonini bildiradi) —
    # shuning uchun to'lov haydovchi sotadigan (yoki kutilayotgan) kg miqdoriga qarab hisoblanadi
    farmer_payment = round(base_price * final_quantity)

    # Fermer "gektar" hisobida qo'ygan bo'lsa-yu, haydovchi kg hisobida qayta sotayotgan bo'lsa —
    # bu endi mijoz uchun oddiy "naval" (kg, sochilma) turi hisoblanadi
    final_package_type = "naval" if (package_type == "gektar" and final_unit == "kg") else package_type

    cur.execute("""
        INSERT INTO driver_listings (driver_id, seller_id, seller_product_id, product_name, unit,
                                      quantity, estimated_quantity, actual_weight, weight_status,
                                      base_price, sell_price, farmer_payment, payment_confirmed,
                                      region, pickup_address, package_type, photo_file_id, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'kutilmoqda', ?, ?, ?, 0, ?, ?, ?, ?, 'faol', ?)
    """, (driver_id, seller_id, seller_product_id, product_name, final_unit, final_quantity, final_quantity,
          base_price, sell_price, farmer_payment, region, pickup_address, final_package_type, photo_file_id,
          datetime.now().strftime("%Y-%m-%d %H:%M")))
    listing_id = cur.lastrowid
    conn.commit()
    conn.close()
    return listing_id


def confirm_payment(listing_id):
    """Fermer haydovchidan pulni olganini tasdiqlaydi"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE driver_listings SET payment_confirmed = 1 WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()


def get_driver_debts(driver_id, exclude_listing_id=None, region=None):
    """Haydovchining to'lanmagan qarzlarini qaytaradi.
    Qora ro'yxat endi FAQAT bitta viloyat ichida shakllanadi — agar `region` berilsa,
    faqat shu viloyatdagi (dl.region) qarzlar hisobga olinadi, boshqa viloyatdagi
    to'lanmagan qarzlar bu yerga ta'sir qilmaydi."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if region:
        cur.execute("""
            SELECT dl.id, s.shop_name, dl.farmer_payment, dl.created_at
            FROM driver_listings dl
            JOIN sellers s ON s.id = dl.seller_id
            WHERE dl.driver_id = ? AND dl.payment_confirmed = 0 AND dl.region = ?
        """, (driver_id, region))
    else:
        cur.execute("""
            SELECT dl.id, s.shop_name, dl.farmer_payment, dl.created_at
            FROM driver_listings dl
            JOIN sellers s ON s.id = dl.seller_id
            WHERE dl.driver_id = ? AND dl.payment_confirmed = 0
        """, (driver_id,))
    rows = cur.fetchall()
    conn.close()

    debts = []
    for listing_id, farmer_name, amount, created_at in rows:
        if exclude_listing_id and listing_id == exclude_listing_id:
            continue
        if not created_at:
            continue
        try:
            days = (datetime.now() - datetime.strptime(created_at, "%Y-%m-%d %H:%M")).days
        except ValueError:
            continue
        if days >= 5:
            level = "qizil"
        elif days >= 3:
            level = "sariq"
        else:
            continue
        debts.append({"farmer_name": farmer_name, "amount": amount, "days": days, "level": level})
    return debts


def get_all_unpaid_transactions():
    """Admin uchun: platformadagi barcha to'lanmagan tranzaksiyalar (fermerlar bo'yicha)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT dl.id, s.shop_name, d.full_name, d.vehicle_number, dl.product_name,
               dl.quantity, dl.unit, dl.farmer_payment, dl.created_at
        FROM driver_listings dl
        JOIN sellers s ON s.id = dl.seller_id
        JOIN drivers d ON d.id = dl.driver_id
        WHERE dl.payment_confirmed = 0
        ORDER BY dl.created_at ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_farmer_transactions(seller_id):
    """Fermerning barcha e'lonlari (eski va yangi) bo'yicha haydovchilar hisoboti — Excel jadvaliga o'xshash"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT shop_name, phone FROM sellers WHERE id = ?", (seller_id,))
    farmer_row = cur.fetchone()
    farmer_name = farmer_row[0] if farmer_row else ""

    cur.execute("""
        SELECT sp.id, sp.product_name, sp.unit, sp.price, sp.quantity_available, sp.claimed
        FROM seller_products sp
        WHERE sp.seller_id = ?
        ORDER BY sp.id DESC
    """, (seller_id,))
    postings = cur.fetchall()

    report = []
    for sp_id, product_name, unit, price, remaining_qty, claimed in postings:
        cur.execute("""
            SELECT dl.id, d.full_name, d.vehicle_number, d.phone, dl.quantity, dl.farmer_payment,
                   dl.payment_confirmed, dl.weight_status, dl.actual_weight, dl.created_at, dl.driver_id
            FROM driver_listings dl
            JOIN drivers d ON d.id = dl.driver_id
            WHERE dl.seller_product_id = ?
            ORDER BY dl.id ASC
        """, (sp_id,))
        rows = cur.fetchall()
        report.append({
            "sp_id": sp_id, "product_name": product_name, "unit": unit, "price": price,
            "remaining_qty": remaining_qty, "claimed": claimed, "transactions": rows
        })

    conn.close()
    return farmer_name, report


def get_farmer_transactions_flat(seller_id):
    """Fermerning BARCHA e'lonlari bo'yicha, bitta yagona (soddalashtirilgan) shaxsiy jadval uchun —
    barcha haydovchi tranzaksiyalarini (botdan yuk olganlar + fermer o'zi qo'lda yozganlar) bitta
    ro'yxatga jamlaydi (posting bo'yicha bo'lmaydi), sana bo'yicha tartiblab."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT shop_name, phone FROM sellers WHERE id = ?", (seller_id,))
    farmer_row = cur.fetchone()
    farmer_name = farmer_row[0] if farmer_row else ""

    cur.execute("""
        SELECT dl.id, d.vehicle_number, d.phone, dl.quantity, dl.farmer_payment,
               dl.payment_confirmed, dl.created_at, dl.driver_id, sp.unit, sp.price
        FROM driver_listings dl
        JOIN drivers d ON d.id = dl.driver_id
        JOIN seller_products sp ON sp.id = dl.seller_product_id
        WHERE sp.seller_id = ?
        ORDER BY dl.id ASC
    """, (seller_id,))
    bot_rows = cur.fetchall()

    cur.execute("""
        SELECT id, vehicle_number, phone, price_per_kg, kg, total_sum, paid, created_at
        FROM manual_ledger_entries
        WHERE seller_id = ? AND kg IS NOT NULL
        ORDER BY id ASC
    """, (seller_id,))
    manual_rows = cur.fetchall()
    conn.close()

    combined = []
    for tid, vehicle_number, phone, quantity, payment, confirmed, created_at, driver_id, unit, price in bot_rows:
        combined.append({
            "source": "bot", "id": tid, "vehicle_number": vehicle_number, "phone": phone,
            "quantity": quantity, "payment": payment, "confirmed": confirmed,
            "created_at": created_at, "driver_id": driver_id, "unit": unit, "price": price,
        })
    for mid, vehicle_number, phone, price_per_kg, kg, total_sum, paid, created_at in manual_rows:
        combined.append({
            "source": "manual", "id": mid, "vehicle_number": vehicle_number, "phone": phone,
            "quantity": kg, "payment": total_sum, "confirmed": paid,
            "created_at": created_at, "driver_id": None, "unit": "kg", "price": price_per_kg,
        })

    combined.sort(key=lambda r: r["created_at"] or "")
    return farmer_name, combined


def get_pending_manual_entries_for_seller(seller_id):
    """Miqdori hali kiritilmagan (tarozidan hali natija kelmagan) qolda yozilgan yozuvlar"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, vehicle_number, phone, price_per_kg, created_at
        FROM manual_ledger_entries
        WHERE seller_id = ? AND kg IS NULL
        ORDER BY id ASC
    """, (seller_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_manual_entry_by_id(entry_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT mle.id, mle.seller_id, mle.vehicle_number, mle.phone, mle.price_per_kg, mle.kg,
               mle.total_sum, mle.paid, mle.region, s.telegram_id, s.shop_name
        FROM manual_ledger_entries mle
        JOIN sellers s ON s.id = mle.seller_id
        WHERE mle.id = ?
    """, (entry_id,))
    row = cur.fetchone()
    conn.close()
    return row


def set_manual_entry_weight(entry_id, kg):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT price_per_kg FROM manual_ledger_entries WHERE id = ?", (entry_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    total_sum = round(row[0] * kg)
    cur.execute("UPDATE manual_ledger_entries SET kg = ?, total_sum = ? WHERE id = ?",
                (kg, total_sum, entry_id))
    conn.commit()
    conn.close()
    return total_sum


def get_unpaid_entries_for_seller(seller_id):
    """Fermer uchun: hali pul olinmagan barcha yozuvlar (bot orqali + qolda yozilgan), '✅ Pulni belgilash' uchun"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT dl.id, d.vehicle_number, dl.farmer_payment, dl.quantity, sp.unit
        FROM driver_listings dl
        JOIN drivers d ON d.id = dl.driver_id
        JOIN seller_products sp ON sp.id = dl.seller_product_id
        WHERE sp.seller_id = ? AND dl.payment_confirmed = 0
        ORDER BY dl.id ASC
    """, (seller_id,))
    bot_rows = cur.fetchall()
    cur.execute("""
        SELECT id, vehicle_number, total_sum
        FROM manual_ledger_entries
        WHERE seller_id = ? AND paid = 0 AND kg IS NOT NULL
        ORDER BY id ASC
    """, (seller_id,))
    manual_rows = cur.fetchall()
    conn.close()
    return bot_rows, manual_rows


def get_vehicle_debts(vehicle_number, region, exclude_manual_id=None):
    """Mashina raqami bo'yicha, shu VILOYAT ichida to'lanmagan qarzlarni tekshiradi — botda ro'yxatdan
    o'tgan haydovchilar (driver_listings) VA fermer qo'lda yozgan yozuvlar (manual_ledger_entries)
    ikkalasini ham hisobga oladi. Yangi kelgan mashinani darhol tekshirish uchun ishlatiladi."""
    if not vehicle_number:
        return []
    veh_key = vehicle_number.strip().upper()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT s.shop_name, dl.farmer_payment, dl.created_at
        FROM driver_listings dl
        JOIN drivers d ON d.id = dl.driver_id
        JOIN sellers s ON s.id = dl.seller_id
        WHERE UPPER(TRIM(d.vehicle_number)) = ? AND dl.region = ? AND dl.payment_confirmed = 0
    """, (veh_key, region))
    rows = cur.fetchall()
    cur.execute("""
        SELECT s.shop_name, mle.total_sum, mle.created_at, mle.id
        FROM manual_ledger_entries mle
        JOIN sellers s ON s.id = mle.seller_id
        WHERE UPPER(TRIM(mle.vehicle_number)) = ? AND mle.region = ? AND mle.paid = 0
              AND mle.total_sum IS NOT NULL
    """, (veh_key, region))
    manual_rows = cur.fetchall()
    conn.close()

    debts = []
    for farmer_name, amount, created_at in rows:
        if not created_at:
            continue
        try:
            days = (datetime.now() - datetime.strptime(created_at, "%Y-%m-%d %H:%M")).days
        except ValueError:
            continue
        if days >= 5:
            level = "qizil"
        elif days >= 3:
            level = "sariq"
        else:
            continue
        debts.append({"farmer_name": farmer_name, "amount": amount, "days": days, "level": level})
    for farmer_name, amount, created_at, mid in manual_rows:
        if exclude_manual_id and mid == exclude_manual_id:
            continue
        if not created_at:
            continue
        try:
            days = (datetime.now() - datetime.strptime(created_at, "%Y-%m-%d %H:%M")).days
        except ValueError:
            continue
        if days >= 5:
            level = "qizil"
        elif days >= 3:
            level = "sariq"
        else:
            continue
        debts.append({"farmer_name": farmer_name, "amount": amount, "days": days, "level": level})
    return debts


def add_manual_ledger_entry(seller_id, vehicle_number, phone, price_per_kg, region):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO manual_ledger_entries (seller_id, vehicle_number, phone, price_per_kg, kg,
                                            total_sum, paid, region, created_at)
        VALUES (?, ?, ?, ?, NULL, NULL, 0, ?, ?)
    """, (seller_id, vehicle_number, phone, price_per_kg, region,
          datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    entry_id = cur.lastrowid
    conn.close()
    return entry_id


def confirm_manual_payment(entry_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE manual_ledger_entries SET paid = 1 WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def get_active_driver_listings():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, driver_id, product_name, unit, quantity, sell_price, region, pickup_address, package_type, photo_file_id
        FROM driver_listings WHERE status = 'faol' AND quantity > 0
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_listings_for_comparison(product_name=None):
    """Xaridor uchun: barcha faol haydovchi e'lonlari, eng arzonidan boshlab — rasm, narx, manzil bilan"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if product_name:
        cur.execute("""
            SELECT dl.id, dl.product_name, dl.unit, dl.quantity, dl.sell_price, dl.region,
                   dl.pickup_address, dl.photo_file_id, d.full_name, d.phone, d.vehicle_number
            FROM driver_listings dl
            JOIN drivers d ON d.id = dl.driver_id
            WHERE dl.status = 'faol' AND dl.quantity > 0 AND dl.product_name = ?
            ORDER BY dl.sell_price ASC
        """, (product_name,))
    else:
        cur.execute("""
            SELECT dl.id, dl.product_name, dl.unit, dl.quantity, dl.sell_price, dl.region,
                   dl.pickup_address, dl.photo_file_id, d.full_name, d.phone, d.vehicle_number
            FROM driver_listings dl
            JOIN drivers d ON d.id = dl.driver_id
            WHERE dl.status = 'faol' AND dl.quantity > 0
            ORDER BY dl.sell_price ASC
        """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_driver_listing_by_id(listing_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT dl.id, dl.driver_id, dl.seller_id, dl.product_name, dl.unit, dl.quantity,
               dl.estimated_quantity, dl.actual_weight, dl.weight_status,
               dl.base_price, dl.sell_price, dl.region, dl.pickup_address, dl.status,
               d.telegram_id, d.full_name, s.telegram_id, s.shop_name,
               dl.farmer_payment, dl.payment_confirmed, d.vehicle_number, dl.package_type,
               dl.weight_photo_file_id
        FROM driver_listings dl
        JOIN drivers d ON d.id = dl.driver_id
        JOIN sellers s ON s.id = dl.seller_id
        WHERE dl.id = ?
    """, (listing_id,))
    row = cur.fetchone()
    conn.close()
    return row


def set_listing_weight(listing_id, actual_weight, weight_photo_file_id=None):
    """Haydovchi tarozida tortgan haqiqiy og'irlikni (va cheki rasmini) kiritadi (fermer tasdiqlashini kutadi)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE driver_listings SET actual_weight = ?, weight_status = 'kutilmoqda', weight_photo_file_id = ? WHERE id = ?",
        (actual_weight, weight_photo_file_id, listing_id)
    )
    conn.commit()
    conn.close()


def set_weight_photo_only(listing_id, weight_photo_file_id):
    """Haydovchi raqam kiritmasdan, faqat yuk/tarozi rasmini yuboradi — fermer rasmga qarab
    o'zi miqdorni kiritadi (farmer_set_weight orqali)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE driver_listings SET weight_photo_file_id = ? WHERE id = ?",
        (weight_photo_file_id, listing_id)
    )
    conn.commit()
    conn.close()


def confirm_listing_weight(listing_id, confirmed):
    """Fermer tarozi natijasini tasdiqlaydi yoki rad etadi.
    Tasdiqlansa, to'lov ham HAQIQIY og'irlikka qarab qayta hisoblanadi (dastlabki taxmin emas)."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if confirmed:
        cur.execute("SELECT actual_weight, base_price, payment_confirmed FROM driver_listings WHERE id = ?", (listing_id,))
        row = cur.fetchone()
        actual_weight = row[0] if row else None
        base_price = row[1] if row else None
        already_paid = row[2] if row else 0

        new_farmer_payment = round(base_price * actual_weight) if (base_price and actual_weight) else None

        if new_farmer_payment is not None and not already_paid:
            cur.execute(
                "UPDATE driver_listings SET weight_status = 'tasdiqlangan', quantity = ?, "
                "farmer_payment = ? WHERE id = ?",
                (actual_weight, new_farmer_payment, listing_id)
            )
        else:
            # To'lov allaqachon tasdiqlangan bo'lsa, summani orqaga o'zgartirmaymiz — faqat miqdorni yangilaymiz
            cur.execute(
                "UPDATE driver_listings SET weight_status = 'tasdiqlangan', quantity = ? WHERE id = ?",
                (actual_weight, listing_id)
            )
    else:
        cur.execute("UPDATE driver_listings SET weight_status = 'bahsli' WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()


def farmer_set_weight(listing_id, weight, custom_price=None):
    """Fermer haydovchi telefon/rasm orqali aytgan miqdorni (va kerak bo'lsa, shu yetkazma uchun
    alohida narxni) to'g'ridan-to'g'ri o'zi kiritadi. Darhol tasdiqlangan hisoblanadi va to'lov qayta hisoblanadi."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT base_price, payment_confirmed FROM driver_listings WHERE id = ?", (listing_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    base_price, already_paid = row

    price_to_use = custom_price if custom_price is not None else base_price
    new_farmer_payment = round(price_to_use * weight) if price_to_use else None

    if new_farmer_payment is not None and not already_paid:
        cur.execute(
            "UPDATE driver_listings SET actual_weight = ?, quantity = ?, weight_status = 'tasdiqlangan', "
            "farmer_payment = ?, base_price = ? WHERE id = ?",
            (weight, weight, new_farmer_payment, price_to_use, listing_id)
        )
    else:
        cur.execute(
            "UPDATE driver_listings SET actual_weight = ?, quantity = ?, weight_status = 'tasdiqlangan' WHERE id = ?",
            (weight, weight, listing_id)
        )
    conn.commit()
    conn.close()
    return new_farmer_payment


def get_unweighed_listings_for_seller(seller_id):
    """Fermerning hali og'irligi kiritilmagan (haydovchi ham, fermer ham) barcha yuklarini qaytaradi"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT dl.id, dl.product_name, dl.unit, dl.estimated_quantity, d.full_name, d.vehicle_number, d.phone,
               dl.weight_photo_file_id
        FROM driver_listings dl
        JOIN drivers d ON d.id = dl.driver_id
        WHERE dl.seller_id = ? AND dl.actual_weight IS NULL AND dl.weight_status = 'kutilmoqda'
        ORDER BY dl.id DESC
    """, (seller_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def reduce_driver_listing_quantity(listing_id, sold_qty):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT quantity FROM driver_listings WHERE id = ?", (listing_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return
    new_qty = max(0, row[0] - sold_qty)
    status = "tugagan" if new_qty <= 0 else "faol"
    cur.execute(
        "UPDATE driver_listings SET quantity = ?, status = ? WHERE id = ?",
        (new_qty, status, listing_id)
    )
    conn.commit()
    conn.close()


def get_driver_listings_for_driver(driver_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, product_name, unit, quantity, sell_price, region, status,
               estimated_quantity, actual_weight, weight_status, package_type, weight_photo_file_id
        FROM driver_listings WHERE driver_id = ? ORDER BY id DESC
    """, (driver_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_seller_orders(seller_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, full_name, phone, product_name, quantity, unit,
               total_price, region, address, status, created_at
        FROM orders WHERE seller_id = ? ORDER BY id DESC LIMIT 20
    """, (seller_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ----------------- Foydalanuvchilar / Referal tizimi -----------------

def get_or_create_user(telegram_id, referred_by=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, referred_by, discount_percent, referral_rewarded FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row

    cur.execute("""
        INSERT INTO users (telegram_id, referred_by, discount_percent, referral_rewarded, created_at)
        VALUES (?, ?, 0, 0, ?)
    """, (telegram_id, referred_by, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    cur.execute("SELECT telegram_id, referred_by, discount_percent, referral_rewarded FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_user(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, referred_by, discount_percent, referral_rewarded FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row


def add_user_discount(telegram_id, percent):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET discount_percent = discount_percent + ? WHERE telegram_id = ?",
        (percent, telegram_id)
    )
    conn.commit()
    conn.close()


def clear_user_discount(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET discount_percent = 0 WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()


def mark_referral_rewarded(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET referral_rewarded = 1 WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()


def count_referrals(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (telegram_id,))
    count = cur.fetchone()[0]
    conn.close()
    return count


def has_completed_order(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (telegram_id,))
    count = cur.fetchone()[0]
    conn.close()
    return count > 0


# ----------------- Haydovchilar (drivers) -----------------

def register_driver(telegram_id, full_name, phone, vehicle_type, vehicle_number, capacity_tons, region):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO drivers (telegram_id, full_name, phone, vehicle_type, vehicle_number, capacity_tons, region, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'tasdiqlangan', ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            full_name=excluded.full_name, phone=excluded.phone,
            vehicle_type=excluded.vehicle_type, vehicle_number=excluded.vehicle_number,
            capacity_tons=excluded.capacity_tons,
            region=excluded.region, status='tasdiqlangan'
    """, (telegram_id, full_name, phone, vehicle_type, vehicle_number, capacity_tons, region,
          datetime.now().strftime("%Y-%m-%d %H:%M")))
    driver_id = cur.lastrowid
    conn.commit()
    conn.close()
    return driver_id


def get_driver_by_telegram_id(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, telegram_id, full_name, phone, vehicle_type, capacity_tons, region, status, vehicle_number
        FROM drivers WHERE telegram_id = ?
    """, (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_driver_by_id(driver_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, telegram_id, full_name, phone, vehicle_type, capacity_tons, region, status, vehicle_number
        FROM drivers WHERE id = ?
    """, (driver_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_pending_drivers():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, telegram_id, full_name, phone, vehicle_type, capacity_tons, region, vehicle_number
        FROM drivers WHERE status = 'kutilmoqda'
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_approved_drivers():
    """Barcha tasdiqlangan haydovchilarning telegram_id larini qaytaradi — yangi elon haqida
    xabar yuborish uchun"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM drivers WHERE status = 'tasdiqlangan'")
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]


def haversine_km(lat1, lon1, lat2, lon2):
    """Ikki koordinata orasidagi masofani km hisobida hisoblaydi (Yer sharining egriligini hisobga olib)"""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def update_driver_location(driver_id, latitude, longitude):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE drivers SET latitude = ?, longitude = ? WHERE id = ?", (latitude, longitude, driver_id))
    conn.commit()
    conn.close()


def get_drivers_near(latitude, longitude, max_km=30):
    """Berilgan koordinatadan max_km radiusidagi tasdiqlangan haydovchilarning telegram_id larini qaytaradi.
    Joylashuvini bermagan haydovchilar bu ro'yxatga kirmaydi."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT telegram_id, latitude, longitude FROM drivers
        WHERE status = 'tasdiqlangan' AND latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    rows = cur.fetchall()
    conn.close()

    nearby = []
    for tg_id, drv_lat, drv_lon in rows:
        try:
            dist = haversine_km(latitude, longitude, drv_lat, drv_lon)
            if dist <= max_km:
                nearby.append(tg_id)
        except (TypeError, ValueError):
            continue
    return nearby


def get_drivers_by_regions(regions):
    """Berilgan hududlar (viloyatlar) ro'yxatidagi tasdiqlangan haydovchilarning telegram_id larini qaytaradi —
    joylashuv (koordinata) berilmagan hollarda hudud bo'yicha zaxira filtri sifatida ishlatiladi."""
    if not regions:
        return []
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in regions)
    cur.execute(f"""
        SELECT telegram_id FROM drivers
        WHERE status = 'tasdiqlangan' AND region IN ({placeholders})
    """, regions)
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]


def update_driver_tuman(driver_id, tuman):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE drivers SET tuman = ? WHERE id = ?", (tuman, driver_id))
    conn.commit()
    conn.close()


def get_drivers_by_tumans(tumans):
    """Berilgan tumanlar ro'yxatidagi tasdiqlangan haydovchilarning telegram_id larini qaytaradi —
    e'lon beruvchi aniq qo'shni tumanlarni o'zi tanlaganda ishlatiladi."""
    if not tumans:
        return []
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in tumans)
    cur.execute(f"""
        SELECT telegram_id FROM drivers
        WHERE status = 'tasdiqlangan' AND tuman IN ({placeholders})
    """, tumans)
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]


def set_driver_status(driver_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE drivers SET status = ? WHERE id = ?", (status, driver_id))
    conn.commit()
    conn.close()


def find_available_drivers(region, min_capacity):
    """Shu hududda ishlaydigan va yukni ko'tara oladigan tasdiqlangan haydovchilarni topish"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, telegram_id, full_name, phone, vehicle_type, capacity_tons
        FROM drivers
        WHERE status = 'tasdiqlangan' AND region = ? AND capacity_tons >= ?
    """, (region, min_capacity))
    rows = cur.fetchall()
    conn.close()
    return rows


def assign_order_driver(order_id, driver_id):
    """Faqat hali haydovchi biriktirilmagan buyurtmaga tayinlaydi (band bo'lib qolmasligi uchun)"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT driver_id FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    if row is None or row[0] is not None:
        conn.close()
        return False
    cur.execute(
        "UPDATE orders SET driver_id = ?, status = 'yetkazishga olindi' WHERE id = ?",
        (driver_id, order_id)
    )
    conn.commit()
    conn.close()
    return True


def get_driver_orders(driver_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, full_name, phone, product_name, quantity, unit,
               total_price, region, address, status, created_at
        FROM orders WHERE driver_id = ? ORDER BY id DESC LIMIT 20
    """, (driver_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ----------------- Kombaynlar -----------------

def register_combine_owner(telegram_id, full_name, phone, region):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO combine_owners (telegram_id, full_name, phone, region, status, created_at)
        VALUES (?, ?, ?, ?, 'tasdiqlangan', ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            full_name=excluded.full_name, phone=excluded.phone,
            region=excluded.region, status='tasdiqlangan'
    """, (telegram_id, full_name, phone, region, datetime.now().strftime("%Y-%m-%d %H:%M")))
    owner_id = cur.lastrowid
    conn.commit()
    conn.close()
    return owner_id


def get_combine_owner_by_telegram_id(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, telegram_id, full_name, phone, region, status
        FROM combine_owners WHERE telegram_id = ?
    """, (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_combine_owner_by_id(owner_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, telegram_id, full_name, phone, region, status
        FROM combine_owners WHERE id = ?
    """, (owner_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_pending_combine_owners():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, telegram_id, full_name, phone, region
        FROM combine_owners WHERE status = 'kutilmoqda'
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def set_combine_owner_status(owner_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE combine_owners SET status = ? WHERE id = ?", (status, owner_id))
    conn.commit()
    conn.close()


def add_combine_listing(owner_id, model, price_per_gektar, address, region, photo_file_id=None, coverage="vodiy"):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO combine_listings (owner_id, model, price_per_gektar, photo_file_id, address, region, active, created_at, coverage)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (owner_id, model, price_per_gektar, photo_file_id, address, region,
          datetime.now().strftime("%Y-%m-%d %H:%M"), coverage))
    conn.commit()
    listing_id = cur.lastrowid
    conn.close()
    return listing_id


def get_active_combine_listings(region=None):
    """Fermerlar uchun: barcha faol kombayn e'lonlari, eng arzonidan boshlab.
    Respublika bo'ylab xizmat ko'rsatuvchilar barcha hududlarda ko'rinadi,
    vodiy bo'ylab xizmat ko'rsatuvchilar esa faqat oz region so'ralganda yoki umumiy royxatda ko'rinadi."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if region:
        cur.execute("""
            SELECT cl.id, cl.model, cl.price_per_gektar, cl.photo_file_id, cl.address, cl.region,
                   co.full_name, co.phone, cl.coverage
            FROM combine_listings cl
            JOIN combine_owners co ON co.id = cl.owner_id
            WHERE cl.active = 1 AND co.status = 'tasdiqlangan'
                  AND (cl.region = ? OR cl.coverage = 'respublika')
            ORDER BY cl.price_per_gektar ASC
        """, (region,))
    else:
        cur.execute("""
            SELECT cl.id, cl.model, cl.price_per_gektar, cl.photo_file_id, cl.address, cl.region,
                   co.full_name, co.phone, cl.coverage
            FROM combine_listings cl
            JOIN combine_owners co ON co.id = cl.owner_id
            WHERE cl.active = 1 AND co.status = 'tasdiqlangan'
            ORDER BY cl.price_per_gektar ASC
        """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_combine_listing_by_id(listing_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT cl.id, cl.owner_id, cl.model, cl.price_per_gektar, cl.photo_file_id, cl.address,
               cl.region, cl.active, cl.coverage, co.telegram_id, co.full_name, co.phone
        FROM combine_listings cl
        JOIN combine_owners co ON co.id = cl.owner_id
        WHERE cl.id = ?
    """, (listing_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_combine_listings_for_owner(owner_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, model, price_per_gektar, photo_file_id, address, region, active, coverage
        FROM combine_listings WHERE owner_id = ? ORDER BY id DESC
    """, (owner_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ----------------- Kombayn egasi silos elonlari (o'rilayotgan silosni sotish) -----------------

def add_combine_silos_listing(owner_id, price_per_kg, quantity_available, address, region, photo_file_id=None, latitude=None, longitude=None, description=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO combine_silos_listings (owner_id, price_per_kg, quantity_available, photo_file_id,
                                             address, region, latitude, longitude, active, created_at, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (owner_id, price_per_kg, quantity_available, photo_file_id, address, region, latitude, longitude,
          datetime.now().strftime("%Y-%m-%d %H:%M"), description))
    conn.commit()
    listing_id = cur.lastrowid
    conn.close()
    return listing_id


def get_active_combine_silos_listings(region=None):
    """Mijozlar uchun: barcha faol kombayn-silos elonlari, eng arzonidan boshlab.
    Agar `region` berilsa, faqat shu viloyatdagi elonlar qaytariladi."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if region:
        cur.execute("""
            SELECT csl.id, csl.price_per_kg, csl.quantity_available, csl.photo_file_id,
                   csl.address, csl.region, co.id, co.full_name, co.phone, csl.description
            FROM combine_silos_listings csl
            JOIN combine_owners co ON co.id = csl.owner_id
            WHERE csl.active = 1 AND co.status = 'tasdiqlangan' AND csl.region = ?
                  AND (csl.quantity_available IS NULL OR csl.quantity_available > 0)
            ORDER BY csl.price_per_kg ASC
        """, (region,))
    else:
        cur.execute("""
            SELECT csl.id, csl.price_per_kg, csl.quantity_available, csl.photo_file_id,
                   csl.address, csl.region, co.id, co.full_name, co.phone, csl.description
            FROM combine_silos_listings csl
            JOIN combine_owners co ON co.id = csl.owner_id
            WHERE csl.active = 1 AND co.status = 'tasdiqlangan'
                  AND (csl.quantity_available IS NULL OR csl.quantity_available > 0)
            ORDER BY csl.price_per_kg ASC
        """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_combine_silos_listing_by_id(listing_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT csl.id, csl.owner_id, csl.price_per_kg, csl.quantity_available, csl.photo_file_id,
               csl.address, csl.region, csl.active, co.telegram_id, co.full_name, co.phone
        FROM combine_silos_listings csl
        JOIN combine_owners co ON co.id = csl.owner_id
        WHERE csl.id = ?
    """, (listing_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_combine_silos_listings_for_owner(owner_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, price_per_kg, quantity_available, photo_file_id, address, region, active
        FROM combine_silos_listings WHERE owner_id = ? ORDER BY id DESC
    """, (owner_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def reduce_combine_silos_quantity(listing_id, sold_qty):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT quantity_available FROM combine_silos_listings WHERE id = ?", (listing_id,))
    row = cur.fetchone()
    if not row or row[0] is None:
        conn.close()
        return
    new_qty = max(0, row[0] - sold_qty)
    status = 0 if new_qty <= 0 else 1
    cur.execute(
        "UPDATE combine_silos_listings SET quantity_available = ?, active = ? WHERE id = ?",
        (new_qty, status, listing_id)
    )
    conn.commit()
    conn.close()


# ----------------- Haydovchi o'z silosini sotish elonlari ("Mashinada sotiladi") -----------------

def add_driver_silos_listing(driver_id, price_per_kg, quantity_available, address, region, photo_file_id=None, description=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO driver_silos_listings (driver_id, price_per_kg, quantity_available, photo_file_id,
                                            address, region, active, created_at, description)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (driver_id, price_per_kg, quantity_available, photo_file_id, address, region,
          datetime.now().strftime("%Y-%m-%d %H:%M"), description))
    conn.commit()
    listing_id = cur.lastrowid
    conn.close()
    return listing_id


def get_active_driver_silos_listings(region=None):
    """Mijozlar uchun: barcha faol haydovchi-silos elonlari, eng arzonidan boshlab.
    Qora ro'yxatdagi (5+ kun to'lanmagan qarzi bor) haydovchilarning elonlari bu ro'yxatga kirmaydi.
    Agar `region` berilsa, faqat shu viloyatdagi elonlar qaytariladi."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if region:
        cur.execute("""
            SELECT dsl.id, dsl.driver_id, dsl.price_per_kg, dsl.quantity_available, dsl.photo_file_id,
                   dsl.address, dsl.region, d.full_name, d.phone, d.vehicle_number, dsl.description
            FROM driver_silos_listings dsl
            JOIN drivers d ON d.id = dsl.driver_id
            WHERE dsl.active = 1 AND d.status = 'tasdiqlangan' AND dsl.region = ?
                  AND (dsl.quantity_available IS NULL OR dsl.quantity_available > 0)
            ORDER BY dsl.price_per_kg ASC
        """, (region,))
    else:
        cur.execute("""
            SELECT dsl.id, dsl.driver_id, dsl.price_per_kg, dsl.quantity_available, dsl.photo_file_id,
                   dsl.address, dsl.region, d.full_name, d.phone, d.vehicle_number, dsl.description
            FROM driver_silos_listings dsl
            JOIN drivers d ON d.id = dsl.driver_id
            WHERE dsl.active = 1 AND d.status = 'tasdiqlangan'
                  AND (dsl.quantity_available IS NULL OR dsl.quantity_available > 0)
            ORDER BY dsl.price_per_kg ASC
        """)
    rows = cur.fetchall()
    conn.close()

    # Qora ro'yxatdagi (5+ kun qarzdor) haydovchilarni FAQAT shu viloyat ichida chetlab o'tish
    visible = []
    for row in rows:
        driver_id, drow_region = row[1], row[6]
        debts = get_driver_debts(driver_id, region=drow_region)
        if any(d["level"] == "qizil" for d in debts):
            continue
        visible.append(row)
    return visible


def get_driver_silos_listing_by_id(listing_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT dsl.id, dsl.driver_id, dsl.price_per_kg, dsl.quantity_available, dsl.photo_file_id,
               dsl.address, dsl.region, dsl.active, d.telegram_id, d.full_name, d.phone, d.vehicle_number
        FROM driver_silos_listings dsl
        JOIN drivers d ON d.id = dsl.driver_id
        WHERE dsl.id = ?
    """, (listing_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_driver_silos_listings_for_driver(driver_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, price_per_kg, quantity_available, photo_file_id, address, region, active
        FROM driver_silos_listings WHERE driver_id = ? ORDER BY id DESC
    """, (driver_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def reduce_driver_silos_quantity(listing_id, sold_qty):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT quantity_available FROM driver_silos_listings WHERE id = ?", (listing_id,))
    row = cur.fetchone()
    if not row or row[0] is None:
        conn.close()
        return
    new_qty = max(0, row[0] - sold_qty)
    status = 0 if new_qty <= 0 else 1
    cur.execute(
        "UPDATE driver_silos_listings SET quantity_available = ?, active = ? WHERE id = ?",
        (new_qty, status, listing_id)
    )
    conn.commit()
    conn.close()


# ----------------- E'lonlarni o'chirish (egasi yoki admin) va avtomatik tozalash -----------------

def deactivate_seller_product(sp_id):
    """Fermer/sotuvchi mahsulot e'lonini o'chiradi — tarixiy hisobot buzilmasligi uchun
    qator o'chirilmaydi, faqat quantity_available = 0 qilinadi (browse'da ko'rinmay qoladi)."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE seller_products SET quantity_available = 0 WHERE id = ?", (sp_id,))
    conn.commit()
    conn.close()


def deactivate_driver_silos_listing(listing_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE driver_silos_listings SET active = 0 WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()


def deactivate_combine_listing(listing_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE combine_listings SET active = 0 WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()


def deactivate_combine_silos_listing(listing_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE combine_silos_listings SET active = 0 WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()


def cleanup_old_listings(days=2):
    """2 kundan eski, hali faol/band qilinmagan e'lonlarni avtomatik o'chiradi (deaktivatsiya qiladi).
    Tarixi bor (band qilingan/sotilgan) yozuvlarga tegilmaydi — faqat hali ochiq turgan e'lonlar."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")

    cur.execute("""
        UPDATE seller_products SET quantity_available = 0
        WHERE claimed = 0 AND quantity_available > 0 AND created_at IS NOT NULL AND created_at < ?
    """, (cutoff,))
    sp_count = cur.rowcount

    cur.execute("""
        UPDATE driver_silos_listings SET active = 0
        WHERE active = 1 AND created_at IS NOT NULL AND created_at < ?
    """, (cutoff,))
    ds_count = cur.rowcount

    cur.execute("""
        UPDATE combine_listings SET active = 0
        WHERE active = 1 AND created_at IS NOT NULL AND created_at < ?
    """, (cutoff,))
    cl_count = cur.rowcount

    cur.execute("""
        UPDATE combine_silos_listings SET active = 0
        WHERE active = 1 AND created_at IS NOT NULL AND created_at < ?
    """, (cutoff,))
    csl_count = cur.rowcount

    conn.commit()
    conn.close()
    return {"seller_products": sp_count, "driver_silos": ds_count, "combine_tech": cl_count, "combine_silos": csl_count}
