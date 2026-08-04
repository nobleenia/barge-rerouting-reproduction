"""Inspect the canonical rolling-horizon booking-event sequence."""

from __future__ import annotations

from collections import Counter

from barge_rerouting.config import load_experiment_config
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rolling_horizon import build_booking_timeline


def main() -> None:
    """Assemble and print the canonical booking timeline."""
    config = load_experiment_config("configs/toy_experiment.yaml")
    instance = assemble_experiment_instance(config)
    timeline = build_booking_timeline(instance)

    events_per_time = Counter(event.decision_time for event in timeline.events)

    print("Booking timeline")
    print(f"Experiment:       {config.experiment_name}")
    print(f"Fingerprint:      {instance.demand_fingerprint}")
    print(f"Booking events:   {timeline.event_count}")
    print(f"Decision times:   {timeline.decision_times}")
    print("Events per time:")

    for decision_time in timeline.decision_times:
        print(f"  time {decision_time}: {events_per_time[decision_time]} events")

    print()
    print("Sequential booking decisions:")

    for event in timeline.events:
        prior_count = len(timeline.prior_demand_ids(event.sequence_number))
        future_count = len(timeline.future_demand_ids(event.sequence_number))

        print(
            f"  {event.sequence_number:02d} "
            f"| time={event.decision_time} "
            f"| demand={event.demand_id} "
            f"| category={event.demand.category.value} "
            f"| prior={prior_count} "
            f"| future={future_count}"
        )


if __name__ == "__main__":
    main()
