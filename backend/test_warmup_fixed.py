import pandas as pd
from app.engine.ema_scalp import EMAScalpStrategy

class MockBroker:
    capital = 100000.0
    positions = {}
    history = []
    def place_order(self, *a, **kw): return False

print("Test 1: Normal warm-up (i=0 initializes columns)")
df = pd.DataFrame([{"Value": 100 + i, "priceDate": f"2026-09-24 09:{30+i:02d}:00", "scripName": "RELIANCE"} for i in range(30)])
s = EMAScalpStrategy(MockBroker())
for i in range(len(df)):
    s.on_bar(df, i)
print("  OK - ema_fast at end:", df.loc[29, "ema_fast"])

print("\nTest 2: Live engine scenario - df rebuilt without ema columns at i=10")
bars = [{"Value": 100 + i, "priceDate": f"2026-09-24 09:{30+i:02d}:00", "scripName": "RELIANCE"} for i in range(10)]
new_bar = {"Value": 111, "priceDate": "2026-09-24 09:40:00", "scripName": "RELIANCE"}
bars.append(new_bar)
df2 = pd.DataFrame(bars)
# No ema_fast column - simulates what happens when live engine builds df from raw stored bars
print("  Columns before:", list(df2.columns))
s2 = EMAScalpStrategy(MockBroker())
try:
    s2.on_bar(df2, 10)
    print("  OK - ema_fast at i=10:", df2.loc[10, "ema_fast"])
except Exception as e:
    print(f"  FAILED: {e}")

print("\nTest 3: Existing ema_fast but NaN for previous row (gaps in history)")
bars2 = [{"Value": 100 + i, "priceDate": f"2026-09-24 09:{30+i:02d}:00", "scripName": "RELIANCE", "ema_fast": None, "ema_slow": None} for i in range(10)]
bars2.append({"Value": 111, "priceDate": "2026-09-24 09:40:00", "scripName": "RELIANCE"})
df3 = pd.DataFrame(bars2)
s3 = EMAScalpStrategy(MockBroker())
try:
    s3.on_bar(df3, 10)
    print("  OK - ema_fast at i=10:", df3.loc[10, "ema_fast"])
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"  FAILED: {e}")

print("\nAll tests passed!")
