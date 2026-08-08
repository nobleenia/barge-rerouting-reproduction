"""Ex-ante non-oracle future-demand forecasts for Phase 11.

The source paper uses probability distributions for potential future
demands but does not disclose the complete forecast-generation process.

The controlled Phase 11 baseline therefore generates an independent
forecast catalogue before optimisation begins.

Important boundary:

- realised future demand attributes are never inspected;
- forecast structural attributes use an independent deterministic RNG;
- forecast volumes retain the complete A032 probability distribution;
- DCA-RM and DCA-RRM receive the identical forecast catalogue;
- DCA and DCA-Reroute do not use forecasts.

The exact forecasting process remains a controlled substitute input,
not a claim about undisclosed author data.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

from barge_rerouting.domain import (
    FutureDemandForecast,
    FutureValueInterpretation,
)
from barge_rerouting.experiments.phase11_baseline import (
    default_table4_controlled_demand_process,
    default_table4_controlled_economic_spec,
)
from barge_rerouting.experiments.phase11_demands import (
    Table4RequestTemplate,
    generate_table4_request_templates,
)
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
)
from barge_rerouting.revenue_management.run import (
    ForecastProvider,
)
from barge_rerouting.rolling_horizon import (
    BookingDecisionEvent,
    RollingBookingState,
)

TABLE4_FORECAST_SEED_OFFSET: Final = 2_000_000

TABLE4_FORECAST_VALUE_INTERPRETATION: Final = FutureValueInterpretation.PRINTED

TABLE4_FORECAST_SELECTION_MODE: Final = FutureDemandSelectionMode.A004_SHARED_ARC

# None means no additional look-ahead truncation is applied after the
# ex-ante catalogue provider has removed non-future reservation periods.
TABLE4_FORECAST_LOOKAHEAD_PERIODS: Final[int | None] = None


def _validate_seed(
    value: object,
) -> int:
    """Validate one non-negative experiment seed."""
    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise TypeError("seed must be an integer.")

    if value < 0:
        raise ValueError("seed must be non-negative.")

    return value


def table4_forecast_seed(
    seed: int,
) -> int:
    """Derive the independent ex-ante forecast random stream."""
    return _validate_seed(seed) + TABLE4_FORECAST_SEED_OFFSET


def _fare_for_forecast_template(
    template: Table4RequestTemplate,
) -> float:
    """Return A032 fare for one independent forecast template."""
    economic_spec = default_table4_controlled_economic_spec()

    distance_input = economic_spec.input_for_distance(template.distance)

    early_reservation = template.anticipation_lag >= distance_input.anticipation_threshold

    standard_delivery = template.delivery_slack >= distance_input.delivery_threshold

    fare = economic_spec.fare_per_teu_for_classes(
        distance=template.distance,
        early_reservation=early_reservation,
        standard_delivery=standard_delivery,
    )

    return float(fare)


@dataclass(frozen=True, slots=True)
class Table4ForecastCatalogueEntry:
    """One ex-ante potential future request."""

    reservation_time: int
    slot_number: int
    forecast: FutureDemandForecast

    def __post_init__(self) -> None:
        """Validate catalogue timing and identity."""
        if isinstance(self.reservation_time, bool) or not isinstance(
            self.reservation_time,
            int,
        ):
            raise TypeError("reservation_time must be an integer.")

        if self.reservation_time < 0:
            raise ValueError("reservation_time must be non-negative.")

        if isinstance(self.slot_number, bool) or not isinstance(
            self.slot_number,
            int,
        ):
            raise TypeError("slot_number must be an integer.")

        if self.slot_number < 1 or self.slot_number > 10:
            raise ValueError("slot_number must lie between 1 and 10.")

        if not isinstance(
            self.forecast,
            FutureDemandForecast,
        ):
            raise TypeError("forecast must be a FutureDemandForecast.")

    @property
    def forecast_id(self) -> str:
        """Return forecast identifier."""
        return str(self.forecast.forecast_id)

    @property
    def ordering_key(
        self,
    ) -> tuple[int, int, str]:
        """Return deterministic catalogue order."""
        return (
            self.reservation_time,
            self.slot_number,
            self.forecast_id,
        )


@dataclass(frozen=True, slots=True)
class Table4ForecastCatalogue:
    """Immutable ex-ante forecast catalogue for one demand-set seed."""

    seed: int
    forecast_seed: int
    catalogue_fingerprint: str
    entries: tuple[Table4ForecastCatalogueEntry, ...]

    def __post_init__(self) -> None:
        """Validate catalogue identity and deterministic ordering."""
        selected_seed = _validate_seed(self.seed)
        selected_forecast_seed = _validate_seed(self.forecast_seed)

        if selected_forecast_seed != table4_forecast_seed(selected_seed):
            raise ValueError("forecast_seed is inconsistent with seed.")

        if not isinstance(
            self.entries,
            tuple,
        ):
            raise TypeError("entries must be a tuple.")

        for entry in self.entries:
            if not isinstance(
                entry,
                Table4ForecastCatalogueEntry,
            ):
                raise TypeError("Every entry must be a Table4ForecastCatalogueEntry.")

        ordered = tuple(
            sorted(
                self.entries,
                key=lambda entry: entry.ordering_key,
            )
        )

        if self.entries != ordered:
            raise ValueError(
                "Forecast catalogue entries must be in deterministic chronological order."
            )

        ids = tuple(entry.forecast_id for entry in self.entries)

        if len(set(ids)) != len(ids):
            raise ValueError("Forecast identifiers must be unique.")

        if forecast_catalogue_fingerprint(self.entries) != self.catalogue_fingerprint:
            raise ValueError("catalogue_fingerprint does not match entries.")

    @property
    def entry_count(self) -> int:
        """Return total ex-ante forecast opportunities."""
        return len(self.entries)


def _forecast_entry_record(
    entry: Table4ForecastCatalogueEntry,
) -> dict[str, object]:
    """Return one stable serialisable catalogue record."""
    forecast = entry.forecast

    return {
        "reservation_time": (entry.reservation_time),
        "slot_number": entry.slot_number,
        "forecast_id": forecast.forecast_id,
        "origin": forecast.origin,
        "destination": forecast.destination,
        "availability_time": (forecast.availability_time),
        "due_time": forecast.due_time,
        "category": forecast.category.value,
        "fare_per_teu": (float(forecast.fare_per_teu)),
        "volume_outcomes": [
            {
                "volume": outcome.volume,
                "probability": (float(outcome.probability)),
            }
            for outcome in forecast.outcomes
        ],
    }


def forecast_catalogue_fingerprint(
    entries: Sequence[Table4ForecastCatalogueEntry],
) -> str:
    """Return SHA-256 of a complete ex-ante catalogue."""
    selected = tuple(entries)

    for entry in selected:
        if not isinstance(
            entry,
            Table4ForecastCatalogueEntry,
        ):
            raise TypeError("Every entry must be a Table4ForecastCatalogueEntry.")

    records = tuple(_forecast_entry_record(entry) for entry in selected)

    payload = json.dumps(
        records,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return sha256(payload.encode("utf-8")).hexdigest()


def build_table4_forecast_catalogue(
    *,
    seed: int,
) -> Table4ForecastCatalogue:
    """Generate one independent ex-ante forecast catalogue."""
    selected_seed = _validate_seed(seed)

    process_spec = default_table4_controlled_demand_process()
    economic_spec = default_table4_controlled_economic_spec()

    forecast_seed = table4_forecast_seed(selected_seed)

    templates = generate_table4_request_templates(
        process_spec,
        seed=forecast_seed,
    )

    entries: list[Table4ForecastCatalogueEntry] = []

    for template in templates:
        slot_number = ((template.sequence_number - 1) % process_spec.requests_per_period) + 1

        forecast = FutureDemandForecast(
            forecast_id=(f"FC{template.sequence_number:04d}"),
            origin=template.origin,
            destination=template.destination,
            availability_time=(template.availability_time),
            due_time=template.due_time,
            category=template.category,
            fare_per_teu=(_fare_for_forecast_template(template)),
            outcomes=(economic_spec.volume_distribution.outcomes),
        )

        entries.append(
            Table4ForecastCatalogueEntry(
                reservation_time=(template.reservation_time),
                slot_number=slot_number,
                forecast=forecast,
            )
        )

    selected_entries = tuple(entries)

    return Table4ForecastCatalogue(
        seed=selected_seed,
        forecast_seed=forecast_seed,
        catalogue_fingerprint=(forecast_catalogue_fingerprint(selected_entries)),
        entries=selected_entries,
    )


def forecasts_after_decision_time(
    catalogue: Table4ForecastCatalogue,
    *,
    decision_time: int,
) -> tuple[FutureDemandForecast, ...]:
    """Return forecasts from strictly later reservation periods."""
    if not isinstance(
        catalogue,
        Table4ForecastCatalogue,
    ):
        raise TypeError("catalogue must be a Table4ForecastCatalogue.")

    if isinstance(decision_time, bool) or not isinstance(
        decision_time,
        int,
    ):
        raise TypeError("decision_time must be an integer.")

    if decision_time < 0:
        raise ValueError("decision_time must be non-negative.")

    return tuple(
        entry.forecast for entry in catalogue.entries if entry.reservation_time > decision_time
    )


def build_table4_forecast_provider(
    catalogue: Table4ForecastCatalogue,
) -> ForecastProvider:
    """Build the non-oracle provider used by DCA-RM/DCA-RRM."""
    if not isinstance(
        catalogue,
        Table4ForecastCatalogue,
    ):
        raise TypeError("catalogue must be a Table4ForecastCatalogue.")

    def provide(
        event: BookingDecisionEvent,
        state: RollingBookingState,
    ) -> tuple[FutureDemandForecast, ...]:
        if not isinstance(
            event,
            BookingDecisionEvent,
        ):
            raise TypeError("event must be a BookingDecisionEvent.")

        if not isinstance(
            state,
            RollingBookingState,
        ):
            raise TypeError("state must be a RollingBookingState.")

        return forecasts_after_decision_time(
            catalogue,
            decision_time=event.decision_time,
        )

    return provide


def write_table4_forecast_catalogue(
    catalogue: Table4ForecastCatalogue,
    *,
    output_directory: str | Path,
    demand_set_id: str,
) -> tuple[Path, Path]:
    """Persist forecast CSV and traceability manifest."""
    if not isinstance(
        catalogue,
        Table4ForecastCatalogue,
    ):
        raise TypeError("catalogue must be a Table4ForecastCatalogue.")

    if not isinstance(
        demand_set_id,
        str,
    ):
        raise TypeError("demand_set_id must be a string.")

    selected_id = demand_set_id.strip()

    if not selected_id:
        raise ValueError("demand_set_id must be non-empty.")

    directory = Path(output_directory)
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_path = directory / f"{selected_id}_forecast_catalogue.csv"
    manifest_path = directory / f"{selected_id}_forecast_manifest.json"

    fieldnames = (
        "reservation_time",
        "slot_number",
        "forecast_id",
        "origin",
        "destination",
        "availability_time",
        "due_time",
        "category",
        "fare_per_teu",
        "volume_outcomes",
    )

    with csv_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for entry in catalogue.entries:
            record = _forecast_entry_record(entry)
            record["volume_outcomes"] = json.dumps(
                record["volume_outcomes"],
                sort_keys=True,
                separators=(",", ":"),
            )
            writer.writerow(record)

    manifest = {
        "demand_set_id": selected_id,
        "seed": catalogue.seed,
        "forecast_seed": (catalogue.forecast_seed),
        "classification": ("controlled_substitute_input"),
        "forecast_entry_count": (catalogue.entry_count),
        "catalogue_fingerprint": (catalogue.catalogue_fingerprint),
        "provider_rule": ("strictly_later_reservation_period"),
        "selection_mode": (TABLE4_FORECAST_SELECTION_MODE.value),
        "value_interpretation": (TABLE4_FORECAST_VALUE_INTERPRETATION.value),
        "lookahead_periods": (TABLE4_FORECAST_LOOKAHEAD_PERIODS),
        "uses_realised_future_attributes": False,
    }

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return (
        csv_path,
        manifest_path,
    )
