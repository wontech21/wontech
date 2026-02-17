"""
Delivery Routes — driver dispatch, route optimization, delivery tracking.
"""

from flask import Blueprint, jsonify, request, g
import json
import os
import requests as http_requests
from datetime import datetime

from db_manager import get_org_db
from middleware import login_required, organization_required

delivery_bp = Blueprint('delivery', __name__, url_prefix='/api/delivery')

GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _parse_dt(dt_str):
    """Parse a datetime string, return datetime or None."""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        try:
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError):
            return None


def _priority_score(created_at_str, distance_miles, scheduled_for_str=None, max_radius=10.0):
    """Higher score = more urgent delivery.

    Regular orders:  minutes_waiting × (1 + distance / max_radius)
    Scheduled orders: urgency based on how close we are to the promised time.
      - lead_time = estimated drive time + 10 min buffer
      - effective_wait = lead_time - minutes_until_due
      - 2× multiplier (missing a promised time is worse than a regular wait)
      - Once past due, urgency climbs rapidly
    """
    now = datetime.now()
    dist = distance_miles or 0
    distance_factor = 1 + dist / max_radius

    if scheduled_for_str:
        scheduled = _parse_dt(scheduled_for_str)
        if scheduled:
            minutes_until_due = (scheduled - now).total_seconds() / 60.0
            # Estimated lead time: drive time (~2.5 min/mile) + 10 min buffer
            lead_time = (dist * 2.5) + 10
            effective_wait = lead_time - minutes_until_due
            if effective_wait < 0:
                # Still have time, but start building priority as window shrinks
                effective_wait = max(0, lead_time - minutes_until_due + 10) * 0.5
            # 2× multiplier for scheduled orders
            return round(effective_wait * 2 * distance_factor, 2)

    # Regular order: time since placed
    created = _parse_dt(created_at_str)
    if not created:
        return 0
    minutes_waiting = (now - created).total_seconds() / 60.0
    return round(minutes_waiting * distance_factor, 2)


def _geocode_address(address):
    """Convert address string to lat/lng via Google Geocoding API."""
    if not GOOGLE_MAPS_API_KEY or not address:
        return None, None
    try:
        resp = http_requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json',
            params={'address': address, 'key': GOOGLE_MAPS_API_KEY},
            timeout=5,
        )
        data = resp.json()
        if data.get('status') == 'OK' and data.get('results'):
            loc = data['results'][0]['geometry']['location']
            return loc['lat'], loc['lng']
    except Exception:
        pass
    return None, None


def _distance_matrix(origins, destinations):
    """Call Google Distance Matrix API. Returns list of durations in minutes.
    origins/destinations are lists of "lat,lng" strings."""
    if not GOOGLE_MAPS_API_KEY:
        return None
    try:
        resp = http_requests.get(
            'https://maps.googleapis.com/maps/api/distancematrix/json',
            params={
                'origins': '|'.join(origins),
                'destinations': '|'.join(destinations),
                'key': GOOGLE_MAPS_API_KEY,
                'units': 'imperial',
            },
            timeout=10,
        )
        data = resp.json()
        if data.get('status') != 'OK':
            return None
        return data['rows']
    except Exception:
        return None


def _get_store_address():
    """Get store address from org settings or pos_settings."""
    conn = get_org_db()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM pos_settings WHERE setting_key = 'store_address'")
    row = cursor.fetchone()
    return row[0] if row else None


def _get_store_coords():
    """Get store lat/lng, geocoding and caching if needed."""
    conn = get_org_db()
    cursor = conn.cursor()

    # Check cached coords
    cursor.execute("SELECT setting_value FROM pos_settings WHERE setting_key = 'store_lat'")
    lat_row = cursor.fetchone()
    cursor.execute("SELECT setting_value FROM pos_settings WHERE setting_key = 'store_lng'")
    lng_row = cursor.fetchone()
    if lat_row and lng_row:
        try:
            return float(lat_row[0]), float(lng_row[0])
        except (ValueError, TypeError):
            pass

    # Geocode from address
    address = _get_store_address()
    if address:
        lat, lng = _geocode_address(address)
        if lat and lng:
            cursor.execute(
                "INSERT OR REPLACE INTO pos_settings (setting_key, setting_value) VALUES ('store_lat', ?)",
                (str(lat),))
            cursor.execute(
                "INSERT OR REPLACE INTO pos_settings (setting_key, setting_value) VALUES ('store_lng', ?)",
                (str(lng),))
            conn.commit()
            return lat, lng
    return None, None


