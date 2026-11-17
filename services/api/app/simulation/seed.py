"""Idempotent demo seed: fictional schedule + NASA-derived engines + real model predictions.

Every run deletes the demo tables and rebuilds them from (seed, dataset, model artifact), so the
result is reproducible. Predictions are produced here by the trained `RulPredictor`; the API only
reads them.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from aerofleet_ml.data.cmapss import COLUMNS
from aerofleet_ml.data.load import UNIT, load_subset
from aerofleet_ml.inference.predictor import MANIFEST_FILE, Prediction, RulPredictor
from app import models
from app.services.fleet import load_snapshot
from app.services.maintenance import derive_jobs
from app.simulation.airline import GENERATOR_VERSION, ScheduleConfig, generate_schedule
from app.simulation.maintenance import FACILITIES, PARTS

SETTINGS = list(COLUMNS[2:5])
SENSORS = list(COLUMNS[5:])


class SeedError(RuntimeError):
    pass


@dataclass(frozen=True)
class SeedReport:
    model_version: str
    data_kind: str
    aircraft: int
    engines: int
    flights: int
    observations: int
    source_units: tuple[int, ...]
    maintenance_jobs: int


def _select_units(final: dict[int, Prediction], n: int, rng: random.Random) -> list[int]:
    """Spread engines across the predicted-RUL range: one seeded pick per quantile chunk.

    Uses only model predictions (never ground truth) so the fleet mix is realistic to an operator.
    """
    if len(final) < n:
        raise SeedError(f"need {n} engines but the dataset has {len(final)} test units")
    ordered = sorted(final, key=lambda u: (final[u].rul_point, u))
    return [rng.choice(list(chunk)) for chunk in np.array_split(np.array(ordered), n)]


def _clear(session: Session) -> None:
    for table in (
        models.ScenarioResult,
        models.Scenario,
        models.MaintenanceJob,
        models.PartInventory,
        models.TechnicianShift,
        models.MaintenanceBay,
        models.MaintenanceFacility,
        models.EnginePrediction,
        models.EngineObservation,
        models.Flight,
        models.Engine,
        models.Aircraft,
        models.ModelVersion,
        models.Simulation,
        models.Airport,
    ):
        session.execute(delete(table))


def seed_database(
    session: Session,
    dataset_dir: Path,
    artifact_dir: Path,
    config: ScheduleConfig | None = None,
    *,
    allow_synthetic: bool = False,
    planning_buffer: int = 10,
) -> SeedReport:
    cfg = config or ScheduleConfig()
    predictor = RulPredictor.load(artifact_dir)
    manifest: dict[str, Any] = json.loads((artifact_dir / MANIFEST_FILE).read_text())
    metrics: dict[str, Any] = json.loads((artifact_dir / "metrics.json").read_text())
    data_kind = manifest["data_kind"]
    if data_kind != "nasa_cmapss" and not allow_synthetic:
        raise SeedError(f"artifact {manifest['model_version']} was trained on {data_kind}")

    subset = manifest["subset"]
    _, test = load_subset(dataset_dir, subset)
    histories = {
        int(unit): test[test[UNIT] == unit].drop(columns="rul") for unit in test[UNIT].unique()
    }
    trajectories = {u: predictor.predict_trajectory(h) for u, h in histories.items()}
    final = {u: t[-1] for u, t in trajectories.items()}

    rng = random.Random(cfg.seed)
    units = _select_units(final, cfg.n_aircraft, rng)
    rng.shuffle(units)
    schedule = generate_schedule(cfg)
    true_rul = test.groupby(UNIT)["rul"].min()  # value at the last observed cycle

    _clear(session)
    session.add_all(
        models.Airport(
            code=a.code,
            name=a.name,
            city=a.city,
            timezone=a.timezone,
            latitude=a.latitude,
            longitude=a.longitude,
            is_hub=a.is_hub,
            has_maintenance_base=a.has_maintenance_base,
        )
        for a in cfg.airports
    )
    session.flush()  # tables without ORM relationships are inserted in dependency order
    session.add(
        models.Simulation(
            id=1,
            seed=cfg.seed,
            starts_at=cfg.start,
            ends_at=cfg.end,
            generator_version=GENERATOR_VERSION,
            created_at=datetime.now(UTC),
        )
    )
    session.add(
        models.ModelVersion(
            version=predictor.model_version,
            data_kind=data_kind,
            subset=subset,
            trained_at=datetime.fromisoformat(manifest["created_at"]),
            manifest=manifest,
            metrics=metrics,
            is_active=True,
        )
    )
    session.add_all(
        models.Aircraft(
            id=a.id,
            fleet_type=a.fleet_type,
            home_base=a.home_base,
            initial_station=a.initial_station,
            status="active",
        )
        for a in schedule.aircraft
    )
    session.flush()

    observations = 0
    for aircraft, unit in zip(schedule.aircraft, units, strict=True):
        engine_id = f"ENG-{aircraft.id}"
        history = histories[unit]
        session.add(
            models.Engine(
                id=engine_id,
                aircraft_id=aircraft.id,
                source_dataset="NASA C-MAPSS",
                source_subset=subset,
                source_split="test",
                source_unit_id=unit,
                observed_through_cycle=int(history["cycle"].max()),
                eval_true_rul=int(true_rul[unit]),
            )
        )
        session.flush()
        session.add_all(_observations(engine_id, history))
        observations += len(history)
        session.flush()
        session.add_all(
            models.EnginePrediction(
                engine_id=engine_id,
                cycle=p.observed_through_cycle,
                model_version=p.model_version,
                rul_point=p.rul_point,
                rul_lower=p.rul_lower,
                rul_upper=p.rul_upper,
            )
            for p in trajectories[unit]
        )

    session.add_all(
        models.Flight(
            id=f.id,
            flight_number=f.flight_number,
            aircraft_id=f.aircraft_id,
            origin=f.origin,
            destination=f.destination,
            scheduled_departure=f.departure,
            scheduled_arrival=f.arrival,
            status="scheduled",
            cycles=f.cycles,
        )
        for f in schedule.flights
    )
    session.flush()
    jobs = _seed_maintenance(session, cfg, planning_buffer)
    session.commit()
    return SeedReport(
        model_version=predictor.model_version,
        data_kind=data_kind,
        aircraft=len(schedule.aircraft),
        engines=len(units),
        flights=len(schedule.flights),
        observations=observations,
        source_units=tuple(sorted(int(u) for u in units)),
        maintenance_jobs=jobs,
    )


def _seed_maintenance(session: Session, cfg: ScheduleConfig, buffer: int) -> int:
    """Fictional facilities, bays, rosters and spares, plus job cards for the default buffer."""
    for f in FACILITIES:
        session.add(
            models.MaintenanceFacility(
                code=f.code, name=f.name, kind=f.kind, supports=list(f.supports)
            )
        )
    session.flush()
    for f in FACILITIES:
        session.add_all(
            models.MaintenanceBay(id=f"{f.code}-{n}", facility_code=f.code, name=f"Bay {n}")
            for n in range(1, f.bays + 1)
        )
        session.add_all(
            models.TechnicianShift(
                facility_code=f.code,
                name=s.name,
                start_local=s.start,
                end_local=s.end,
                technicians=s.technicians,
                is_night=s.is_night,
            )
            for s in f.shifts
        )
    session.add_all(
        models.PartInventory(
            id=p.id,
            part_type=p.part_type,
            location=p.location,
            quantity=p.quantity,
            available_at=cfg.start + p.available_after,
            transfer_lead_hours=p.transfer_lead_hours,
        )
        for p in PARTS
    )
    session.flush()
    jobs = derive_jobs(load_snapshot(session, buffer))
    session.add_all(
        models.MaintenanceJob(
            id=j.id,
            engine_id=j.engine_id,
            aircraft_id=j.aircraft_id,
            job_type=j.job_type,
            duration_hours=j.duration_hours,
            technicians=j.technicians,
            part_type=j.part_type,
            reason=j.reason,
            planning_buffer=buffer,
            due_flight_id=j.due_flight_id,
            due_at=j.due_at,
            status="open",
        )
        for j in jobs
    )
    return len(jobs)


def _observations(engine_id: str, history: pd.DataFrame) -> list[models.EngineObservation]:
    cycles = history["cycle"].astype(int).tolist()
    settings = history[SETTINGS].to_numpy(dtype=float).tolist()
    sensors = history[SENSORS].to_numpy(dtype=float).tolist()
    return [
        models.EngineObservation(engine_id=engine_id, cycle=c, settings=st, sensors=sn)
        for c, st, sn in zip(cycles, settings, sensors, strict=True)
    ]
