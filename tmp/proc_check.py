import psutil
import json

def get_procs():
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        if 'python' in p.info['name'].lower() or 'freqtrade' in p.info['name'].lower():
            procs.append(p.info)
    print(json.dumps(procs, indent=2))

if __name__ == "__main__":
    get_procs()
