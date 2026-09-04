"""
Run EXPLAIN ANALYZE on spatial queries.
"""
from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# 1. Historical landslide search query around Chamoli (30.555, 79.123)
sql_current = """
EXPLAIN ANALYZE
SELECT id, gsi_slide_no, ST_Distance(ST_GeogFromWKB(ST_AsBinary(geom)), ST_GeogFromWKB(ST_AsBinary(ST_SetSRID(ST_MakePoint(79.123, 30.555), 4326)))) as dist
FROM historical_landslides
WHERE ST_DWithin(ST_GeogFromWKB(ST_AsBinary(geom)), ST_GeogFromWKB(ST_AsBinary(ST_SetSRID(ST_MakePoint(79.123, 30.555), 4326))), 25000)
ORDER BY dist;
"""

print("=== EXPLAIN ANALYZE: Current Query ===")
res = db.execute(text(sql_current)).fetchall()
for r in res:
    print(r[0])

# 2. Test direct cast geom::geography
sql_cast = """
EXPLAIN ANALYZE
SELECT id, gsi_slide_no, ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(79.123, 30.555), 4326)::geography) as dist
FROM historical_landslides
WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(79.123, 30.555), 4326)::geography, 25000)
ORDER BY dist;
"""

print("\n=== EXPLAIN ANALYZE: geom::geography ===")
res_cast = db.execute(text(sql_cast)).fetchall()
for r in res_cast:
    print(r[0])

# 3. Test nearest road network node query
sql_road = """
EXPLAIN ANALYZE
SELECT osm_node_id, ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(75.8708, 30.8933), 4326)::geography) as dist
FROM road_network_nodes
WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(75.8708, 30.8933), 4326)::geography, 5000)
ORDER BY dist;
"""

print("\n=== EXPLAIN ANALYZE: Road Node Search ===")
res_road = db.execute(text(sql_road)).fetchall()
for r in res_road:
    print(r[0])

db.close()
