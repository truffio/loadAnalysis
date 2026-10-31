"""Pydantic schema for the JSON definition file (docs/spec.md §5).

Parsing is strict: a number is a finite JSON number, never a boolean or numeric string. Rules that
span several elements live in `ela.validate`.
"""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

BAND_NAMES = ("transient", "short_term", "continuous")

Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Watts = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]
Volts = Annotated[float, Field(strict=True, allow_inf_nan=False, gt=0)]
Margin = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]
Efficiency = Annotated[float, Field(strict=True, allow_inf_nan=False, gt=0, le=1)]
Phases = Annotated[int, Field(strict=True, ge=1)]

SwitchState = Literal["closed", "open"]
RunState = Literal["operative", "failed"]
SOURCE_STATES = ("operative", "failed")
RAT_STATES = ("available", "unavailable")


class Bands(BaseModel):
    """One power or capacity figure per time band."""

    transient: Watts
    short_term: Watts
    continuous: Watts


class Meta(BaseModel):
    aircraft: StrictStr
    revision: StrictStr
    description: StrictStr | None = None


class BandInfo(BaseModel):
    label: StrictStr | None = None
    duration_s: Number | None = None


class BandSettings(BaseModel):
    transient: BandInfo = Field(default_factory=BandInfo)
    short_term: BandInfo = Field(default_factory=BandInfo)
    continuous: BandInfo = Field(default_factory=BandInfo)

    @model_validator(mode="after")
    def _fill_default_labels(self):
        defaults = {"transient": "Transient", "short_term": "5 s", "continuous": "Continuous"}
        for band, label in defaults.items():
            info = getattr(self, band)
            if info.label is None:
                info.label = label
        return self


class Settings(BaseModel):
    safety_margin: Margin
    bands: BandSettings = Field(default_factory=BandSettings)


class Element(BaseModel):
    id: StrictStr
    name: StrictStr


class Rated(Element):
    """An element that takes a capacity check."""

    capacity: Bands | None = None
    safety_margin: Margin | None = None


class Source(Rated):
    kind: Literal["engine_generator", "apu_generator", "emergency_generator", "battery"]
    engine: StrictInt | None = Field(default=None, validate_default=True)
    output: Literal["AC", "DC"]
    voltage: Volts
    phases: Phases = 3  # read only on AC. `phases` in the file of a DC source is an unknown key.
    capacity: Bands
    default_state: StrictStr

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if data.get("output") == "DC":
            data.pop("phases", None)
        if data.get("kind", "emergency_generator") == "emergency_generator":
            data.setdefault("default_state", "unavailable")
        return data

    @field_validator("engine")
    @classmethod
    def _engine_generators_need_a_number(cls, value, info: ValidationInfo):
        if value is None and info.data.get("kind") == "engine_generator":
            raise PydanticCustomError("missing_key", "missing required key 'engine'")
        return value

    @field_validator("default_state")
    @classmethod
    def _state_suits_kind(cls, value, info: ValidationInfo):
        kind = info.data.get("kind")
        if kind is None:
            return value
        allowed = RAT_STATES if kind == "emergency_generator" else SOURCE_STATES
        if value not in allowed:
            raise PydanticCustomError(
                "enum", "Input should be {allowed}", {"allowed": " or ".join(allowed)}
            )
        return value


class Bus(Rated):
    type: Literal["AC", "DC"]
    role: Literal["main", "essential", "emergency", "other", "battery"]
    voltage: Volts
    phases: Phases = 3  # read only on AC. `phases` in the file of a DC bus is an unknown key.
    crew_switch: StrictBool = False

    @model_validator(mode="before")
    @classmethod
    def _drop_dc_phases(cls, data):
        if isinstance(data, dict) and data.get("type") == "DC":
            data = {k: v for k, v in data.items() if k != "phases"}
        return data

    @field_validator("role")
    @classmethod
    def _battery_role_is_dc_only(cls, value, info: ValidationInfo):
        if value == "battery" and info.data.get("type") == "AC":
            raise PydanticCustomError("enum", "role 'battery' is not allowed on an AC bus")
        return value


class Tru(Rated):
    input_bus: StrictStr
    output_bus: StrictStr
    efficiency: Efficiency
    capacity: Bands  # output capacity
    default_state: RunState


class Contactor(Rated):
    kind: Literal["source", "bus_tie", "tru"]
    from_: StrictStr = Field(alias="from")
    to: StrictStr
    default_state: SwitchState

    model_config = ConfigDict(populate_by_name=True)


class Load(Element):
    bus: StrictStr
    power: Bands
    essential: StrictBool = False


class Scenario(BaseModel):
    id: StrictStr
    name: StrictStr
    description: StrictStr | None = None
    states: dict[StrictStr, StrictStr]


class Definition(BaseModel):
    """A whole definition file. Use `ela.validate.validate` to build one from a parsed document."""

    meta: Meta
    settings: Settings
    sources: list[Source]
    buses: list[Bus]
    trus: list[Tru]
    contactors: list[Contactor]
    loads: list[Load]
    scenarios: list[Scenario]
