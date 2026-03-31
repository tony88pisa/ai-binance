from storage.repository import Repository
r = Repository()
snaps = r.get_latest_snapshots()
if not snaps:
    print("NO DATA IN market_snapshots TABLE")
else:
    for s in snaps:
        print(f"{s['asset']:10} price={s['price']:>10.2f}  rsi5m={s.get('rsi_5m',''):>6}  rsi1h={s.get('rsi_1h',''):>6}  decision={s.get('decision',''):>5}  conf={s.get('confidence',''):>3}  updated={s['updated_at'][:19]}")
    print(f"\nTotal: {len(snaps)} snapshots")

hb = r.get_daemon_heartbeat()
print(f"Daemon: {hb['status']} | Heartbeat: {hb['last_heartbeat']}")
