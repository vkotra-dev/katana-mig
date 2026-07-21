from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationInfo, model_validator

class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    source_field: str
    destination_field: str
    binding_type: Literal["direct", "detail_fk", "lookup_fk"]
    reference_table_name: str | None = None
    destination_data_type: str | None = None
    nullable: bool | None = None

    @field_validator("nullable", mode="before")
    @classmethod
    def _validate_nullable(cls, v: any) -> bool | None:
        if v is not None and not isinstance(v, bool):
            raise ValueError("nullable must be a JSON boolean or null")
        return v

    @model_validator(mode="after")
    def _require_ref_for_fk(self, info: ValidationInfo) -> "Binding":
        if self.binding_type in ("detail_fk", "lookup_fk"):
            if not self.reference_table_name:
                raise ValueError(f"reference_table_name is required when binding_type is {self.binding_type}")
        else:
            if self.reference_table_name:
                raise ValueError("reference_table_name must be null when binding_type is direct")
        return self


class TableProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    destination_table_name: str
    bindings: list[Binding]


class AIFieldMappingProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    tables: list[TableProposal]
    error_code: str | None = None
    error_message: str | None = None

    def validate_source_fields(self, valid_source_fields: list[str]) -> list[str]:
        unknown = []
        valid_set = {f.lower() for f in valid_source_fields if f and f.strip()}
        for t in self.tables:
            for b in t.bindings:
                if b.source_field.lower() not in valid_set:
                    unknown.append(b.source_field)
        return list(set(unknown))