def _haversine_miles(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points in miles."""
    import math
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_neighbor_order(stops, store_coords):
    """Reorder stops via nearest-neighbor starting from store. Returns sorted list."""
    if len(stops) <= 1:
        return stops
    ordered = []
    remaining = list(stops)
    current_lat, current_lng = store_coords

    while remaining:
        best = None
        best_dist = float('inf')
        for s in remaining:
            if s.get('lat') and s.get('lng'):
                d = _haversine_miles(current_lat, current_lng, s['lat'], s['lng'])
            else:
                d = float('inf')
            if d < best_dist:
                best_dist = d
                best = s
        if not best:
            ordered.extend(remaining)
            break
        ordered.append(best)
        remaining.remove(best)
        if best.get('lat') and best.get('lng'):
            current_lat, current_lng = best['lat'], best['lng']

    return ordered


def _bearing_from_store(store_lat, store_lng, lat, lng):
    """Compass bearing (0-360) from store to a point. 0=N, 90=E, 180=S, 270=W."""
    import math
    dlat = lat - store_lat
    dlng = lng - store_lng
    return math.degrees(math.atan2(dlng, dlat)) % 360


def _cluster_max_priority(cluster):
    """Highest priority score in a cluster."""
    return max(o.get('priority_score', 0) for o in cluster)


def _route_distance(group, store_coords):
    """Total haversine: store → stops (nearest-neighbor order) → store."""
    if not group or not store_coords:
        return 0
    pts = [(o.get('lat'), o.get('lng')) for o in group if o.get('lat') and o.get('lng')]
    if not pts:
        return 0
    total = 0
    cur = store_coords
    remaining = list(pts)
    while remaining:
        best_d, best_i = float('inf'), 0
        for i, p in enumerate(remaining):
            d = _haversine_miles(cur[0], cur[1], p[0], p[1])
            if d < best_d:
                best_d, best_i = d, i
        total += best_d
        cur = remaining.pop(best_i)
    total += _haversine_miles(cur[0], cur[1], store_coords[0], store_coords[1])
    return total


def _best_split_for_count(all_orders, num_routes, store_coords):
    """Find the best contiguous split of the sweep into num_routes groups.
    Returns (groups, total_route_distance) or None if impossible."""
    import math
    from itertools import combinations

    total = len(all_orders)
    if num_routes <= 0 or num_routes > total:
        return None
    if num_routes == 1:
        return [all_orders], _route_distance(all_orders, store_coords)

    min_size = max(1, total // num_routes)
    max_size = math.ceil(total / num_routes)

    best_cost = float('inf')
    best_groups = None

    for splits in combinations(range(1, total), num_routes - 1):
        boundaries = [0] + list(splits) + [total]
        groups = [all_orders[boundaries[i]:boundaries[i + 1]]
                  for i in range(num_routes)]
        if any(len(g) < min_size or len(g) > max_size for g in groups):
            continue
        cost = sum(_route_distance(g, store_coords) for g in groups)
        if cost < best_cost:
            best_cost = cost
            best_groups = groups

    if best_groups:
        return best_groups, best_cost
    return None


def _estimate_route_minutes(group):
    """Estimate minutes for a route: drive time + 3 min per stop + 10 min overhead."""
    return sum(o.get('drive_time_min', 5) + 3 for o in group) + 10


# Target range for route duration (minutes)
ROUTE_MIN_MINUTES = 30
ROUTE_MAX_MINUTES = 50


def _build_routes_for_orders(orders, drivers, store_coords):
    """Direction-aware route builder — angular sweep + optimal driver count.

    1. Compute compass bearing from store to each order
    2. Sort by bearing, find largest gap → sweep start
    3. Try driver counts from 1 to len(drivers) — for each, find best
       contiguous split minimizing total route distance
    4. Pick the driver count where routes best fit the 30-55 min sweet spot
    5. Assign routes to drivers: most urgent → first available
    6. Optimize stop order within each route via nearest-neighbor
    """
    import math

    if not orders or not drivers:
        return []

    max_drivers = len(drivers)

    # --- Phase 1: Compute bearings and sort ---
    geocoded = []
    no_coords = []
    for o in orders:
        if o.get('lat') and o.get('lng') and store_coords:
            o['bearing'] = _bearing_from_store(
                store_coords[0], store_coords[1], o['lat'], o['lng'])
            geocoded.append(o)
        else:
            no_coords.append(o)

    geocoded.sort(key=lambda o: o['bearing'])

    # --- Phase 2: Find largest angular gap → sweep start ---
    n = len(geocoded)
    if n > 1:
        max_gap = 0
        gap_idx = 0
        for i in range(n):
            next_b = geocoded[(i + 1) % n]['bearing']
            this_b = geocoded[i]['bearing']
            gap = (next_b - this_b) % 360
            if gap > max_gap:
                max_gap = gap
                gap_idx = (i + 1) % n
        geocoded = geocoded[gap_idx:] + geocoded[:gap_idx]

    all_orders = geocoded + no_coords
    total = len(all_orders)

    # --- Phase 3: Find optimal driver count ---
    # Try each possible driver count, score by how well routes fit the sweet spot.
    best_score = float('inf')
    best_clusters = None

    for try_count in range(1, min(max_drivers, total) + 1):
        result = _best_split_for_count(all_orders, try_count, store_coords)
        if not result:
            continue
        groups, _ = result

        # Score: penalty for routes outside the 30-55 min sweet spot
        penalty = 0
        for g in groups:
            est = _estimate_route_minutes(g)
            if est < ROUTE_MIN_MINUTES:
                penalty += (ROUTE_MIN_MINUTES - est) ** 2
            elif est > ROUTE_MAX_MINUTES:
                penalty += (est - ROUTE_MAX_MINUTES) ** 2

        if penalty < best_score:
            best_score = penalty
            best_clusters = groups

    clusters = best_clusters if best_clusters else [all_orders]

    # --- Phase 4: Assign routes to drivers by urgency ---
    clusters.sort(key=lambda c: _cluster_max_priority(c), reverse=True)

    routes = []
    for idx, driver in enumerate(drivers):
        if idx >= len(clusters):
            break
        cluster = clusters[idx]

        # Optimize stop order via nearest-neighbor from store
        if store_coords:
            cluster = _nearest_neighbor_order(cluster, store_coords)

        est_minutes = _estimate_route_minutes(cluster)

        stops = []
        for o in cluster:
            stops.append({
                'order_id': o['id'],
                'order_number': o.get('order_number', ''),
                'address': o.get('customer_address', ''),
                'customer_name': o.get('customer_name', ''),
                'lat': o.get('lat'),
                'lng': o.get('lng'),
                'status': 'pending',
            })

        routes.append({
            'driver': driver,
            'stops': stops,
            'estimated_duration_min': round(est_minutes, 1),
            'order_count': len(cluster),
        })

    return routes


# ---------------------------------------------------------------------------
#  Endpoints
# ---------------------------------------------------------------------------

@delivery_bp.route('/queue', methods=['GET'])
@login_required
@organization_required
def delivery_queue():
    """Pending delivery orders with priority scores."""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, order_number, order_type, status, customer_name, customer_phone,
               customer_address, delivery_distance, delivery_fee, total, notes,
               estimated_ready_time, actual_ready_time, created_at, driver_id,
               delivery_route_id, customer_lat, customer_lng, scheduled_for
        FROM orders
        WHERE order_type = 'delivery'
          AND status IN ('ready', 'confirmed', 'preparing', 'out_for_delivery')
          AND DATE(created_at) = DATE('now', 'localtime')
        ORDER BY created_at ASC
    """)
    rows = cursor.fetchall()
    cols = [d[0] for d in cursor.description]

    orders = []
    for row in rows:
        o = dict(zip(cols, row))
        o['priority_score'] = _priority_score(
            o['created_at'], o.get('delivery_distance'),
            scheduled_for_str=o.get('scheduled_for'))
        o['is_scheduled'] = bool(o.get('scheduled_for'))
        # Minutes waiting (or minutes until due for scheduled)
        created = _parse_dt(o['created_at']) or datetime.now()
        o['minutes_waiting'] = round((datetime.now() - created).total_seconds() / 60.0, 1)
        if o.get('scheduled_for'):
            scheduled = _parse_dt(o['scheduled_for'])
            if scheduled:
                o['minutes_until_due'] = round((scheduled - datetime.now()).total_seconds() / 60.0, 1)

        # Geocode if missing and address exists
        if not o.get('customer_lat') and o.get('customer_address'):
            lat, lng = _geocode_address(o['customer_address'])
            if lat and lng:
                o['customer_lat'] = lat
                o['customer_lng'] = lng
                cursor.execute(
                    "UPDATE orders SET customer_lat = ?, customer_lng = ? WHERE id = ?",
                    (lat, lng, o['id']))

        # Expose as lat/lng for frontend
        o['lat'] = o.get('customer_lat')
        o['lng'] = o.get('customer_lng')
        orders.append(o)

    conn.commit()

    # Sort by priority descending (highest priority first)
    orders.sort(key=lambda o: o['priority_score'], reverse=True)

    store_coords = _get_store_coords()

    return jsonify({'success': True, 'orders': orders, 'store_coords': store_coords})


