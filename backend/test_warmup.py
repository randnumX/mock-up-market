import pandas as pd
from app.engine.ema_scalp import EMAScalpStrategy
df = pd.DataFrame([{"Value": 100, "priceDate": "2026-09-24"} for _ in range(30)])
class MockBroker: pass
s = EMAScalpStrategy(MockBroker())
for i in range(len(df)):
    try:
        s.on_bar(df, i)
    except Exception as e:
        print(f"Failed at i={i}: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        break
print("Done")
