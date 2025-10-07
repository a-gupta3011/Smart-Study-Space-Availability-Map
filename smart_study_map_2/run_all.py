import subprocess, sys, os, time, signal, webbrowser
from pathlib import Path

ROOT = Path(__file__).parent

def ensure_csvs():
    rooms = ROOT / 'backend' / 'rooms.csv'
    tt = ROOT / 'backend' / 'timetable.csv'
    print('Regenerating CSVs with structured campus data (UB, TP, TP2)...')
    subprocess.check_call([sys.executable, 'scripts/generate_sample_data.py', '--seed', '42'])

def populate_db():
    print('Populating DB from CSV (if empty)...')
    subprocess.check_call([sys.executable, '-c', 'import backend.init_db as i; i.populate_from_csv()'])

def start_backend():
    print('Starting backend (uvicorn) on port 8000...')
    return subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '0.0.0.0', '--port', '8000'])


def start_streamlit():
    print('Starting streamlit admin on port 8501...')
    return subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'streamlit_admin/admin.py', '--server.port', '8501'])

def start_streamlit1():
    print('Starting streamlit user on port 8502...')
    return subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'streamlit_user/user.py', '--server.port', '8502'])

def start_streamlit_ops():
    print('Starting Streamlit ops dashboard on port 8503...')
    return subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'streamlit_ops/ops_dashboard.py', '--server.port', '8503'])

def main():
    ensure_csvs()
    populate_db()
    procs = []
    try:
        procs.append(start_backend())
        try:
            procs.append(start_streamlit())
            procs.append(start_streamlit1())
            procs.append(start_streamlit_ops())
        except Exception as e:
            print('Failed to start streamlit (not installed?).', e)
        print('All services launched. Opening analytics dashboard...')
        # Give dev server a moment to start
        time.sleep(2)
        try:
            webbrowser.open('http://localhost:8501')
        except Exception:
            pass
        print('Open http://localhost:8501 (Streamlit Admin), http://localhost:8502 (Streamlit User), and http://localhost:8503 (Ops Dashboard).')
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('Stopping services...')
        for p in procs:
            try:
                p.terminate()
            except:
                pass
if __name__ == '__main__':
    main()
