import sqlite3

def clean_db():
    conn = sqlite3.connect('storage/v8_platform.sqlite')
    count_models = conn.execute("DELETE FROM model_versions WHERE tag_name LIKE 'Llama3.2%'").rowcount
    count_runs = conn.execute("DELETE FROM training_runs WHERE model_output_tag LIKE 'Llama3.2%'").rowcount
    conn.commit()
    conn.close()
    print(f"Cleaned {count_models} models and {count_runs} runs.")

if __name__ == '__main__':
    clean_db()
