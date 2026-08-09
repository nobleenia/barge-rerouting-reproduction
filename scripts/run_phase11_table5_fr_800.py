"""Run the frozen Phase-11 Table-5 FR 800-booking pilot with progress reporting."""

from __future__ import annotations

import json
import traceback
from datetime import UTC, datetime
from pathlib import Path
from subprocess import check_output
from threading import Event, Lock, Thread
from time import perf_counter

from barge_rerouting.disruption.timeline import (
    build_operational_timeline,
)
from barge_rerouting.experiments import (
    phase11_table5_execution as table5,
)
from barge_rerouting.experiments.phase11_table5_pilot import (
    build_table5_pilot_inputs,
)
from barge_rerouting.optimization.solver_backend import (
    SolverBackend,
)

TARGET_BOOKINGS = 800
PROGRESS_EVERY = 10
HEARTBEAT_SECONDS = 60

OUTPUT_DIR = Path("results/phase11/table5/pilot")
FINAL_OUTPUT = OUTPUT_DIR / "fr_800.json"
PROGRESS_OUTPUT = OUTPUT_DIR / "fr_800_progress.json"
FAILURE_OUTPUT = OUTPUT_DIR / "fr_800_failure.json"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

inputs = build_table5_pilot_inputs()
backend = SolverBackend.CPLEX_CE_AWARE

git_commit = check_output(
    ["git", "rev-parse", "HEAD"],
    text=True,
).strip()

timeline = build_operational_timeline(
    inputs.instance,
    status_updates=(),
)

# ---------------------------------------------------------------------
# Frozen experiment guards
# ---------------------------------------------------------------------

assert len(inputs.instance.demands) == 800
assert timeline.booking_event_count == 800
assert timeline.status_update_count == 0
assert timeline.event_count == 800

print("=" * 96)
print("PHASE 11 TABLE 5 — FULL REROUTE 800-BOOKING PILOT")
print("=" * 96)
print("Bookings:", timeline.booking_event_count)
print("Status updates:", timeline.status_update_count)
print("Timeline events:", timeline.event_count)
print(
    "Demand fingerprint:",
    inputs.instance.demand_fingerprint,
)
print("Solver backend:", backend.value)
print("Git commit:", git_commit)
print()
print(f"Real progress prints every {PROGRESS_EVERY} completed bookings.")
print(f"A heartbeat prints every {HEARTBEAT_SECONDS} seconds during long solves.")
print("=" * 96)
print(flush=True)


# ---------------------------------------------------------------------
# Initialise exactly like run_phase11_table5_fr()
# ---------------------------------------------------------------------

state = table5.RecoveryOperationalState.empty(table5.RollingBookingState.empty(inputs.instance))

known_updates = []
results = []

booking_count = 0
milestones: list[dict[str, object]] = []

start = perf_counter()
previous_milestone_elapsed = 0.0


# ---------------------------------------------------------------------
# Shared heartbeat state
# ---------------------------------------------------------------------

heartbeat_stop = Event()
heartbeat_lock = Lock()

heartbeat_state: dict[str, object] = {
    "completed_bookings": 0,
    "current_booking": None,
    "current_demand_id": None,
    "current_physical_time": None,
    "current_event_started": None,
}


def write_progress(
    *,
    status: str,
    latest: dict[str, object] | None = None,
) -> None:
    """Persist lightweight progress without modifying experiment state."""
    payload = {
        "status": status,
        "target_bookings": TARGET_BOOKINGS,
        "completed_bookings": booking_count,
        "elapsed_seconds": (perf_counter() - start),
        "latest": latest,
        "milestones": milestones,
        "demand_fingerprint": (inputs.instance.demand_fingerprint),
        "solver_backend": backend.value,
        "git_commit": git_commit,
        "updated_at_utc": datetime.now(UTC).isoformat(),
    }

    PROGRESS_OUTPUT.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def heartbeat() -> None:
    """Print proof-of-life while one FR solve is running."""
    while not heartbeat_stop.wait(HEARTBEAT_SECONDS):
        now = perf_counter()

        with heartbeat_lock:
            snapshot = dict(heartbeat_state)

        event_started = snapshot["current_event_started"]

        if isinstance(
            event_started,
            float,
        ):
            event_elapsed = now - event_started
        else:
            event_elapsed = 0.0

        print(
            "[FR-800 heartbeat] "
            f"completed="
            f"{snapshot['completed_bookings']}/"
            f"{TARGET_BOOKINGS} | "
            f"solving="
            f"{snapshot['current_booking']} | "
            f"demand="
            f"{snapshot['current_demand_id']} | "
            f"t="
            f"{snapshot['current_physical_time']} | "
            f"current event="
            f"{event_elapsed:.1f}s | "
            f"total elapsed="
            f"{now - start:.1f}s",
            flush=True,
        )


