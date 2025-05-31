import json
import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

# Load locations from config
with open('locations_config.json') as f:
    config = json.load(f)

with open('maps_api_key.json') as f:
    maps_api_key_config = json.load(f)

address1 = config['location1']
address2 = config['location2']

GOOGLE_MAPS_API_KEY = maps_api_key_config["GOOGLE_MAPS_API_KEY"]
SERVER_COMMAND = "npx"
SERVER_ARGS = ["-y", "@modelcontextprotocol/server-google-maps"]


def extract_json_from_result(result):
    # Extract and parse the first text content from the result
    try:
        text = result.content[0].text
        return json.loads(text)
    except Exception as e:
        raise ValueError(f"Could not extract JSON from result: {e}")

def get_lat_lng(geo_json):
    # Extract latitude and longitude from the geocode JSON
    try:
        location = geo_json['location']
        return location['lat'], location['lng']
    except Exception as e:
        raise ValueError(f"Could not extract lat/lng: {e}")

def calculate_midpoint(lat1, lng1, lat2, lng2):
    return (lat1 + lat2) / 2, (lng1 + lng2) / 2

async def main():
    params = StdioServerParameters(
        command=SERVER_COMMAND,
        args=SERVER_ARGS,
        env={"GOOGLE_MAPS_API_KEY": GOOGLE_MAPS_API_KEY}
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Step 1: Geocode both addresses
            geo1_result = await session.call_tool("maps_geocode", {"address": address1})
            geo2_result = await session.call_tool("maps_geocode", {"address": address2})
            geo1_json = extract_json_from_result(geo1_result)
            geo2_json = extract_json_from_result(geo2_result)
            

            lat1, lng1 = get_lat_lng(geo1_json)
            lat2, lng2 = get_lat_lng(geo2_json)

            print(f"Geocode for {address1}: {lat1}, {lng1}")
            print(f"Geocode for {address2}: {lat2}, {lng2}")

            # Step 2: Calculate midpoint
            mid_lat, mid_lng = calculate_midpoint(lat1, lng1, lat2, lng2)
            print(f"Midpoint coordinates: ({mid_lat}, {mid_lng})")

            # Step 3: Search for coffee shops near the midpoint
            search_result = await session.call_tool(
                "maps_search_places",
                {
                    "query": "coffee shop",
                    "location": {"latitude": mid_lat, "longitude": mid_lng},
                    "radius": 2000
                }
            )
            search_json = extract_json_from_result(search_result)
            # print(f"Search result near midpoint: {json.dumps(search_json, indent=2)}")

            # Pick the place with the highest rating (if any)
            places = search_json.get('places', [])
            if not places:
                print("No places found near the midpoint.")
                return
            best_place = max(places, key=lambda p: p.get('rating', 0))
            place_name = best_place.get('name')
            place_address = best_place.get('formatted_address')
            place_location = best_place.get('geometry', {}).get('location', {})
            print(f"Suggested meeting spot: {place_name}, {place_address} (Rating: {best_place.get('rating', 'N/A')})")

            # Step 4: Get directions for each user to the suggested place
            directions1_result = await session.call_tool(
                "maps_directions",
                {
                    "origin": address1,
                    "destination": place_address,
                    "mode": "driving"
                }
            )
            directions2_result = await session.call_tool(
                "maps_directions",
                {
                    "origin": address2,
                    "destination": place_address,
                    "mode": "driving"
                }
            )
            directions1_json = extract_json_from_result(directions1_result)
            directions2_json = extract_json_from_result(directions2_result)

            def get_distance_duration(directions_json):
                try:
                    route = directions_json['routes'][0]
                    distance = route['distance']['text']
                    duration = route['duration']['text']
                    return distance, duration
                except Exception as e:
                    return None, None

            dist1, dur1 = get_distance_duration(directions1_json)
            dist2, dur2 = get_distance_duration(directions2_json)
            print(f"{address1} to {place_name}: {dist1}, {dur1}")
            print(f"{address2} to {place_name}: {dist2}, {dur2}")

if __name__ == "__main__":
    asyncio.run(main()) 