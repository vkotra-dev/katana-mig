import sys
sys.path.append('engine/src')
from migrations_engine.db.session import SessionLocal
from migrations_engine.db.models import CodeGenerationArtifact
from migrations_engine.codegen.service import list_codegen_artifacts

with SessionLocal() as db:
    art = db.query(CodeGenerationArtifact).order_by(CodeGenerationArtifact.created_at.desc()).first()
    if art:
        project_id = art.project_id
        res = list_codegen_artifacts(db, project_id=project_id)
        if res:
            first = res[0]
            print("Type:", type(first))
            print("Dict keys:", getattr(first, '__dict__', {}).keys())
            try:
                print("Has attr?", hasattr(first, 'compiled_system_prompt'))
                print("compiled_system_prompt type:", type(first.compiled_system_prompt))
            except Exception as e:
                print("Error:", repr(e))
        else:
            print("No artifacts found for project")