@delivery_bp.route('/drivers', methods=['GET'])
@login_required
@organization_required
def available_drivers():
    """All clocked-in drivers with their availability status."""
    conn = get_org_db()
    cursor = conn.cursor()

    # Get all clocked-in drivers
    cursor.execute("""
        SELECT e.id, e.first_name, e.last_name, e.phone, e.position,
               a.clock_in
        FROM employees e
        JOIN attendance a ON a.employee_id = e.id
        WHERE e.is_driver = 1
          AND e.status = 'active'
          AND a.clock_out IS NULL
          AND DATE(a.clock_in) = DATE('now', 'localtime')
        GROUP BY e.id
        ORDER BY a.clock_in ASC
    """)
    rows = cursor.fetchall()
    cols = [d[0] for d in cursor.description]

    drivers = [dict(zip(cols, row)) for row in rows]

    # Check which drivers are on active routes
    cursor.execute("SELECT driver_id, id FROM delivery_routes WHERE status = 'active'")
    active_routes = {row[0]: row[1] for row in cursor.fetchall()}

    for d in drivers:
        if d['id'] in active_routes:
            d['is_dispatched'] = True
            d['active_route_id'] = active_routes[d['id']]
        else:
            d['is_dispatched'] = False
            d['active_route_id'] = None

    return jsonify({'success': True, 'drivers': drivers})


