"""Quick test of Lake County search"""
import asyncio
from src.api.lake_county_service import search_lake_county_project

async def test():
    result = await search_lake_county_project("Wadsworth")
    print(f"Found: {result.get('found')}")
    print(f"Number of matches: {len(result.get('matches', []))}")
    
    for i, m in enumerate(result.get('matches', [])[:3]):
        name = m.get('attributes', {}).get('Name', 'Unknown')
        print(f"{i+1}. {name}")

if __name__ == "__main__":
    asyncio.run(test())