write_progress(
    status="starting",
)

heartbeat_thread = Thread(
    target=heartbeat,
    daemon=True,
)

heartbeat_thread.start()


# ---------------------------------------------------------------------
# Execute the exact FR event loop with instrumentation around it
# ---------------------------------------------------------------------

try:
    for entry in timeline.entries:
        event_start = perf_counter()

        current_booking_number = None
        current_demand_id = None

        if entry.is_booking:
            current_booking_number = booking_count + 1

            booking_event = entry.booking_event

            if booking_event is None:
                raise RuntimeError("Booking entry lost its booking event.")

            current_demand_id = booking_event.demand_id

        with heartbeat_lock:
            heartbeat_state["current_booking"] = current_booking_number
            heartbeat_state["current_demand_id"] = current_demand_id
            heartbeat_state["current_physical_time"] = entry.physical_time
            heartbeat_state["current_event_started"] = event_start

        # -------------------------------------------------------------
        # This block is the committed FR runner logic.
        # -------------------------------------------------------------

        if entry.is_status_update:
            status_event = entry.status_update

            if status_event is None:
                raise ValueError("Status entry has no status event.")

            known_updates.append(status_event)

            core_result = table5.dynamic_fr._status_result(
                inputs.instance,
                state,
                entry,
                tuple(known_updates),
                inputs.truck_penalty_per_teu_by_demand,
                backend,
            )

        else:
            core_result = table5.dynamic_fr._booking_result(
                inputs.instance,
                state,
                entry,
                tuple(known_updates),
                inputs.truck_penalty_per_teu_by_demand,
                backend,
            )

        (
            wrapped,
            state,
            stop,
        ) = table5._wrapped_result(
            policy_key="fr",
            instance=inputs.instance,
            state=state,
            core_result=core_result,
        )

        results.append(wrapped)

        # -------------------------------------------------------------
        # Instrumentation resumes here.
        # -------------------------------------------------------------

        event_seconds = perf_counter() - event_start

        if entry.is_booking:
            booking_count += 1

        with heartbeat_lock:
            heartbeat_state["completed_bookings"] = booking_count
            heartbeat_state["current_event_started"] = None

        if entry.is_booking and (
            booking_count % PROGRESS_EVERY == 0 or booking_count == TARGET_BOOKINGS or stop
        ):
            elapsed = perf_counter() - start

            batch_seconds = elapsed - previous_milestone_elapsed

            milestone = {
                "completed_bookings": (booking_count),
                "last_demand_id": (current_demand_id),
                "physical_time": (entry.physical_time),
                "last_event_seconds": (event_seconds),
                "last_10_bookings_seconds": (batch_seconds),
                "elapsed_seconds": elapsed,
                "truck_volume_teu": float(state.total_truck_volume),
                "truck_penalty": float(state.total_truck_penalty),
            }

            milestones.append(milestone)

            previous_milestone_elapsed = elapsed

            write_progress(
                status=("stopped" if stop else "running"),
                latest=milestone,
            )

            print(
                f"[FR-800] "
                f"{booking_count:3d}/"
                f"{TARGET_BOOKINGS} | "
                f"t={entry.physical_time:2d} | "
                f"last="
                f"{current_demand_id} | "
                f"event="
                f"{event_seconds:9.3f}s | "
                f"last10="
                f"{batch_seconds:9.3f}s | "
                f"elapsed="
                f"{elapsed:10.3f}s | "
                f"truck="
                f"{state.total_truck_volume:.1f} TEU",
                flush=True,
            )

        if stop:
            print()
            print(
                f"FR RUN STOPPED EARLY AT BOOKING {booking_count}",
                flush=True,
            )
            break

