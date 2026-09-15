"""Domain models and schemas for procurement input, ambiguity reporting, and vendor evaluation.

Strict Pydantic models implementing the 4-field schema contract,
ambiguity diagnostics, and multi-tier evidence structures.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AmbiguitySeverity(str, Enum):
    """Severity classification for procurement requirement ambiguities."""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class AmbiguityType(str, Enum):
    """Categorization of ambiguities identified in material requests."""
    UNSPECIFIED_QUANTITY_UNIT = "UNSPECIFIED_QUANTITY_UNIT"
    NOMINAL_BORE_VS_OUTSIDE_DIAMETER = "NOMINAL_BORE_VS_OUTSIDE_DIAMETER"
    NON_STANDARD_WALL_THICKNESS = "NON_STANDARD_WALL_THICKNESS"
    UNSPECIFIED_STEEL_GRADE = "UNSPECIFIED_STEEL_GRADE"


class VendorTier(str, Enum):
    """Geographic scope tier for vendor separation."""
    AHMEDABAD = "AHMEDABAD"
    INDIA_OUTSIDE_AHMEDABAD = "INDIA_OUTSIDE_AHMEDABAD"
    GLOBAL = "GLOBAL"


class VendorType(str, Enum):
    """Operational classification of industrial vendor."""
    PRIMARY_MANUFACTURER = "PRIMARY_MANUFACTURER"
    AUTHORIZED_DISTRIBUTOR = "AUTHORIZED_DISTRIBUTOR"
    STOCKIST_TRADER = "STOCKIST_TRADER"
    EPC_SUPPLIER = "EPC_SUPPLIER"


class MatchCategory(str, Enum):
    """Match precision level based on verifiable product evidence."""
    EXACT_MATCH = "EXACT_MATCH"
    NEAR_MATCH = "NEAR_MATCH"
    CATEGORY_LEVEL_LEAD = "CATEGORY_LEVEL_LEAD"
    UNVERIFIED_LEAD = "UNVERIFIED_LEAD"


class MaterialInput(BaseModel):
    """4-field input schema representing procurement scenario requirement.

    Field 1: id - Unique material requirement identifier (e.g. M-01)
    Field 2: material - Material description and dimensions
    Field 3: quantity - Quantity required (unitless number per assessment spec)
    Field 4: location - Destination procurement location
    """
    id: str = Field(..., description="Unique material identifier, e.g. M-01")
    material: str = Field(
        ...,
        description="Material description and technical dimensions, e.g. 40 mm MS ERW, Class B pipe",
    )
    quantity: float = Field(
        ...,
        description="Quantity required (intentionally unitless to evaluate ambiguity detection)",
    )
    location: str = Field(
        default="Ahmedabad, Gujarat, India",
        description="Procurement location / delivery destination",
    )


class AmbiguityItem(BaseModel):
    """Structured representation of a technical or commercial ambiguity."""
    field: str = Field(..., description="The input field where ambiguity was detected")
    ambiguity_type: AmbiguityType = Field(..., description="Classification category")
    severity: AmbiguitySeverity = Field(..., description="Severity level")
    description: str = Field(..., description="Technical explanation of the ambiguity")
    stated_assumption: str = Field(..., description="Explicit assumption made by the agent")
    clarification_prompt: str = Field(..., description="Suggested buyer clarification prompt")
    unit_conversions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Conversion values such as meters to metric tons or pipe lengths",
    )


class NormalizedSpecification(BaseModel):
    """Technical specification parsed and normalized from raw input."""
    raw_input: MaterialInput
    parsed_dn_mm: Optional[int] = None
    parsed_od_mm: Optional[float] = None
    parsed_wall_thickness_mm: Optional[float] = None
    parsed_standard: Optional[str] = None
    parsed_class: Optional[str] = None
    is_erw: bool = True
    assumed_quantity_unit: str = "meters"
    estimated_linear_weight_kg_m: Optional[float] = None
    total_estimated_metric_tons: Optional[float] = None
    total_estimated_pieces_6m: Optional[int] = None
    ambiguities: List[AmbiguityItem] = Field(default_factory=list)


class VendorEvidence(BaseModel):
    """Evidence model enforcing strict separation between facts, inferences, and gaps."""
    sourced_facts: List[str] = Field(
        default_factory=list,
        description="Directly cited facts from verified catalogs, certificates, or registry [SOURCED]",
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Engineering inferences made by the model [ASSUMPTION]",
    )
    needs_confirmation_rfq: List[str] = Field(
        default_factory=list,
        description="Items requiring explicit confirmation via buyer RFQ [NEEDS_CONFIRMATION_RFQ]",
    )
    catalog_spec: str = Field(..., description="Relevant product line or catalog description")
    source_url: str = Field(..., description="Verifiable reference URL or source catalog")
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: str = Field(..., description="Physical verified facility or office location")
    certifications: List[str] = Field(default_factory=list, description="Verified standards/certifications")


class EvaluatedVendor(BaseModel):
    """Evaluated and scored vendor candidate."""
    vendor_name: str
    tier: VendorTier
    location: str
    country: str
    vendor_type: VendorType
    match_category: MatchCategory
    confidence_score: float = Field(..., ge=0.0, le=100.0)
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    evidence: VendorEvidence
    unresolved_issues: List[str] = Field(default_factory=list)
    recommended_next_step: str
    rank: int = 1


class ProcurementResult(BaseModel):
    """Complete procurement workflow result payload."""
    material_id: str
    run_id: str
    timestamp: str
    location: str
    specification: NormalizedSpecification
    ahmedabad_vendors: List[EvaluatedVendor] = Field(default_factory=list)
    india_vendors: List[EvaluatedVendor] = Field(default_factory=list)
    global_vendors: List[EvaluatedVendor] = Field(default_factory=list)
    exclusion_log: List[Dict[str, str]] = Field(default_factory=list)
    audit_trail: List[str] = Field(default_factory=list)
    llm_synthesis: Optional[str] = Field(default=None, description="Executive procurement synthesis from LLM")
    model_provider: Optional[str] = Field(default="mock", description="Active LLM provider name")
