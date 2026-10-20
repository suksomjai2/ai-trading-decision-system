import sys
from pathlib import Path
from datetime import datetime

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
logs = root / "logs"
logs.mkdir(exist_ok=True)
path = logs / datetime.now().strftime("server-%Y%m%d-%H%M%S-%f.log")
stream = path.open("a", encoding="utf-8", buffering=1)
sys.stdout = stream
sys.stderr = stream

from data_feed.research_observer import start as start_research
start_research(root)

from data_feed.supabase_sync import start
start()

from data_feed.live_server import run
run(host="127.0.0.1", port=8000)
