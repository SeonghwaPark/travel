import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from fast_flights import FlightData, Passengers, get_flights

result = get_flights(
    flight_data=[FlightData(date="2026-04-10", from_airport="ICN", to_airport="NRT")],
    trip="one-way",
    passengers=Passengers(adults=1),
    seat="economy",
    fetch_mode="fallback",
)
for i, flight in enumerate(result.flights[:3]):
    print(f"--- Flight {i+1} ---")
    for attr in dir(flight):
        if not attr.startswith('_'):
            val = getattr(flight, attr)
            if not callable(val):
                print(f"  {attr}: {repr(val)}")
