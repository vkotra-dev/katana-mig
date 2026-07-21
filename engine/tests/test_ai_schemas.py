import pytest
from pydantic import ValidationError
from migrations_engine.mapping.ai_schemas import Binding, TableProposal, AIFieldMappingProposal

def test_binding_validation():
    # Direct binding allows null reference_table_name
    b1 = Binding(source_field="a", destination_field="b", binding_type="direct")
    assert b1.binding_type == "direct"
    assert b1.reference_table_name is None

    # detail_fk requires reference_table_name
    with pytest.raises(ValidationError):
        Binding(source_field="a", destination_field="b", binding_type="detail_fk")

    # lookup_fk requires reference_table_name
    with pytest.raises(ValidationError):
        Binding(source_field="a", destination_field="b", binding_type="lookup_fk")

    # lookup_fk with reference works
    b2 = Binding(source_field="a", destination_field="b", binding_type="lookup_fk", reference_table_name="foo_ref")
    assert b2.reference_table_name == "foo_ref"

    # direct with reference raises error
    with pytest.raises(ValidationError):
        Binding(source_field="a", destination_field="b", binding_type="direct", reference_table_name="foo_ref")

def test_nullable_validation():
    # nullable must be bool
    with pytest.raises(ValidationError):
        Binding(source_field="a", destination_field="b", binding_type="direct", nullable="yes") # type: ignore

    b3 = Binding(source_field="a", destination_field="b", binding_type="direct", nullable=True)
    assert b3.nullable is True

def test_validate_source_fields():
    proposal = AIFieldMappingProposal(
        tables=[
            TableProposal(
                destination_table_name="T1",
                bindings=[
                    Binding(source_field="col1", destination_field="d1", binding_type="direct"),
                    Binding(source_field="Col2", destination_field="d2", binding_type="direct")
                ]
            )
        ]
    )
    unknown = proposal.validate_source_fields(["col1", "col3"])
    assert len(unknown) == 1
    assert unknown[0].lower() == "col2"
