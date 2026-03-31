import json
import sqlite3
import os

try:
    conn = sqlite3.connect('storage/v8_platform.sqlite')
    conn.row_factory = sqlite3.Row

    print('=== TRAINING RUNS ===')
    runs = conn.execute('SELECT * FROM training_runs ORDER BY created_at DESC LIMIT 1').fetchall()
    for r in runs:
        d = dict(r)
        d['metrics_json'] = json.loads(d['metrics_json']) if d['metrics_json'] else {}
        print(json.dumps(d, indent=2))

    print('\n=== MODEL REGISTRY RECENTLY ADDED ===')
    models = conn.execute('SELECT tag_name, parent_tag, base_model, status FROM model_versions ORDER BY trained_at DESC LIMIT 1').fetchall()
    for m in models:
        print(json.dumps(dict(m), indent=2))

    print('\n=== DASHBOARD PIPELINE STATE ===')
    state = conn.execute("SELECT config_json FROM service_state WHERE service_name='training_pipeline'").fetchone()
    if state:
        print(json.dumps(json.loads(state['config_json']), indent=2))
        
    conn.close()
except Exception as e:
    print(f'Error: {e}')
