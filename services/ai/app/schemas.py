"""Request/response shapes and the internal objects passed between stages."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# API contracts
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class TripContext(BaseModel):
    """The app's My Trip, as controlled context (Master Plan §20). Optional."""

    day_count: Optional[int] = Field(default=None, ge=1, le=90)
    destinations: list[str] = Field(default_factory=list, max_length=12)
    start_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("destinations")
    @classmethod
    def short_names(cls, value: list[str]) -> list[str]:
        return [v.strip()[:80] for v in value if v and v.strip()]


class AIActionOut(BaseModel):
    """A proposed action. The app validates it and runs it only on a tap."""

    id: str
    tool: Literal["add_to_trip", "save_place"]
    args: dict[str, Any]
    access: Literal["read", "write", "confirm"]
    label: str
    requires_confirmation: bool = False


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    # The page the traveller is reading when they open the chat. Used as a weak
    # retrieval hint only — it never overrides what they actually asked.
    page_url: Optional[str] = None
    page_title: Optional[str] = None
    locale: Optional[str] = None
    trip_context: Optional[TripContext] = None

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message cannot be empty")
        return value


class ResourceCard(BaseModel):
    """A ComeMorocco page the answer points to."""

    content_id: str
    title: str
    url: str
    anchor_text: str
    reason: str
    score: float


class AffiliateCard(BaseModel):
    """A commercial recommendation. Always rendered with a disclosure."""

    affiliate_id: str
    name: str
    category: str
    url: str
    label: str
    reason: str
    disclosure: str = "Partner link — ComeMorocco may earn a commission if you book through it."


class ChatResponse(BaseModel):
    # Returned so the caller can send it back on the next turn. The widget
    # generates its own and keeps it in localStorage; other clients should
    # store whatever comes back here.
    session_id: str
    conversation_id: str
    message_id: str
    answer: str
    resources: list[ResourceCard] = []
    affiliates: list[AffiliateCard] = []
    intents: list[str] = []
    language: str = "en"
    trip_state: dict[str, Any] = {}
    # Surfaced to the UI so it can render "General seasonal guidance, not a
    # forecast" style notes without the model having to remember to say it.
    notices: list[str] = []
    actions: list[AIActionOut] = []
    latency_ms: int = 0


class FeedbackRequest(BaseModel):
    message_id: str
    helpful: bool
    reason: Optional[
        Literal[
            "incorrect",
            "outdated",
            "irrelevant",
            "too_long",
            "too_short",
            "did_not_answer",
            "bad_link",
            "other",
        ]
    ] = None
    comment: Optional[str] = Field(default=None, max_length=1000)


class AnalyticsEvent(BaseModel):
    name: Literal[
        "chat_opened",
        "chat_closed",
        "message_sent",
        "response_generated",
        "conversation_started",
        "follow_up_question",
        "link_clicked",
        "affiliate_link_clicked",
        "feedback_positive",
        "feedback_negative",
        "error_occurred",
        "conversation_abandoned",
        "starter_question_clicked",
    ]
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    properties: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Internal pipeline objects
# ---------------------------------------------------------------------------

Intent = str

ALL_INTENTS: tuple[str, ...] = (
    "DESTINATION", "ITINERARY", "HOTEL", "ACTIVITY", "RESTAURANT", "TRANSPORTATION",
    "TRAIN", "FLIGHT", "CAR_RENTAL", "WEATHER", "PACKING", "SAFETY", "BUDGET",
    "FOOD", "CULTURE", "FAMILY", "COUPLE", "SOLO", "SENIOR", "DESERT", "HIKING",
    "BEACH", "SHOPPING", "VISA", "BOOKING", "COMPARISON", "PROBLEM", "GENERAL",
    "OFF_TOPIC", "GREETING", "IMPOSSIBLE_ACTION",
)


@dataclass
class TripState:
    """What we know about this traveller's trip so far.

    Every field is optional. The assistant works with partial information and
    never forces the traveller through a questionnaire.
    """

    trip_duration_days: Optional[int] = None
    travel_dates: Optional[str] = None
    season: Optional[str] = None
    party_adults: Optional[int] = None
    party_children: Optional[int] = None
    children_ages: list[str] = field(default_factory=list)
    traveler_type: Optional[str] = None
    destinations: list[str] = field(default_factory=list)
    excluded_destinations: list[str] = field(default_factory=list)
    origin: Optional[str] = None
    arrival_city: Optional[str] = None
    departure_city: Optional[str] = None
    budget: Optional[str] = None
    interests: list[str] = field(default_factory=list)
    transport_preference: Optional[str] = None
    travel_pace: Optional[str] = None
    accommodation_preference: Optional[str] = None
    constraints: list[str] = field(default_factory=list)
    already_visited: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, [], "")}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TripState":
        if not data:
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def is_empty(self) -> bool:
        return not self.to_dict()

    def summary(self) -> str:
        """A compact line for the model prompt."""
        parts = []
        if self.trip_duration_days:
            parts.append(f"{self.trip_duration_days} days")
        if self.travel_dates:
            parts.append(self.travel_dates)
        party = []
        if self.party_adults:
            party.append(f"{self.party_adults} adult{'s' if self.party_adults > 1 else ''}")
        if self.party_children:
            ages = f" (ages {', '.join(self.children_ages)})" if self.children_ages else ""
            party.append(f"{self.party_children} child{'ren' if self.party_children > 1 else ''}{ages}")
        if party:
            parts.append(" + ".join(party))
        if self.traveler_type:
            parts.append(self.traveler_type)
        if self.destinations:
            parts.append("wants: " + ", ".join(self.destinations))
        if self.excluded_destinations:
            parts.append("ruled out: " + ", ".join(self.excluded_destinations))
        if self.already_visited:
            parts.append("already visited: " + ", ".join(self.already_visited))
        if self.arrival_city:
            parts.append(f"arrives {self.arrival_city}")
        if self.departure_city:
            parts.append(f"departs {self.departure_city}")
        if self.budget:
            parts.append(f"budget: {self.budget}")
        if self.travel_pace:
            parts.append(f"pace: {self.travel_pace}")
        if self.transport_preference:
            parts.append(f"transport: {self.transport_preference}")
        if self.accommodation_preference:
            parts.append(f"stays: {self.accommodation_preference}")
        if self.interests:
            parts.append("interests: " + ", ".join(self.interests))
        if self.constraints:
            parts.append("constraints: " + "; ".join(self.constraints))
        return " | ".join(parts)


@dataclass
class RetrievedItem:
    content_id: str
    title: str
    url: str
    score: float
    reasons: list[str]
    item: dict[str, Any]


@dataclass
class Classification:
    intents: list[str]
    language: str
    commercial_intent: Literal["none", "low", "medium", "high"] = "none"
    needs_live_data: bool = False
    safety_sensitive: bool = False
    complexity: Literal["simple", "moderate", "complex"] = "simple"
    destinations: list[str] = field(default_factory=list)
    notes: Optional[str] = None
