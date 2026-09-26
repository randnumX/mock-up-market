import pandas as pd
from app.engine.ema_scalp import EMAScalpStrategy
# Mock the df passed to on_bar at tick 11
df = pd.DataFrame([{"Value": 100, "priceDate": "2026-09-24", "ema_fast": None}] * 10 + [{"Value": 101, "priceDate": "2026-09-24"}])
print("Columns before:", df.columns)
class MockBroker:
    pass
s = EMAScalpStrategy(MockBroker())
try:
    s.on_bar(df, 10)
    print("Success! df.loc[10, 'ema_fast'] =", df.loc[10, "ema_fast"])
except Exception as e:
    import traceback
    traceback.print_exc()
