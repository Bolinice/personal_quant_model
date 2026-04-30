import React from 'react';

interface FactorHeatmapProps {
  data: Array<{
    factor1: string;
    factor2: string;
    correlation: number;
  }>;
  height?: number;
  title?: string;
}

// Recharts doesn't have native heatmap, use a simple grid rendering
const FactorHeatmap: React.FC<FactorHeatmapProps> = ({ data, title }) => {
  if (!data.length) return null;

  const factors = [...new Set(data.flatMap((d) => [d.factor1, d.factor2]))];
  const cellSize = Math.min(60, 400 / factors.length);

  const getColor = (value: number) => {
    const absVal = Math.abs(value);
    if (value > 0) {
      const intensity = Math.min(absVal, 1);
      return `rgba(24, 144, 255, ${intensity})`;
    }
    const intensity = Math.min(absVal, 1);
    return `rgba(245, 34, 45, ${intensity})`;
  };

  return (
    <div>
      {title && <h4 style={{ marginBottom: 8 }}>{title}</h4>}
      <div style={{ overflow: 'auto' }}>
        <svg width={factors.length * cellSize + 80} height={factors.length * cellSize + 30}>
          {data.map((item, i) => {
            const x = factors.indexOf(item.factor1) * cellSize + 80;
            const y = factors.indexOf(item.factor2) * cellSize + 30;
            return (
              <g key={i}>
                <rect
                  x={x}
                  y={y}
                  width={cellSize - 1}
                  height={cellSize - 1}
                  fill={getColor(item.correlation)}
                  rx={2}
                />
                <text
                  x={x + cellSize / 2}
                  y={y + cellSize / 2}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize={10}
                  fill="#333"
                >
                  {item.correlation.toFixed(2)}
                </text>
              </g>
            );
          })}
          {factors.map((f, i) => (
            <React.Fragment key={`label-${f}`}>
              <text
                x={80 + i * cellSize + cellSize / 2}
                y={20}
                textAnchor="middle"
                fontSize={9}
                fill="#666"
                transform={`rotate(-45, ${80 + i * cellSize + cellSize / 2}, 20)`}
              >
                {f.slice(0, 8)}
              </text>
              <text
                x={75}
                y={30 + i * cellSize + cellSize / 2}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize={9}
                fill="#666"
              >
                {f.slice(0, 8)}
              </text>
            </React.Fragment>
          ))}
        </svg>
      </div>
    </div>
  );
};

export default FactorHeatmap;
