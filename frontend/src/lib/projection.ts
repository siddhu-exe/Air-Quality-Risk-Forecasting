export interface GeoPoint {
  lat: number
  lon: number
}

export interface MapBox {
  /** viewBox of the map artwork. */
  width: number
  height: number
  /** Space kept clear around the pins (room for labels and the river). */
  padding: { left: number; right: number; top: number; bottom: number }
}

export interface MapPosition {
  /** Percentage of the map width (0-100). */
  leftPct: number
  /** Pixels from the top of the map. */
  topPx: number
}

/** The stylised Delhi map in the design is 600 x 480 with room for labels. */
export const DELHI_MAP_BOX: MapBox = {
  width: 600,
  height: 480,
  padding: { left: 74, right: 80, top: 60, bottom: 90 },
}

/**
 * Fits the stations' bounding box into the padded map area (north is up).
 * A linear fit rather than true Mercator: across Delhi (~0.27 deg) the
 * difference is invisible, and the design's hand-placed pins match it.
 */
export function projectToMap(points: readonly GeoPoint[], box: MapBox = DELHI_MAP_BOX): MapPosition[] {
  if (points.length === 0) return []
  const lats = points.map((p) => p.lat)
  const lons = points.map((p) => p.lon)
  const minLat = Math.min(...lats)
  const maxLat = Math.max(...lats)
  const minLon = Math.min(...lons)
  const maxLon = Math.max(...lons)

  const innerW = box.width - box.padding.left - box.padding.right
  const innerH = box.height - box.padding.top - box.padding.bottom
  // A single point (or a degenerate span) sits in the middle instead of dividing by zero.
  const lonSpan = maxLon - minLon || 1
  const latSpan = maxLat - minLat || 1

  return points.map((p) => {
    const x = maxLon === minLon ? innerW / 2 : ((p.lon - minLon) / lonSpan) * innerW
    const y = maxLat === minLat ? innerH / 2 : ((maxLat - p.lat) / latSpan) * innerH
    return {
      leftPct: ((box.padding.left + x) / box.width) * 100,
      topPx: box.padding.top + y,
    }
  })
}