@delivery_bp.route('/routes/build', methods=['POST'])
@login_required
@organization_required
def build_routes():
    """Run optimizer — return proposed routes with ETAs. Does NOT persist."""
    conn = get_org_db()
    cursor = conn.cursor()

    # Get unassigned ready delivery orders
    cursor.execute("""
        SELECT id, order_number, customer_name, customer_address,
               delivery_distance, total, created_at, scheduled_for,
               customer_lat, customer_lng
        FROM orders
        WHERE order_type = 'delivery'
          AND status = 'ready'
          AND driver_id IS NULL
          AND DATE(created_at) = DATE('now', 'localtime')
        ORDER BY created_at ASC
    """)
    rows = cursor.fetchall()
    cols = [d[0] for d in cursor.description]
    orders = []
    for row in rows:
        o = dict(zip(cols, row))
        o['priority_score'] = _priority_score(
            o['created_at'], o.get('delivery_distance'),
            scheduled_for_str=o.get('scheduled_for'))
        # Estimate drive time from distance (rough: 2.5 min/mile in suburbs)
        dist = o.get('delivery_distance') or 3
        o['drive_time_min'] = round(dist * 2.5, 1)
        # Use cached coords if available
        o['lat'] = o.get('customer_lat')
        o['lng'] = o.get('customer_lng')
        orders.append(o)

    if not orders:
        return jsonify({'success': True, 'routes': [], 'message': 'No ready orders to route'})

    # Get available drivers
    cursor.execute("""
        SELECT e.id, e.first_name, e.last_name, e.phone
        FROM employees e
        JOIN attendance a ON a.employee_id = e.id
        WHERE e.is_driver = 1
          AND e.status = 'active'
          AND a.clock_out IS NULL
          AND DATE(a.clock_in) = DATE('now', 'localtime')
          AND e.id NOT IN (
              SELECT driver_id FROM delivery_routes WHERE status = 'active'
          )
        GROUP BY e.id
        ORDER BY a.clock_in ASC
    """)
    d_rows = cursor.fetchall()
    d_cols = [d[0] for d in cursor.description]
    drivers = [dict(zip(d_cols, r)) for r in d_rows]

    if not drivers:
        return jsonify({'success': True, 'routes': [], 'message': 'No available drivers'})

    store_coords = _get_store_coords()

    # Try to geocode orders and get real drive times via Distance Matrix
    if GOOGLE_MAPS_API_KEY and store_coords:
        store_str = f"{store_coords[0]},{store_coords[1]}"
        destinations = []
        for o in orders:
            lat, lng = _geocode_address(o['customer_address'])
            o['lat'] = lat
            o['lng'] = lng
            if lat and lng:
                destinations.append(f"{lat},{lng}")
            else:
                destinations.append(o.get('customer_address', ''))

        if destinations:
            matrix = _distance_matrix([store_str], destinations)
            if matrix and matrix[0].get('elements'):
                for i, elem in enumerate(matrix[0]['elements']):
                    if elem.get('status') == 'OK':
                        orders[i]['drive_time_min'] = round(
                            elem['duration']['value'] / 60.0, 1)

    proposed = _build_routes_for_orders(orders, drivers, store_coords)

    return jsonify({'success': True, 'routes': proposed, 'store_coords': store_coords})


