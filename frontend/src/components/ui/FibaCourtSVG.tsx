/**
 * FibaCourtSVG — official FIBA half-court rendered in SVG.
 *
 * Dimensions follow FIBA 2020 rules, scale factor 30 px / metre.
 * The court is drawn with the basket at the BOTTOM (baseline) and
 * half-court line at the TOP, matching the standard shot-chart orientation.
 *
 * Props
 * -----
 * zones          – Optional array of zone stats for heatmap overlay.
 *                  Each entry has `zone`, `fga`, `fgm`, `fg_pct`.
 * onZoneClick    – Called with the zone key when a heatmap bubble is clicked.
 * highlightZone  – Key of the zone to highlight with a ring.
 * width / height – Override the default SVG size (default: 450 × 420).
 */
import { useMemo, type RefObject } from 'react'
import type { ShotZoneData, ShotRawData } from '@/api/client'

// ---------------------------------------------------------------------------
// Court geometry (all measurements in SVG pixels, 1 px = 1/30 m)
// ---------------------------------------------------------------------------
const S = 30                    // scale: 30 px = 1 m

const CW   = 15 * S             // 450 — court width
const CH   = 14 * S             // 420 — court height (half court)
const BX   = 7.5 * S            // 225 — basket centre x
const BY   = (14 - 1.575) * S   // 373.25 — basket centre y in SVG
const BBY  = (14 - 1.2) * S     // 384 — backboard y
const RR   = 1.25 * S           // 37.5 — restricted area radius
const KL   = (7.5 - 2.45) * S  // 151.5 — key left x
const KR   = (7.5 + 2.45) * S  // 298.5 — key right x
const KT   = (14 - 5.8) * S    // 246   — key top y
const FTR  = 1.8 * S            // 54    — free-throw circle radius
const CL   = 0.9 * S            // 27    — 3pt corner left x
const CR   = 14.1 * S           // 423   — 3pt corner right x
const TR   = 6.75 * S           // 202.5 — 3pt radius
// break: y_fiba where the straight 3pt side meets the arc
const BREAK_FIBA = 1.575 + Math.sqrt(6.75 ** 2 - (7.5 - 0.9) ** 2) // ≈ 2.99 m
const BRK  = (14 - BREAK_FIBA) * S   // ≈ 330.3 — break y in SVG

// ---------------------------------------------------------------------------
// Zone metadata: approximate bubble centre in SVG pixels
// ---------------------------------------------------------------------------
const ZONE_CENTERS: Record<string, { x: number; y: number; label: string }> = {
  restricted_area: { x: BX,       y: (14 - 2.0) * S,  label: 'Zona Restringida'   },
  paint:           { x: BX,       y: (14 - 3.8) * S,  label: 'Pintura'            },
  mid_left:        { x: 3.2 * S,  y: (14 - 4.0) * S,  label: 'Media Izq.'         },
  mid_center:      { x: BX,       y: (14 - 6.5) * S,  label: 'Media Centro'       },
  mid_right:       { x: 11.8 * S, y: (14 - 4.0) * S,  label: 'Media Der.'         },
  corner_left:     { x: 0.45 * S, y: (14 - 1.5) * S,  label: 'Triple Esq. Izq'   },
  wing_left:       { x: 2.0 * S,  y: (14 - 5.5) * S,  label: 'Triple Ala Izq'    },
  top_three:       { x: BX,       y: (14 - 9.0) * S,  label: 'Triple Centro'      },
  wing_right:      { x: 13.0 * S, y: (14 - 5.5) * S,  label: 'Triple Ala Der'    },
  corner_right:    { x: 14.55 * S,y: (14 - 1.5) * S,  label: 'Triple Esq. Der'   },
}

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------

/** Map FG% (0-100) to an HSL colour (red → yellow → green). */
function pctColor(pct: number): string {
  const clamped = Math.max(0, Math.min(100, pct))
  // 0 % → hue 0 (red), 40 % → hue 120 (green)
  const hue = Math.round((clamped / 40) * 120)
  return `hsl(${Math.min(hue, 120)}, 85%, 42%)`
}

