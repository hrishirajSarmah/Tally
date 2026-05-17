"""Idempotent seed: 3 demo users, 1 active cycle, 6 thrust areas.

Usage (from api/):
    uv run python seed.py

Safe to re-run — looks up by unique key, inserts only when missing.
"""

from datetime import date

from sqlmodel import Session, select

from db import engine
from models import Cycle, CyclePhase, Role, ThrustArea, User
from security import hash_password


THRUST_AREAS: list[str] = [
    "Customer Success",
    "Product Delivery",
    "Operational Excellence",
    "People Development",
    "Innovation",
    "Compliance",
]


CYCLE: dict = {
    "name": "FY26",
    "goal_setting_opens": date(2026, 4, 1),
    "q1_opens": date(2026, 7, 1),
    "q2_opens": date(2026, 10, 1),
    "q3_opens": date(2027, 1, 1),
    "q4_opens": date(2027, 4, 1),
    "current_phase": CyclePhase.goal_setting,
    "is_active": True,
}


USERS_BASE: list[dict] = [
    {
        "email": "admin@demo",
        "name": "Admin User",
        "role": Role.admin,
        "department": "HR",
        "password": "demo",
        "manager_email": None,
    },
    {
        "email": "manager@demo",
        "name": "Manager User",
        "role": Role.manager,
        "department": "Engineering",
        "password": "demo",
        "manager_email": None,
    },
    {
        "email": "employee@demo",
        "name": "Employee User",
        "role": Role.employee,
        "department": "Engineering",
        "password": "demo",
        "manager_email": "manager@demo",
    },
]


def seed_thrust_areas(session: Session) -> dict[str, int]:
    inserted = 0
    skipped = 0
    for name in THRUST_AREAS:
        existing = session.exec(
            select(ThrustArea).where(ThrustArea.name == name)
        ).first()
        if existing:
            skipped += 1
            continue
        session.add(ThrustArea(name=name))
        inserted += 1
    return {"inserted": inserted, "skipped": skipped}


def seed_cycle(session: Session) -> dict[str, object]:
    existing = session.exec(select(Cycle).where(Cycle.name == CYCLE["name"])).first()
    if existing is not None:
        existing.is_active = True
        existing.current_phase = CYCLE["current_phase"]
        session.add(existing)
        return {"action": "updated", "name": existing.name, "phase": existing.current_phase.value}
    cycle = Cycle(**CYCLE)
    session.add(cycle)
    return {"action": "inserted", "name": cycle.name, "phase": cycle.current_phase.value}


def seed_users(session: Session) -> dict[str, int]:
    inserted = 0
    skipped = 0
    by_email: dict[str, User] = {}

    for u in USERS_BASE:
        existing = session.exec(select(User).where(User.email == u["email"])).first()
        if existing is not None:
            by_email[u["email"]] = existing
            skipped += 1
            continue
        user = User(
            email=u["email"],
            name=u["name"],
            password_hash=hash_password(u["password"]),
            role=u["role"],
            department=u["department"],
            manager_id=None,
        )
        session.add(user)
        session.flush()
        by_email[u["email"]] = user
        inserted += 1

    for u in USERS_BASE:
        if u["manager_email"] is None:
            continue
        user = by_email[u["email"]]
        manager = by_email[u["manager_email"]]
        if user.manager_id != manager.id:
            user.manager_id = manager.id
            session.add(user)

    return {"inserted": inserted, "skipped": skipped}


def main() -> None:
    print("=== Seeding Tally demo data ===")
    with Session(engine) as session:
        ta = seed_thrust_areas(session)
        print(f"thrust_areas: {ta}")
        cy = seed_cycle(session)
        print(f"cycle:        {cy}")
        us = seed_users(session)
        print(f"users:        {us}")
        session.commit()
    print("=== Done ===")


if __name__ == "__main__":
    main()