except Exception as exc:
    elapsed = perf_counter() - start

    failure = {
        "status": "exception",
        "target_bookings": (TARGET_BOOKINGS),
        "completed_bookings": (booking_count),
        "recorded_event_results": (len(results)),
        "exception_type": (type(exc).__name__),
        "exception_message": str(exc),
        "traceback": traceback.format_exc(),
        "elapsed_seconds": elapsed,
        "milestones": milestones,
        "demand_fingerprint": (inputs.instance.demand_fingerprint),
        "solver_backend": (backend.value),
        "git_commit": git_commit,
        "recorded_at_utc": (datetime.now(UTC).isoformat()),
    }

    FAILURE_OUTPUT.write_text(
        json.dumps(
            failure,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    write_progress(
        status="exception",
        latest=(milestones[-1] if milestones else None),
    )

    print()
    print("=" * 96)
    print("FR-800 EXCEPTION")
    print("=" * 96)
    print(
        "Completed bookings:",
        booking_count,
    )
    print(
        "Exception:",
        repr(exc),
    )
    print(
        "Failure saved:",
        FAILURE_OUTPUT,
    )
    print("=" * 96)
    print(flush=True)

    raise

finally:
    heartbeat_stop.set()
    heartbeat_thread.join(timeout=2.0)


# ---------------------------------------------------------------------
# Construct the same validated result contract
# ---------------------------------------------------------------------

run = table5.Table5OperationalPolicyRun(
    policy_key="fr",
    solver_backend=backend,
    timeline=timeline,
    event_results=tuple(results),
    final_state=state,
)

elapsed = perf_counter() - start

record = {
    "phase": "11B4c",
    "table": 5,
    "pilot_policy": "fr",
    "requested_booking_count": (TARGET_BOOKINGS),
    "requested_status_update_count": 0,
    "timeline_event_count": (run.timeline.event_count),
    "recorded_event_count": (len(run.event_results)),
    "processed_booking_count": (run.processed_booking_count),
    "processed_status_count": (run.processed_status_count),
    "completed": run.completed,
    "a036_feasibility_rejection_count": (run.feasibility_rejection_count),
    "a036_feasibility_rejected_demand_ids": list(run.feasibility_rejection_ids),
    "ordinary_rejection_count": (run.ordinary_rejection_count),
    "solver_failure_count": (run.solver_failure_count),
    "accepted_volume_teu": (run.accepted_volume),
    "total_revenue": (run.total_revenue),
    "total_truck_volume_teu": (run.total_truck_volume),
    "total_truck_penalty": (run.total_truck_penalty),
    "net_realised_value": (run.net_realised_value),
    "runtime_seconds": elapsed,
    "runtime_minutes": (elapsed / 60.0),
    "runtime_hours": (elapsed / 3600.0),
    "milestones": milestones,
    "demand_fingerprint": (inputs.instance.demand_fingerprint),
    "solver_backend": backend.value,
    "git_commit": git_commit,
    "recorded_at_utc": datetime.now(UTC).isoformat(),
}

FINAL_OUTPUT.write_text(
    json.dumps(
        record,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)

write_progress(
    status=("completed" if run.completed else "stopped"),
    latest=(milestones[-1] if milestones else None),
)


# ---------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------

print()
print("=" * 96)
print("FR-800 FINAL RESULT")
print("=" * 96)
print(
    "Completed:",
    run.completed,
)
print(
    "Processed bookings:",
    run.processed_booking_count,
)
print(
    "Processed updates:",
    run.processed_status_count,
)
print(
    "A036:",
    run.feasibility_rejection_count,
)
print(
    "A036 IDs:",
    run.feasibility_rejection_ids,
)
print(
    "Ordinary rejects:",
    run.ordinary_rejection_count,
)
print(
    "Solver failures:",
    run.solver_failure_count,
)
print(
    "Accepted TEU:",
    run.accepted_volume,
)
print(
    "Revenue:",
    run.total_revenue,
)
print(
    "Truck TEU:",
    run.total_truck_volume,
)
print(
    "Truck penalty:",
    run.total_truck_penalty,
)
print(
    "Net value:",
    run.net_realised_value,
)
print(
    "Runtime seconds:",
    round(
        elapsed,
        3,
    ),
)
print(
    "Runtime minutes:",
    round(
        elapsed / 60.0,
        3,
    ),
)
print(
    "Runtime hours:",
    round(
        elapsed / 3600.0,
        3,
    ),
)
print(
    "Final result:",
    FINAL_OUTPUT,
)
print(
    "Progress record:",
    PROGRESS_OUTPUT,
)
print("=" * 96)

assert run.timeline.event_count == 800
assert run.processed_booking_count == 800
assert run.processed_status_count == 0
assert run.completed
assert run.solver_failure_count == 0

print()
print("FR-800 PILOT: PASS")