@delivery_bp.route('/routes', methods=['POST'])
@login_required
@organization_required
def dispatch_route():
    """Confirm & dispatch a proposed route. Assigns driver, updates order statuses."""
    data = request.get_json()
    driver_id = data.get('driver_id')
    stops = data.get('stops', [])
    estimated_duration = data.get('estimated_duration_min')

    if not driver_id or not stops:
        return jsonify({'success': False, 'error': 'driver_id and stops required'}), 400

    conn = get_org_db()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Create route record (explicit created_at in local time to match date filters)
    cursor.execute("""
        INSERT INTO delivery_routes (driver_id, status, stops, estimated_duration_min, started_at, created_at)
        VALUES (?, 'active', ?, ?, ?, ?)
    """, (driver_id, json.dumps(stops), estimated_duration, now, now))
    route_id = cursor.lastrowid

    # Update each order
    order_ids = [s['order_id'] for s in stops if s.get('order_id')]
    for oid in order_ids:
        cursor.execute("""
            UPDATE orders
            SET status = 'out_for_delivery', driver_id = ?, dispatched_at = ?,
                delivery_route_id = ?, updated_at = ?
            WHERE id = ?
        """, (driver_id, now, route_id, now, oid))

    conn.commit()

    return jsonify({'success': True, 'route_id': route_id})


