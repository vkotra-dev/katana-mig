from sqlalchemy import create_engine, text
engine = create_engine('mysql+pymysql://katana:Kotra007%23@127.0.0.1:3306/katana_mig')
with engine.begin() as conn:
    conn.execute(text('ALTER TABLE mapping_binding_sign_offs DROP COLUMN destination_field'))
