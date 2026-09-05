import math

def distance(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, [a['latitude'],a['longitude'],b['latitude'],b['longitude']])
    x = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(x)))

def nearby(items, location, radius):
    return sorted([{**i,'distance_m':round(distance(i,location))} for i in items if distance(i,location)<=radius], key=lambda i:i['distance_m'])

def sample_line(coordinates, spacing=200):
    points=[]
    for a,b in zip(coordinates,coordinates[1:]):
        length=distance({'latitude':a[1],'longitude':a[0]}, {'latitude':b[1],'longitude':b[0]})
        n=max(1,math.ceil(length/spacing))
        for j in range(n):
            t=j/n
            points.append({'latitude':a[1]+(b[1]-a[1])*t,'longitude':a[0]+(b[0]-a[0])*t})
    if coordinates:
        points.append({'latitude':coordinates[-1][1],'longitude':coordinates[-1][0]})
    return points

def line_distance(point, coordinates):
    """Local equirectangular point-to-segment distance for corridor exclusions."""
    scale=111195
    coslat=math.cos(math.radians(point['latitude']))
    best=float('inf')
    for a,b in zip(coordinates,coordinates[1:]):
        ax=(a[0]-point['longitude'])*scale*coslat; ay=(a[1]-point['latitude'])*scale
        bx=(b[0]-point['longitude'])*scale*coslat; by=(b[1]-point['latitude'])*scale
        dx=bx-ax; dy=by-ay
        t=max(0,min(1,-(ax*dx+ay*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
        best=min(best,math.hypot(ax+t*dx,ay+t*dy))
    return best
