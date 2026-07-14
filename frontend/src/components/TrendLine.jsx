export default function TrendLine({
  points = [],
  id = 'trend-line',
  color = '#4f6ef7',
  height = 180,
  compact = false,
  ariaLabel = '趋势折线图',
}) {
  const width = compact ? 260 : 720;
  const padding = compact ? 10 : 34;
  const safePoints = points.length > 0 ? points : [{ label: '-', value: 0 }];
  const values = safePoints.map((point) => point.value);
  const minValue = compact ? Math.max(0, Math.min(...values) - 8) : 0;
  const maxValue = compact ? Math.min(100, Math.max(...values) + 8) : 100;
  const range = Math.max(1, maxValue - minValue);
  const chartWidth = width - padding * 2;
  const chartHeight = height - padding * 2;
  const gradientId = `${id.replace(/[^a-zA-Z0-9-_]/g, '-')}-gradient`;

  const coordinates = safePoints.map((point, index) => {
    const x =
      safePoints.length === 1
        ? width / 2
        : padding + (chartWidth * index) / (safePoints.length - 1);
    const y = padding + ((maxValue - point.value) / range) * chartHeight;

    return { ...point, x, y };
  });

  const linePoints = coordinates
    .map((point) => `${point.x},${point.y}`)
    .join(' ');
  const areaPoints = [
    `${coordinates[0].x},${height - padding}`,
    linePoints,
    `${coordinates[coordinates.length - 1].x},${height - padding}`,
  ].join(' ');

  return (
    <div
      className={`trend-line-chart${compact ? ' trend-line-compact' : ''}`}
      style={{ height }}
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={ariaLabel}
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.22" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>

        {!compact &&
          [0, 25, 50, 75, 100].map((tick) => {
            const y = padding + ((maxValue - tick) / range) * chartHeight;

            return (
              <g key={tick}>
                <line
                  className="trend-line-grid"
                  x1={padding}
                  x2={width - padding}
                  y1={y}
                  y2={y}
                />
                <text
                  className="trend-line-axis-label"
                  x={padding - 10}
                  y={y + 4}
                  textAnchor="end"
                >
                  {tick}
                </text>
              </g>
            );
          })}

        <polygon points={areaPoints} fill={`url(#${gradientId})`} />
        <polyline
          points={linePoints}
          fill="none"
          stroke={color}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={compact ? 4 : 3}
        />

        {coordinates.map((point, index) => (
          <g key={`${point.label}-${point.value}`}>
            {!compact && (
              <text
                className="trend-line-axis-label"
                x={point.x}
                y={height - 8}
                textAnchor="middle"
              >
                {point.label.slice(5)}
              </text>
            )}
            <circle
              cx={point.x}
              cy={point.y}
              r={compact ? 0 : index === coordinates.length - 1 ? 5 : 3.5}
              fill="#ffffff"
              stroke={color}
              strokeWidth={2}
            />
          </g>
        ))}
      </svg>
    </div>
  );
}
