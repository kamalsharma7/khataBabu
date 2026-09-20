from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import OutletCounter


async def next_outlet_counter(db: AsyncSession, outlet_id: uuid.UUID, kind: str) -> int:
    today = date.today()
    result = await db.execute(
        select(OutletCounter)
        .where(
            OutletCounter.outlet_id == outlet_id,
            OutletCounter.counter_date == today,
            OutletCounter.counter_kind == kind,
        )
        .with_for_update(),
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = OutletCounter(
            outlet_id=outlet_id,
            counter_date=today,
            counter_kind=kind,
            value=1,
        )
        db.add(row)
    else:
        row.value += 1
    await db.flush()
    return row.value
