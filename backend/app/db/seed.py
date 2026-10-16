"""Deterministic synthetic e-commerce dataset generator (seed=42) for QueryPilot."""

from __future__ import annotations

import random
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.db.engine import ensure_readonly_role, get_admin_engine
from app.db.models import (
    Category,
    Customer,
    Order,
    OrderItem,
    Payment,
    Product,
    WarehouseBase,
    WebsiteEvent,
)

SEED_VALUE = 42

CATEGORIES_SPEC = [
    (1, "Electronics", "Technology", Decimal("38.50")),
    (2, "Home & Office", "Home", Decimal("44.00")),
    (3, "Sports & Outdoors", "Lifestyle", Decimal("41.00")),
    (4, "Apparel & Footwear", "Lifestyle", Decimal("52.00")),
    (5, "Kitchen & Dining", "Home", Decimal("46.50")),
    (6, "Beauty & Personal Care", "Lifestyle", Decimal("58.00")),
    (7, "Accessories", "Technology", Decimal("60.00")),
    (8, "Books & Media", "Media", Decimal("35.00")),
]

# (sku, name, category_id, brand, unit_cost, unit_price, trend_profile)
# trend_profile: "declining" | "growing" | "stable"
PRODUCTS_SPEC = [
    # Electronics (cat 1)
    ("ELEC-001", "UltraWide 34-inch Curved Monitor", 1, "NovaDisplay", "290.00", "549.00", "growing"),
    ("ELEC-002", "Legacy 4K Webcam Pro", 1, "OptiCam", "65.00", "149.00", "declining"),
    ("ELEC-003", "ANC Wireless Headphones X9", 1, "SonicWave", "110.00", "249.00", "stable"),
    ("ELEC-004", "Thunderbolt 4 Pro Dock", 1, "HyperLink", "95.00", "219.00", "growing"),
    ("ELEC-005", "Wired Studio Headset Gen1", 1, "SonicWave", "48.00", "119.00", "declining"),
    ("ELEC-006", "Portable NVMe SSD 2TB", 1, "FlashCore", "85.00", "179.00", "stable"),
    # Home & Office (cat 2)
    ("HOME-001", "ErgoMesh Executive Chair", 2, "WorkWell", "180.00", "399.00", "growing"),
    ("HOME-002", "Dual-Motor Standing Desk 60in", 2, "WorkWell", "240.00", "499.00", "stable"),
    ("HOME-003", "Cordless Ergo Mouse V1", 2, "KeyCraft", "28.00", "79.00", "declining"),
    ("HOME-004", "LED Architect Desk Lamp", 2, "LumaHome", "32.00", "89.00", "stable"),
    ("HOME-005", "Acoustic Felt Desk Partition", 2, "WorkWell", "45.00", "115.00", "growing"),
    # Sports & Outdoors (cat 3)
    ("SPRT-001", "Smart Fitness Band Gen1", 3, "PulseTrack", "42.00", "109.00", "declining"),
    ("SPRT-002", "Carbon Trail Running Poles", 3, "SummitGear", "55.00", "135.00", "growing"),
    ("SPRT-003", "Insulated Hydration Pack 20L", 3, "SummitGear", "38.00", "95.00", "stable"),
    ("SPRT-004", "Adjustable Dumbbell Pair 50lb", 3, "IronCore", "125.00", "269.00", "stable"),
    # Apparel & Footwear (cat 4)
    ("APPR-001", "Classic Wool Runner", 4, "StrideLab", "45.00", "118.00", "declining"),
    ("APPR-002", "All-Weather Commuter Jacket", 4, "NorthCrest", "68.00", "165.00", "growing"),
    ("APPR-003", "Merino Base Layer Crew", 4, "NorthCrest", "30.00", "78.00", "stable"),
    ("APPR-004", "Performance Stretch Chino", 4, "StrideLab", "34.00", "88.00", "stable"),
    # Kitchen & Dining (cat 5)
    ("KITC-001", "Precision Pour-Over Kettle", 5, "BrewMaster", "40.00", "99.00", "growing"),
    ("KITC-002", "Conical Burr Coffee Grinder", 5, "BrewMaster", "62.00", "149.00", "stable"),
    ("KITC-003", "Tri-Ply Stainless Skillet 12in", 5, "ChefForge", "52.00", "129.00", "stable"),
    ("KITC-004", "Compact Countertop Blender V1", 5, "ChefForge", "35.00", "85.00", "declining"),
    # Beauty & Personal Care (cat 6)
    ("BEAU-001", "Botanical Facial Serum Set", 6, "PureGlow", "22.00", "64.00", "growing"),
    ("BEAU-002", "Ionic Travel Hair Dryer", 6, "PureGlow", "38.00", "98.00", "stable"),
    ("BEAU-003", "Mineral Daily SPF50 Duo", 6, "PureGlow", "16.00", "46.00", "stable"),
    # Accessories (cat 7)
    ("ACCS-001", "GaN 100W Fast Charger", 7, "HyperLink", "20.00", "59.00", "growing"),
    ("ACCS-002", "MagSafe Leather Laptop Sleeve", 7, "KeyCraft", "24.00", "69.00", "stable"),
    ("ACCS-003", "Mechanical Keycap Set PBT", 7, "KeyCraft", "18.00", "49.00", "stable"),
    # Books & Media (cat 8)
    ("BOOK-001", "Designing Data-Intensive Systems", 8, "TechPress", "22.00", "54.00", "stable"),
    ("BOOK-002", "Analytics Engineering Handbook", 8, "TechPress", "19.00", "45.00", "growing"),
    ("BOOK-003", "Product Strategy Field Guide", 8, "TechPress", "15.00", "36.00", "stable"),
]