@delivery_bp.route('/routes', methods=['GET'])
@login_required
@organization_required
def list_routes():
    """Active + recent routes for today."""
    conn = get_org_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT dr.id, dr.driver_id, dr.status, dr.stops,
               dr.estimated_duration_min, dr.actual_duration_min,
               dr.started_at, dr.completed_at, dr.created_at,
               e.first_name || ' ' || e.last_name AS driver_name
        FROM delivery_routes dr
        LEFT JOIN employees e ON e.id = dr.driver_id
        WHERE DATE(dr.created_at) = DATE('now', 'localtime')
        ORDER BY
            CASE dr.status WHEN 'active' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
            dr.created_at DESC
    """)
    rows = cursor.fetchall()
    cols = [d[0] for d in cursor.description]

    routes = []
    for row in rows:
        r = dict(zip(cols, row))
        r['stops'] = json.loads(r['stops']) if r['stops'] else []
        routes.append(r)

    return jsonify({'success': True, 'routes': routes})


@delivery_bp.route('/routes/<int:route_id>/complete', methods=['POST'])
@login_required
@organization_required
def complete_route(route_id):
    """Mark route done, driver returns to available pool."""
    conn = get_org_db()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Get route to calculate actual duration
    cursor.execute("SELECT started_at, stops FROM delivery_routes WHERE id = ?", (route_id,))
    route = cursor.fetchone()
    if not route:
        return jsonify({'success': False, 'error': 'Route not found'}), 404

    actual_min = None
    if route[0]:
        try:
            started = datetime.strptime(route[0], '%Y-%m-%d %H:%M:%S')
            actual_min = round((datetime.now() - started).total_seconds() / 60.0, 1)
        except (ValueError, TypeError):
            pass

    cursor.execute("""
        UPDATE delivery_routes
        SET status = 'completed', completed_at = ?, actual_duration_min = ?
        WHERE id = ?
    """, (now, actual_min, route_id))

    # Mark any remaining stops as delivered
    stops = json.loads(route[1]) if route[1] else []
    for stop in stops:
        oid = stop.get('order_id')
        if oid:
            cursor.execute("""
                UPDATE orders SET status = 'delivered', delivered_at = ?, updated_at = ?
                WHERE id = ? AND status = 'out_for_delivery'
            """, (now, now, oid))

    conn.commit()

    return jsonify({'success': True, 'actual_duration_min': actual_min})


@delivery_bp.route('/orders/<int:order_id>/delivered', methods=['POST'])
@login_required
@organization_required
def mark_delivered(order_id):
    """Mark a single delivery stop as delivered."""
    conn = get_org_db()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("""
        UPDATE orders SET status = 'delivered', delivered_at = ?, updated_at = ?
        WHERE id = ? AND order_type = 'delivery'
    """, (now, now, order_id))

    if cursor.rowcount == 0:
        return jsonify({'success': False, 'error': 'Order not found'}), 404

    # Update the stop status in the route's JSON
    cursor.execute("""
        SELECT delivery_route_id FROM orders WHERE id = ?
    """, (order_id,))
    route_row = cursor.fetchone()
    if route_row and route_row[0]:
        route_id = route_row[0]
        cursor.execute("SELECT stops FROM delivery_routes WHERE id = ?", (route_id,))
        stops_row = cursor.fetchone()
        if stops_row and stops_row[0]:
            stops = json.loads(stops_row[0])
            for stop in stops:
                if stop.get('order_id') == order_id:
                    stop['status'] = 'delivered'
            cursor.execute(
                "UPDATE delivery_routes SET stops = ? WHERE id = ?",
                (json.dumps(stops), route_id))

            # Check if all stops are delivered — auto-complete route
            if all(s.get('status') == 'delivered' for s in stops):
                cursor.execute("SELECT started_at FROM delivery_routes WHERE id = ?", (route_id,))
                r = cursor.fetchone()
                actual_min = None
                if r and r[0]:
                    try:
                        started = datetime.strptime(r[0], '%Y-%m-%d %H:%M:%S')
                        actual_min = round((datetime.now() - started).total_seconds() / 60.0, 1)
                    except (ValueError, TypeError):
                        pass
                cursor.execute("""
                    UPDATE delivery_routes
                    SET status = 'completed', completed_at = ?, actual_duration_min = ?
                    WHERE id = ?
                """, (now, actual_min, route_id))

    conn.commit()

    return jsonify({'success': True})
