"""Inspect the controlled Phase 11 periodic service families."""

from collections import defaultdict

from barge_rerouting.experiments import (
    build_periodic_corridor_transport_legs,
    default_table4_service_family_specs,
)


def main() -> None:
    """Print service slots and departure epochs."""
    periods = tuple(range(0, 29))

    print("Phase 11 Table 4 service-family inspection")
    print("Diagnostic horizon: periods 0..28")
    print("Capacity:           10 TEU")
    print()

    for spec in default_table4_service_family_specs():
        legs = build_periodic_corridor_transport_legs(
            time_periods=periods,
            service_family=spec.family_key,
            capacity_teu=10,
        )

        departures: dict[
            tuple[str, str],
            list[int],
        ] = defaultdict(list)

        for leg in legs:
            if leg.direction == "eastbound" and leg.origin == "A":
                departures[
                    (
                        leg.direction,
                        leg.service_id,
                    )
                ].append(leg.departure_time)

            if leg.direction == "westbound" and leg.origin == "E":
                departures[
                    (
                        leg.direction,
                        leg.service_id,
                    )
                ].append(leg.departure_time)

        print(spec.label)
        print(f"  classification:      {spec.reproduction_class}")
        print(f"  repeat period:       {spec.repeat_period}")
        print(f"  departure offsets:   {spec.departure_offsets}")
        print(f"  slots/direction:      {spec.service_slots_per_direction}")
        print(f"  adjacent travel:      {spec.adjacent_travel_periods}")

        for (
            direction,
            service_id,
        ), values in sorted(departures.items()):
            print(f"  {direction:<10} {service_id}: {tuple(values)}")

        print()


if __name__ == "__main__":
    main()