REGIONS_COUNTRIES = {
    "North America": ["United States", "Canada"],
    "Europe": ["United Kingdom", "Germany", "France", "Netherlands"],
    "APAC": ["Japan", "Australia", "Singapore", "India"],
    "LATAM": ["Brazil", "Mexico", "Colombia", "Chile"],
}

SEGMENTS_CONFIG = {
    # segment: (weight, min_items, max_items, qty_choices, tier_choices, prefer_expensive)
    "Enterprise": (0.14, 2, 4, [2, 3, 4, 5], ["Platinum", "Gold"], True),
    "VIP": (0.18, 2, 3, [1, 2, 3], ["Platinum", "Gold"], True),
    "SMB": (0.28, 1, 3, [1, 2, 2], ["Gold", "Silver"], False),
    "Consumer": (0.40, 1, 2, [1, 1, 2], ["Silver", "Standard"], False),
}

# 12 months: 2025-10 through 2026-09
# Notice 2026-08 is peak (310 orders) and 2026-09 drops to 235 orders (deliberate MoM revenue decrease)
MONTHLY_ORDER_VOLUMES = [
    (2025, 10, 195),
    (2025, 11, 230),
    (2025, 12, 265),
    (2026, 1, 210),
    (2026, 2, 220),
    (2026, 3, 240),
    (2026, 4, 255),
    (2026, 5, 270),
    (2026, 6, 285),
    (2026, 7, 295),
    (2026, 8, 320),
    (2026, 9, 235),  # Deliberate drop in September 2026 vs August 2026
]

REGION_CANCELLATION_RATES = {
    "LATAM": 0.21,          # Highest cancellation rate (~21%)
    "APAC": 0.11,           # Second highest (~11%)
    "Europe": 0.08,         # Moderate (~8%)
    "North America": 0.045, # Lowest (~4.5%)
}

CANCELLATION_REASONS_BY_REGION = {
    "LATAM": ["payment_declined", "shipping_delay", "payment_declined", "customs_hold"],
    "APAC": ["shipping_delay", "payment_declined", "customer_changed_mind"],
    "Europe": ["customer_changed_mind", "shipping_delay", "out_of_stock"],
    "North America": ["customer_changed_mind", "out_of_stock", "fraud_check"],
}


