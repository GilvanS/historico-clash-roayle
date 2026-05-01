from datetime import datetime, timezone, timedelta

def format_time_ago(timestamp: str) -> str:
    if not timestamp or timestamp == 'never':
        return "never"
        
    try:
        if 'T' in timestamp:
            if timestamp.endswith('Z'):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(timestamp)
        else:
            dt = datetime.fromisoformat(timestamp)
            
        now = datetime.now(timezone.utc)
        print(f"Now (UTC): {now}")
        print(f"Parsed dt: {dt}, tzinfo: {dt.tzinfo}")
        
        if dt.tzinfo is None:
            # Se não tem timezone (caso dos CSVs locais), assumimos que é horário do Brasil (UTC-3)
            dt = dt.replace(tzinfo=timezone(timedelta(hours=-3)))
            print(f"After replace (UTC-3): {dt}")
            
        time_diff = now - dt
        print(f"Diff: {time_diff}")
        
        if time_diff.days > 0:
            return f"{time_diff.days} days ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            return f"{hours} hours ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            return f"{minutes} minutes ago"
        else:
            return "just now"
    except Exception as e:
        return f"error: {e}"

# Simulação do caso do usuário
# Batalha em 29/04 às 22:04 BRT
# Agora são 29/04 às 22:16 BRT (01:16 UTC de 30/04)
csv_time = "2026-04-29T22:04:00"
print(f"Testing with: {csv_time}")
print(f"Result: {format_time_ago(csv_time)}")
