import subprocess, sys

apis = [
    ("Anthropic", "scripts/test_anthropic.py"),
    ("Amadeus", "scripts/test_amadeus.py"),
    ("Google Maps", "scripts/test_google_maps.py"),
    ("OpenWeatherMap", "scripts/test_weather.py"),
    ("Serper", "scripts/test_serper.py"),
]

results = []
for name, script in apis:
    r = subprocess.run([sys.executable, script], capture_output=True, text=True)
    ok = r.returncode == 0
    results.append((name, ok, r.stdout, r.stderr))
    status = "PASS" if ok else "FAIL"
    print(f"{status} {name}")

passed = sum(1 for _, ok, _, _ in results if ok)
print(f"\n{passed}/{len(apis)} APIs working")

if passed < len(apis):
    print("\nFailed APIs:")
    for name, ok, _, err in results:
        if not ok:
            print(f"  {name}: {err[:200]}")