/** Compute bubble radius based on shot volume. */
function bubbleRadius(fga: number, maxFga: number): number {
  if (maxFga === 0) return 12
  const min = 10, max = 36
  return min + ((fga / maxFga) ** 0.5) * (max - min)
}

// ---------------------------------------------------------------------------
// Props & component
// ---------------------------------------------------------------------------

interface Props {
  zones?: ShotZoneData[]
  onZoneClick?: (zone: string) => void
  highlightZone?: string | null
  width?: number
  height?: number
  svgRef?: RefObject<SVGSVGElement>
  /** Visualization layer: 'zones' (default), 'scatter', or 'heatmap'. */
  vizMode?: 'zones' | 'scatter' | 'heatmap'
  /** Individual shot records used for scatter / heatmap modes. */
  rawShots?: ShotRawData[]
}

const LINE = '#cccccc'
const LINE_W = 2

export default function FibaCourtSVG({
  zones,
  onZoneClick,
  highlightZone,
  width = CW,
  height = CH,
  svgRef,
  vizMode = 'zones',
  rawShots,
}: Props) {
  // Normalise zone data keyed by zone id
  const zoneMap = useMemo(() => {
    const m: Record<string, ShotZoneData> = {}
    zones?.forEach(z => { m[z.zone] = z })
    return m
  }, [zones])

  const maxFga = useMemo(() =>
    Math.max(1, ...Object.values(zoneMap).map(z => z.fga)),
  [zoneMap])

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${CW} ${CH}`}
      width={width}
      height={height}
      className="select-none"
      style={{ background: '#1a1a2e' }}
    >
      {/* Half-court line */}
      <line x1={0} y1={0} x2={CW} y2={0} stroke={LINE} strokeWidth={LINE_W} />
      {/* Side lines */}
      <line x1={0}  y1={0} x2={0}  y2={CH} stroke={LINE} strokeWidth={LINE_W} />
      <line x1={CW} y1={0} x2={CW} y2={CH} stroke={LINE} strokeWidth={LINE_W} />
      {/* Baseline */}
      <line x1={0} y1={CH} x2={CW} y2={CH} stroke={LINE} strokeWidth={LINE_W} />

      {/* Key (paint rectangle) */}
      <rect x={KL} y={KT} width={KR - KL} height={CH - KT}
        fill="rgba(59,130,246,0.06)" stroke={LINE} strokeWidth={LINE_W} />

      {/* Free-throw semi-circles — centred on basket x with correct radius */}
      {/* Top half (solid) — faces midcourt */}
      <path
        d={`M ${BX - FTR},${KT} A ${FTR},${FTR} 0 0,1 ${BX + FTR},${KT}`}
        fill="none" stroke={LINE} strokeWidth={LINE_W}
      />
      {/* Bottom half (dashed) — faces basket */}
      <path
        d={`M ${BX - FTR},${KT} A ${FTR},${FTR} 0 0,0 ${BX + FTR},${KT}`}
        fill="none" stroke={LINE} strokeWidth={LINE_W} strokeDasharray="5,4"
      />

      {/* 3-point line */}
      {/* Left straight segment */}
      <line x1={CL} y1={CH} x2={CL} y2={BRK} stroke={LINE} strokeWidth={LINE_W} />
      {/* Right straight segment */}
      <line x1={CR} y1={CH} x2={CR} y2={BRK} stroke={LINE} strokeWidth={LINE_W} />
      {/* Arc from left break to right break */}
      <path
        d={`M ${CL},${BRK} A ${TR},${TR} 0 0,1 ${CR},${BRK}`}
        fill="none" stroke={LINE} strokeWidth={LINE_W}
      />

      {/* Restricted area */}
      {/* Left vertical line: arc end down to baseline */}
      <line x1={BX - RR} y1={BY} x2={BX - RR} y2={CH} stroke={LINE} strokeWidth={LINE_W} />
      {/* Arc — semicircle open toward baseline (curving toward midcourt) */}
      <path
        d={`M ${BX - RR},${BY} A ${RR},${RR} 0 0,1 ${BX + RR},${BY}`}
        fill="none" stroke={LINE} strokeWidth={LINE_W}
      />
      {/* Right vertical line: arc end down to baseline */}
      <line x1={BX + RR} y1={BY} x2={BX + RR} y2={CH} stroke={LINE} strokeWidth={LINE_W} />

      {/* Backboard */}
      <line x1={BX - 27} y1={BBY} x2={BX + 27} y2={BBY} stroke={LINE} strokeWidth={LINE_W + 1} />

      {/* Hoop */}
      <circle cx={BX} cy={BY} r={6.75} fill="none" stroke="#ff8c00" strokeWidth={2} />

      {/* ── Heatmap overlay — two-layer screen-blend for wide contrast ── */}
      {/* screen() on a dark background compounds additively: sparse zones stay  */}
      {/* cool-blue, medium zones turn orange, dense zones saturate to yellow.  */}
      {vizMode === 'heatmap' && rawShots && rawShots.length > 0 && (
        <>
          <defs>
            {/* Wide spread: reveals density shape across the court */}
            <filter id="heat-wide" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="22" />
            </filter>
            {/* Tight: concentrates heat on the exact hotspots */}
            <filter id="heat-tight" x="-15%" y="-15%" width="130%" height="130%">
              <feGaussianBlur stdDeviation="9" />
            </filter>
          </defs>
          {/* Cool layer — blue, wide, shows general density shape */}
          <g filter="url(#heat-wide)" style={{ mixBlendMode: 'screen' }}>
            {rawShots.map((s, i) => (
              <circle key={`hw${i}`} cx={s.x * S} cy={(14 - s.y) * S} r={20}
                fill="rgba(40,90,255,0.22)" />
            ))}
          </g>
          {/* Hot layer — orange/yellow, tight, marks high-density spots */}
          <g filter="url(#heat-tight)" style={{ mixBlendMode: 'screen' }}>
            {rawShots.map((s, i) => (
              <circle key={`hh${i}`} cx={s.x * S} cy={(14 - s.y) * S} r={15}
                fill="rgba(255,160,0,0.32)" />
            ))}
          </g>
        </>
      )}

      {/* ── Scatter overlay (individual shot dots) ── */}
      {vizMode === 'scatter' && rawShots && rawShots.length > 0 &&
        rawShots.map((s, i) => (
          <circle
            key={i}
            cx={s.x * S}
            cy={(14 - s.y) * S}
            r={4}
            fill={s.made ? '#4ade80' : '#f87171'}
            fillOpacity={0.65}
          />
        ))
      }

      {/* ── Zone heatmap bubbles — only in 'zones' mode ── */}
      {vizMode === 'zones' && zones && zones.length > 0 && Object.entries(ZONE_CENTERS).map(([zoneKey, center]) => {
        const zData = zoneMap[zoneKey]
        if (!zData || zData.fga === 0) return null

        const r  = bubbleRadius(zData.fga, maxFga)
        const color = pctColor(zData.fg_pct)
        const isHighlighted = highlightZone === zoneKey

        return (
          <g key={zoneKey}
            onClick={() => onZoneClick?.(zoneKey)}
            className={onZoneClick ? 'cursor-pointer' : ''}
          >
            <circle
              cx={center.x} cy={center.y} r={r}
              fill={color} fillOpacity={0.82}
              stroke={isHighlighted ? '#fff' : 'rgba(255,255,255,0.15)'}
              strokeWidth={isHighlighted ? 2.5 : 1}
            />
            <text x={center.x} y={center.y - 4} textAnchor="middle" fill="#fff"
              fontSize={11} fontWeight="bold">
              {zData.fg_pct.toFixed(0)}%
            </text>
            <text x={center.x} y={center.y + 9} textAnchor="middle" fill="rgba(255,255,255,0.7)"
              fontSize={9}>
              {zData.fga}T
            </text>
          </g>
        )
      })}

      {/* Empty-state zone placeholders — only in 'zones' mode when no data */}
      {vizMode === 'zones' && (!zones || zones.length === 0) && Object.entries(ZONE_CENTERS).map(([key, c]) => (
        <circle key={key} cx={c.x} cy={c.y} r={10}
          fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.08)" strokeWidth={1}
        />
      ))}
    </svg>
  )
}
