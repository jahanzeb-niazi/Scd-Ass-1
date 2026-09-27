"""Idempotent seed: `python -m app.seed`.

Every complaint has a deterministic UUID (uuid5 of its text), and the insert is
ON CONFLICT (id) DO NOTHING — running the seed twice inserts nothing the second
time. Categories/priorities are hand-labelled rather than triaged, so seeding
never spends LLM quota.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.domain import Category, Priority, Status, TriagedBy
from app.logging_config import configure_logging
from app.repositories.complaint_repository import ComplaintRepository, NewComplaint
from app.repositories.database import build_engine, build_session_factory
from app.services.stats_service import STATS_KEY

log = logging.getLogger("civicpulse.seed")

SEED_NAMESPACE = uuid.UUID("6f1c3c1e-5d2a-4d7e-9a53-0c1a1f2e3b4d")
# Fixed anchor so created_at is identical on every run and every machine.
ANCHOR = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)

W, E, S, R, L, OT = (
    Category.WATER,
    Category.ELECTRICITY,
    Category.SANITATION,
    Category.ROADS,
    Category.STREETLIGHTS,
    Category.OTHER,
)
H, N, LO = Priority.HIGH, Priority.NORMAL, Priority.LOW
OP, IP, RS, RJ = Status.OPEN, Status.IN_PROGRESS, Status.RESOLVED, Status.REJECTED

# (text, location, contact, category, priority, status, summary)
SEED: list[tuple[str, str, str | None, Category, Priority, Status, str]] = [
    (
        "Burst water main flooding Street 12 since fajr, water entering ground floors. Please send team jaldi.",
        "Street 12, Block 4, Gulshan-e-Iqbal, Karachi",
        "0300-1234567",
        W,
        H,
        IP,
        "Burst main flooding Street 12, water entering ground floors",
    ),
    (
        "Pani nahi aa raha for 4 days in our lane, tanker mafia charging Rs 5000. Old people and kids suffering.",
        "Lane 3, Orangi Town Sector 11",
        None,
        W,
        H,
        OP,
        "No water supply for 4 days; residents relying on expensive tankers",
    ),
    (
        "Paani ki pipeline leak ho rahi hai near masjid, clean water wasting on road since yesterday.",
        "Near Jamia Masjid, North Nazimabad Block H",
        None,
        W,
        N,
        OP,
        "Water pipeline leaking near mosque since yesterday",
    ),
    (
        "Dirty water coming from taps, smells like gutter. Children getting stomach problems, please test supply.",
        "Korangi Sector 33-A",
        "resident33a@example.com",
        W,
        H,
        IP,
        "Contaminated tap water, suspected sewage mixing; children ill",
    ),
    (
        "Water meter reading is wrong, bill came double this month. Please check.",
        "House 45, PECHS Block 2",
        None,
        W,
        LO,
        RJ,
        "Disputed water bill, meter reading suspected wrong",
    ),
    (
        "Low water pressure in whole block since new connection was given to plaza. Upper floors get nothing.",
        "Block 13-D, Gulshan-e-Iqbal",
        None,
        W,
        N,
        RS,
        "Low water pressure across block after new commercial connection",
    ),
    (
        "Bijli ka taar gir gaya hai on main road near school, sparking ho rahi hai. Bachay wahan se guzarte hain!",
        "Main Road near Government School, Landhi No. 4",
        "0321-7654321",
        E,
        H,
        IP,
        "Live wire fallen near school, sparking; children at risk",
    ),
    (
        "Transformer blasted last night, whole mohalla without bijli for 14 hours in this heat.",
        "Mohalla Qasimabad, Liaquatabad",
        None,
        E,
        H,
        OP,
        "Transformer failure; neighbourhood without power for 14 hours",
    ),
    (
        "Load shedding schedule not being followed, light goes 6 times a day instead of 3.",
        "Malir Cantt area, Karachi",
        None,
        E,
        N,
        OP,
        "Load-shedding exceeding published schedule",
    ),
    (
        "Voltage bahut low hai, fridge and motor burnt. Please check the transformer at corner.",
        "Street 7, Shah Faisal Colony",
        None,
        E,
        N,
        RS,
        "Very low voltage damaging appliances; transformer check requested",
    ),
    (
        "Electric pole is leaning dangerously after rain, might fall on houses.",
        "Street 2, Model Colony, Malir",
        None,
        E,
        H,
        OP,
        "Electric pole leaning dangerously after rain",
    ),
    (
        "Suggestion: please paint the numbers on electricity poles so we can report faults easily.",
        "Defence Phase 5",
        None,
        E,
        LO,
        RJ,
        "Suggestion to number electricity poles for easier reporting",
    ),
    (
        "Gutter overflow on our street for one week, sewage entering homes. Mosquitoes everywhere, dengue dar hai.",
        "Street 9, Baldia Town",
        "0333-2223344",
        S,
        H,
        IP,
        "Week-long sewage overflow entering homes; dengue risk",
    ),
    (
        "Kachra not collected for 10 days, heap near park is huge and smelling badly.",
        "Near Aziz Bhatti Park, Gulshan Block 5",
        None,
        S,
        N,
        OP,
        "Garbage uncollected for 10 days near park",
    ),
    (
        "Manhole cover missing on busy road, a motorcyclist fell last night. Very dangerous at night.",
        "Shahrah-e-Faisal service road near Nursery",
        None,
        S,
        H,
        OP,
        "Open manhole on busy road; motorcyclist injured",
    ),
    (
        "Nala is blocked with plastic, when rain comes whole area will flood again like last year.",
        "Gujjar Nala, near Nazimabad No. 2",
        None,
        S,
        N,
        IP,
        "Storm drain blocked with plastic; flood risk in rain",
    ),
    (
        "Garbage dump is being burnt every evening, smoke is entering houses, asthma patients suffering.",
        "Behind Sabzi Mandi, Scheme 33",
        None,
        S,
        H,
        OP,
        "Garbage burning nightly; smoke affecting residents' health",
    ),
    (
        "Please place a dustbin at the bus stop, people throw wrappers on ground.",
        "Bus stop, University Road",
        None,
        S,
        LO,
        RS,
        "Request for a dustbin at bus stop",
    ),
    (
        "Big pothole on main sarak near Nipa chowrangi, two bikes slipped today. Very deep when filled with water.",
        "NIPA Chowrangi, University Road",
        None,
        R,
        H,
        IP,
        "Deep pothole at NIPA causing motorbike accidents",
    ),
    (
        "Road was dug for gas pipeline 2 months ago and never repaired. Dust everywhere, cars getting damaged.",
        "Street 4, Gulistan-e-Jauhar Block 15",
        None,
        R,
        N,
        OP,
        "Road left dug up for 2 months after pipeline work",
    ),
    (
        "Illegal speed breaker made by shopkeeper is too high, cars hitting bottom. Please remove.",
        "Tariq Road near Dolmen",
        None,
        R,
        N,
        RJ,
        "Unauthorised, too-high speed breaker on Tariq Road",
    ),
    (
        "Footpath broken and tiles missing, elderly people cannot walk safely to the masjid.",
        "Block 7, Federal B Area",
        None,
        R,
        N,
        OP,
        "Broken footpath unsafe for elderly pedestrians",
    ),
    (
        "Traffic signal not working at the crossing since Monday, daily jam and near accidents.",
        "Karsaz / Shahrah-e-Faisal crossing",
        None,
        R,
        H,
        RS,
        "Traffic signal out since Monday; jams and near-accidents",
    ),
    (
        "Road markings faded near school, minor issue but zebra crossing should be repainted.",
        "Main road, Bahadurabad",
        None,
        R,
        LO,
        OP,
        "Faded zebra crossing near school needs repainting",
    ),
    (
        "Streetlights off on whole street for 3 weeks, andhera hai, snatching incidents increased.",
        "Street 15, Gulshan-e-Maymar",
        None,
        L,
        H,
        IP,
        "Street dark for 3 weeks; snatching incidents rising",
    ),
    (
        "Street light near our gate keeps blinking whole night, please change bulb.",
        "House 12, Block C, North Nazimabad",
        None,
        L,
        LO,
        RS,
        "Flickering streetlight near house needs bulb replacement",
    ),
    (
        "Light pole lamp broken in park, families avoid coming in evening.",
        "Hill Park, PECHS",
        None,
        L,
        N,
        OP,
        "Park lamp broken; families avoiding park after dark",
    ),
    (
        "Streetlights are on during the day for weeks, wasting electricity. Timer might be faulty.",
        "Clifton Block 2",
        None,
        L,
        LO,
        OP,
        "Streetlights staying on during daytime; faulty timer suspected",
    ),
    (
        "Underpass lights not working, very dark and unsafe for women walking at night.",
        "Liaquatabad underpass",
        None,
        L,
        H,
        OP,
        "Underpass lights out; unsafe for pedestrians at night",
    ),
    (
        "Stray dogs in large number in our street, kids scared to go to school.",
        "Street 3, Korangi No. 5",
        None,
        OT,
        N,
        OP,
        "Large stray dog pack frightening children",
    ),
    (
        "Loud wedding hall music after midnight every weekend, nobody sleeps. Please enforce timing.",
        "Rashid Minhas Road marquee area",
        None,
        OT,
        LO,
        RJ,
        "Late-night noise from wedding halls on weekends",
    ),
    (
        "Illegal encroachment by vendors on the whole footpath and half the road near the market.",
        "Saddar, Empress Market",
        None,
        OT,
        N,
        IP,
        "Vendor encroachment blocking footpath near Empress Market",
    ),
    (
        "Tree fell on the road after the storm, blocking one lane and resting on a wire.",
        "Street 20, Clifton Block 8",
        None,
        OT,
        H,
        RS,
        "Fallen tree blocking lane and resting on wire after storm",
    ),
]


def seed_items() -> list[NewComplaint]:
    items = []
    for i, (text, location, contact, cat, pri, status, summary) in enumerate(SEED):
        items.append(
            NewComplaint(
                id=uuid.uuid5(SEED_NAMESPACE, text),
                text=text,
                location=location,
                reporter_contact=contact,
                category=cat,
                priority=pri,
                status=status,
                ai_summary=summary,
                triaged_by=TriagedBy.RULES,
                triage_latency_ms=0,
                created_at=ANCHOR + timedelta(hours=11 * i),
            )
        )
    return items


def run() -> int:
    settings = get_settings()
    engine = build_engine(settings)
    try:
        with build_session_factory(engine)() as session:
            repo = ComplaintRepository(session)
            inserted = repo.add_many_ignore_existing(seed_items())
            repo.commit()
    finally:
        engine.dispose()
    if inserted:
        # New rows change the aggregates; drop the cached stats. Best effort.
        try:
            import redis

            redis.Redis.from_url(settings.redis_url, socket_timeout=2).delete(STATS_KEY)
        except Exception:  # noqa: S110 — the 30 s TTL covers this
            pass
    return inserted


def main() -> None:
    configure_logging(get_settings().log_level)
    inserted = run()
    log.info(
        "seed complete",
        extra={"inserted": inserted, "skipped_existing": len(SEED) - inserted, "total": len(SEED)},
    )


if __name__ == "__main__":
    main()
