interface BboxHighlightProps {
  bbox: [number, number, number, number]
  scaleFactor: number
}

export function BboxHighlight({ bbox, scaleFactor }: BboxHighlightProps) {
  const [x0, y0, x1, y1] = bbox

  return (
    <div
      style={{
        position: 'absolute',
        left: x0 * scaleFactor,
        top: y0 * scaleFactor,
        width: (x1 - x0) * scaleFactor,
        height: (y1 - y0) * scaleFactor,
        backgroundColor: 'rgba(250, 204, 21, 0.3)',
        border: '2px solid rgba(250, 204, 21, 0.6)',
        borderRadius: 2,
        pointerEvents: 'none',
        zIndex: 10,
      }}
    />
  )
}
