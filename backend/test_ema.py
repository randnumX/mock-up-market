import pandas as pd
from app.engine.ema_scalp import EMAScalpStrategy
df = pd.DataFrame([{"Value": 100, "priceDate": "2026-09-24 14:20:00"} for _ in range(30)])
class MockBroker:
    pass
s = EMAScalpStrategy(MockBroker())
try:
    for i in range(len(df)):
        s.on_bar(df, i)
    print("Success! columns:", df.columns)
except Exception as e:
    import traceback
    traceback.print_exc()