def seed_warehouse(engine: Optional[Engine] = None, force: bool = False) -> Dict[str, int]:
    """
    Create warehouse tables, seed deterministic e-commerce data if empty (or if force=True),
    and apply PostgreSQL read-only role permissions.
    """
    admin_engine = engine or get_admin_engine()
    WarehouseBase.metadata.create_all(admin_engine)

    with Session(admin_engine) as session:
        existing_orders = session.scalar(select(func.count()).select_from(Order)) or 0
        if existing_orders > 0 and not force:
            ensure_readonly_role(admin_engine)
            return get_table_counts(admin_engine)

        if force and existing_orders > 0:
            for tbl in reversed(WarehouseBase.metadata.sorted_tables):
                session.execute(tbl.delete())
            session.commit()

        rng = random.Random(SEED_VALUE)
        base_created = datetime(2025, 1, 1, 9, 0, 0)

        # 1. Seed Categories
        categories: List[Category] = []
        for cid, name, dept, margin in CATEGORIES_SPEC:
            categories.append(
                Category(
                    category_id=cid,
                    name=name,
                    department=dept,
                    target_margin_pct=margin,
                    created_at=base_created,
                )
            )
        session.add_all(categories)

        # 2. Seed Products
        products: List[Product] = []
        product_meta: Dict[int, Dict[str, Any]] = {}
        for idx, (sku, name, cid, brand, cost_s, price_s, trend) in enumerate(PRODUCTS_SPEC, start=1):
            cost = Decimal(cost_s)
            price = Decimal(price_s)
            prod = Product(
                product_id=idx,
                sku=sku,
                name=name,
                category_id=cid,
                brand=brand,
                unit_cost=cost,
                unit_price=price,
                is_active=True,
                launch_date=date(2025, rng.randint(1, 9), rng.randint(1, 28)),
            )
            products.append(prod)
            product_meta[idx] = {
                "product_id": idx,
                "category_id": cid,
                "unit_cost": cost,
                "unit_price": price,
                "trend": trend,
            }
        session.add_all(products)

        # 3. Seed Customers (450 customers)
        customers: List[Customer] = []
        customer_meta: Dict[int, Dict[str, Any]] = {}
        first_names = [
            "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn",
            "Elena", "Marcus", "Priya", "Liam", "Sofia", "Noah", "Chloe", "Lucas",
            "Amara", "Kenji", "Mateo", "Hannah", "Zoe", "Daniel", "Maya", "Ethan",
        ]
        last_names = [
            "Patel", "Chen", "Silva", "Mueller", "Kim", "Dubois", "Garcia", "Smith",
            "Johnson", "Lee", "Walker", "Rossi", "Sato", "Fernandez", "Novak", "Reyes",
        ]
        region_names = ["North America", "Europe", "APAC", "LATAM"]
        region_weights = [0.42, 0.26, 0.18, 0.14]
        segment_names = list(SEGMENTS_CONFIG.keys())
        segment_weights = [SEGMENTS_CONFIG[s][0] for s in segment_names]

        for cust_id in range(1, 451):
            fname = rng.choice(first_names)
            lname = rng.choice(last_names)
            seg = rng.choices(segment_names, weights=segment_weights, k=1)[0]
            reg = rng.choices(region_names, weights=region_weights, k=1)[0]
            country = rng.choice(REGIONS_COUNTRIES[reg])
            tier = rng.choice(SEGMENTS_CONFIG[seg][4])
            signup_offset = rng.randint(0, 320)
            signup_dt = date(2025, 1, 1) + timedelta(days=signup_offset)
            customers.append(
                Customer(
                    customer_id=cust_id,
                    email=f"{fname.lower()}.{lname.lower()}.{cust_id}@example.com",
                    full_name=f"{fname} {lname}",
                    segment=seg,
                    region=reg,
                    country=country,
                    signup_date=signup_dt,
                    lifetime_tier=tier,
                )
            )
            customer_meta[cust_id] = {
                "customer_id": cust_id,
                "segment": seg,
                "region": reg,
            }
        session.add_all(customers)
        session.flush()

        # 4. Seed Orders, OrderItems, and Payments across 12 months
        orders: List[Order] = []
        order_items: List[OrderItem] = []
        payments: List[Payment] = []

        order_id_seq = 1
        order_item_id_seq = 1
        payment_id_seq = 1

        all_product_ids = list(product_meta.keys())
        high_ticket_ids = [
            pid for pid, m in product_meta.items() if m["unit_price"] >= Decimal("140.00")
        ]

        for month_idx, (year, month, base_volume) in enumerate(MONTHLY_ORDER_VOLUMES):
            is_last_month = (year == 2026 and month == 9)
            days_in_month = 30 if month in (4, 6, 9, 11) else (28 if month == 2 else 31)

            # Weight products for this month so "declining" products drop sharply after month_idx 7 (May 2026)
            prod_weights: List[float] = []
            for pid in all_product_ids:
                p_info = product_meta[pid]
                trend = p_info["trend"]
                cat_id = p_info["category_id"]
                base_w = 2.8 if cat_id in (1, 2) else (1.5 if cat_id in (3, 4, 5) else 1.0)
                if trend == "declining":
                    # Strong early, steep decline in June/July/Aug/Sept 2026
                    if month_idx <= 7:
                        w = base_w * 2.2
                    elif month_idx == 8:
                        w = base_w * 1.3
                    elif month_idx == 9:
                        w = base_w * 0.75
                    elif month_idx == 10:
                        w = base_w * 0.40
                    else:
                        w = base_w * 0.15
                elif trend == "growing":
                    w = base_w * (0.85 + 0.08 * month_idx)
                else:
                    w = base_w
                # In September 2026 (last month), high-ticket Electronics also dip slightly
                if is_last_month and cat_id == 1:
                    w *= 0.72
                prod_weights.append(w)

            for _ in range(base_volume):
                cust_id = rng.randint(1, 450)
                c_info = customer_meta[cust_id]
                seg = c_info["segment"]
                reg = c_info["region"]

                day = rng.randint(1, days_in_month)
                order_dt = date(year, month, day)
                order_ts = datetime.combine(
                    order_dt,
                    time(rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)),
                )

                # Channel distribution: paid_search drops sharply in Sept 2026
                if is_last_month:
                    channels = ["organic", "paid_search", "social", "email", "direct"]
                    ch_weights = [0.38, 0.10, 0.18, 0.19, 0.15]
                else:
                    channels = ["organic", "paid_search", "social", "email", "direct"]
                    ch_weights = [0.28, 0.30, 0.15, 0.15, 0.12]
                channel = rng.choices(channels, weights=ch_weights, k=1)[0]

                # Cancellation rate by region (elevated in Sept 2026 for LATAM/Europe)
                cancel_prob = REGION_CANCELLATION_RATES[reg]
                if is_last_month and reg in ("LATAM", "Europe"):
                    cancel_prob = min(0.32, cancel_prob * 1.45)

                roll = rng.random()
                if roll < cancel_prob:
                    status = "cancelled"
                    cancellation_reason = rng.choice(CANCELLATION_REASONS_BY_REGION[reg])
                elif roll < cancel_prob + 0.035:
                    status = "refunded"
                    cancellation_reason = None
                elif is_last_month and roll > 0.92:
                    status = "processing"
                    cancellation_reason = None
                elif is_last_month and roll > 0.85:
                    status = "shipped"
                    cancellation_reason = None
                else:
                    status = "completed"
                    cancellation_reason = None

                # Build order items according to customer segment so AOV is clearly differentiated
                _, min_items, max_items, qty_choices, _, prefer_expensive = SEGMENTS_CONFIG[seg]
                num_items = rng.randint(min_items, max_items)
                chosen_pids: List[int] = []
                for _item_i in range(num_items):
                    if prefer_expensive and rng.random() < 0.65:
                        pid = rng.choice(high_ticket_ids)
                    else:
                        pid = rng.choices(all_product_ids, weights=prod_weights, k=1)[0]
                    if pid not in chosen_pids:
                        chosen_pids.append(pid)

                subtotal = Decimal("0.00")
                discount_total = Decimal("0.00")

                for pid in chosen_pids:
                    p_info = product_meta[pid]
                    qty = rng.choice(qty_choices)
                    u_price = p_info["unit_price"]
                    u_cost = p_info["unit_cost"]
                    disc_rate = Decimal("0.05") if (seg == "Enterprise" and qty >= 3) else Decimal("0.00")
                    line_disc = (u_price * qty * disc_rate).quantize(Decimal("0.01"))
                    line_tot = (u_price * qty - line_disc).quantize(Decimal("0.01"))

                    subtotal += u_price * qty
                    discount_total += line_disc

                    order_items.append(
                        OrderItem(
                            order_item_id=order_item_id_seq,
                            order_id=order_id_seq,
                            product_id=pid,
                            quantity=qty,
                            unit_price=u_price,
                            unit_cost=u_cost,
                            discount_amount=line_disc,
                            line_total=line_tot,
                        )
                    )
                    order_item_id_seq += 1

                net_merch = subtotal - discount_total
                tax_amt = (net_merch * Decimal("0.08")).quantize(Decimal("0.01"))
                ship_amt = Decimal("0.00") if net_merch >= Decimal("200.00") else Decimal("12.50")
                total_amt = (net_merch + tax_amt + ship_amt).quantize(Decimal("0.01"))

                orders.append(
                    Order(
                        order_id=order_id_seq,
                        customer_id=cust_id,
                        order_date=order_dt,
                        order_timestamp=order_ts,
                        status=status,
                        region=reg,
                        channel=channel,
                        subtotal_amount=subtotal,
                        discount_amount=discount_total,
                        tax_amount=tax_amt,
                        shipping_amount=ship_amt,
                        total_amount=total_amt,
                        cancellation_reason=cancellation_reason,
                    )
                )

                # Payment record
                pay_methods = ["credit_card", "paypal", "wire_transfer", "apple_pay"]
                pay_weights = [0.55, 0.20, 0.15, 0.10] if seg == "Enterprise" else [0.62, 0.22, 0.02, 0.14]
                pay_method = rng.choices(pay_methods, weights=pay_weights, k=1)[0]
                if status == "cancelled":
                    pay_status = "failed" if cancellation_reason == "payment_declined" else "refunded"
                elif status == "refunded":
                    pay_status = "refunded"
                else:
                    pay_status = "captured"
                proc_fee = (total_amt * Decimal("0.029") + Decimal("0.30")).quantize(Decimal("0.01"))

                payments.append(
                    Payment(
                        payment_id=payment_id_seq,
                        order_id=order_id_seq,
                        payment_date=order_ts + timedelta(minutes=rng.randint(1, 15)),
                        payment_method=pay_method,
                        payment_status=pay_status,
                        amount=total_amt,
                        processing_fee=proc_fee,
                    )
                )
                payment_id_seq += 1
                order_id_seq += 1

        session.add_all(orders)
        session.add_all(order_items)
        session.add_all(payments)

        # 5. Seed Website Events (~6,500 events across funnels)
        website_events: List[WebsiteEvent] = []
        event_id_seq = 1
        devices = ["desktop", "mobile", "tablet"]
        device_weights = [0.52, 0.40, 0.08]
        sources = ["organic", "paid_search", "social", "email", "direct"]

        for session_num in range(1, 1801):
            sess_id = f"sess_{session_num:05d}"
            cust_id = rng.randint(1, 450) if rng.random() < 0.75 else None
            reg = customer_meta[cust_id]["region"] if cust_id else rng.choice(region_names)
            dev = rng.choices(devices, weights=device_weights, k=1)[0]
            src = rng.choice(sources)
            pid = rng.choice(all_product_ids)
            ev_ts = datetime(2025, 10, 1, 8, 0, 0) + timedelta(
                days=rng.randint(0, 364),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )

            # Funnel stages
            funnel = ["page_view", "product_view"]
            if rng.random() < 0.48:
                funnel.append("add_to_cart")
                if rng.random() < 0.58:
                    funnel.append("checkout_start")
                    if rng.random() < 0.68:
                        funnel.append("purchase")

            for step_idx, ev_type in enumerate(funnel):
                website_events.append(
                    WebsiteEvent(
                        event_id=event_id_seq,
                        customer_id=cust_id,
                        session_id=sess_id,
                        event_timestamp=ev_ts + timedelta(seconds=step_idx * rng.randint(20, 120)),
                        event_type=ev_type,
                        product_id=pid if ev_type != "page_view" else None,
                        device_type=dev,
                        traffic_source=src,
                        region=reg,
                    )
                )
                event_id_seq += 1

        session.add_all(website_events)
        session.commit()

    # Ensure PostgreSQL read-only role has SELECT privileges on all seeded tables
    ensure_readonly_role(admin_engine)
    if admin_engine.dialect.name == "postgresql":
        with admin_engine.begin() as conn:
            conn.execute(text("ANALYZE;"))

    return get_table_counts(admin_engine)


def get_table_counts(engine: Optional[Engine] = None) -> Dict[str, int]:
    """Return current row counts for all 7 warehouse tables."""
    target_engine = engine or get_admin_engine()
    counts: Dict[str, int] = {}
    with Session(target_engine) as session:
        for model in (Category, Product, Customer, Order, OrderItem, Payment, WebsiteEvent):
            cnt = session.scalar(select(func.count()).select_from(model)) or 0
            counts[model.__tablename__] = int(cnt)
    return counts


if __name__ == "__main__":
    engine = get_admin_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS qp_query_history CASCADE;"))
    from app.db.persistence import init_persistence_db

    init_persistence_db()
    summary = seed_warehouse(force=True)
    print("Emptied PostgreSQL (history, approvals & warehouse) and re-seeded fresh data:", summary)
