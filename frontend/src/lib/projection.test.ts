import { DELHI_MAP_BOX, projectToMap } from './projection'

const bawana = { lat: 28.7762, lon: 77.05107 }
const anandVihar = { lat: 28.64683, lon: 77.31603 }
const rkPuram = { lat: 28.56326, lon: 77.18694 }

describe('projectToMap', () => {
  it('puts the extremes on the padded edges of the map, north up', () => {
    const [nw, e, s] = projectToMap([bawana, anandVihar, rkPuram])
    const { padding, width } = DELHI_MAP_BOX
    expect(nw?.leftPct).toBeCloseTo((padding.left / width) * 100)
    expect(nw?.topPx).toBe(padding.top)
    expect(e?.leftPct).toBeCloseTo(((width - padding.right) / width) * 100)
    expect(s?.topPx).toBe(DELHI_MAP_BOX.height - padding.bottom)
  })

  it('keeps stations ordered west-to-east and north-to-south', () => {
    const [a, b] = projectToMap([bawana, anandVihar])
    expect(b?.leftPct).toBeGreaterThan(a?.leftPct ?? Infinity)
    const [north, south] = projectToMap([bawana, rkPuram])
    expect(south?.topPx).toBeGreaterThan(north?.topPx ?? Infinity)
  })

  it('centres a single station instead of dividing by zero', () => {
    const [only] = projectToMap([bawana])
    expect(Number.isFinite(only?.leftPct)).toBe(true)
    expect(Number.isFinite(only?.topPx)).toBe(true)
  })

  it('returns nothing for no stations', () => {
    expect(projectToMap([])).toEqual([])
  })
})
