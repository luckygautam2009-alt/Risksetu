"""
Investigate why GSIPDFParser.parse() yields 31417 vs 31509 valid coord lines.
"""
from app.services.ingestion.gsi_parser import GSIPDFParser

parser = GSIPDFParser("/Users/yashgautam/Desktop/risksetu/database/landslide_report.pdf")
records = list(parser.parse())
print(f"GSIPDFParser.parse() yielded: {len(records)} records")

# Let's inspect duplicate slide_nos or duplicate source_record_hashes
hashes = [r.source_record_hash for r in records]
unique_hashes = set(hashes)
print(f"Unique source record hashes: {len(unique_hashes)}")

# Check duplicate hashes count
import collections
counts = collections.Counter(hashes)
duplicates = {k: v for k, v in counts.items() if v > 1}
print(f"Duplicate hashes count: {len(duplicates)}")
