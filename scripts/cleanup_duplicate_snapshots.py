import os
import sys

# Setup django/fastapi environment
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session
from migrations_engine.db.session import SessionLocal
from migrations_engine.db.models import MappingSnapshot, MappingBindingSignOff

def run_cleanup():
    db = SessionLocal()
    
    try:
        # Find all snapshots grouped by (project_id, source_definition_id, destination_object_name)
        # where status == "draft". We are looking for groups with count > 1.
        all_drafts = db.scalars(
            select(MappingSnapshot)
            .where(MappingSnapshot.status == "draft")
            .order_by(
                MappingSnapshot.project_id,
                MappingSnapshot.source_definition_id,
                MappingSnapshot.destination_object_name,
                MappingSnapshot.created_at.desc() # newest first
            )
        ).all()
        
        groups = {}
        for draft in all_drafts:
            key = (draft.project_id, draft.source_definition_id, draft.destination_object_name)
            if key not in groups:
                groups[key] = []
            groups[key].append(draft)
            
        duplicates = {k: v for k, v in groups.items() if len(v) > 1}
        
        if not duplicates:
            print("No duplicate draft snapshots found.")
            return

        print(f"Found {len(duplicates)} duplicate groups.")
        for key, drafts in duplicates.items():
            print(f"\nGroup {key}:")
            # drafts are ordered newest first
            latest_draft = drafts[0]
            older_drafts = drafts[1:]
            print(f"  Keeping latest: {latest_draft.mapping_snapshot_id} (version: {latest_draft.mapping_snapshot_version})")
            
            # Fetch sign-offs for older drafts
            older_ids = [d.mapping_snapshot_id for d in older_drafts]
            sign_offs = db.scalars(
                select(MappingBindingSignOff)
                .where(MappingBindingSignOff.mapping_snapshot_id.in_(older_ids))
            ).all()
            
            if sign_offs:
                print(f"  Found {len(sign_offs)} sign-offs on older drafts.")
                # We need to migrate them to the latest draft if the binding pair exists and values match.
                # Actually the task says "re-associates any MappingBindingSignOff rows from older drafts onto it for pairs whose value still matches".
                
                latest_bindings = {
                    (b["source_field"], b["destination_field"]): b
                    for b in latest_draft.field_bindings
                }
                
                for so in sign_offs:
                    pair = (so.source_field, so.destination_field)
                    
                    # check if older draft's binding matches latest draft's binding
                    # We have to find the older draft
                    older_draft = next(d for d in older_drafts if d.mapping_snapshot_id == so.mapping_snapshot_id)
                    older_binding = next((b for b in older_draft.field_bindings if b["source_field"] == pair[0] and b["destination_field"] == pair[1]), None)
                    latest_binding = latest_bindings.get(pair)
                    
                    if older_binding and latest_binding and older_binding == latest_binding:
                        print(f"    Migrating sign-off {so.id} for pair {pair} to latest draft.")
                        so.mapping_snapshot_id = latest_draft.mapping_snapshot_id
                    else:
                        print(f"    Warning: Sign-off {so.id} for pair {pair} does not match latest draft. It will be left orphaned/deleted when older draft is superseded.")
            
            # Mark older drafts as superseded
            for d in older_drafts:
                print(f"  Marking {d.mapping_snapshot_id} as superseded.")
                d.status = "superseded"
                
        db.commit()
        print("Cleanup completed successfully.")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_cleanup()
