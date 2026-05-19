interface SpineDiagramProps {
  highlightedVertebrae?: string[];
  curveType?: string;
}

export function SpineDiagram({ highlightedVertebrae = [], curveType }: SpineDiagramProps) {
  const vertebrae = [
    { id: 'C1', label: 'C1', y: 50 },
    { id: 'C2', label: 'C2', y: 70 },
    { id: 'C3', label: 'C3', y: 90 },
    { id: 'C4', label: 'C4', y: 110 },
    { id: 'C5', label: 'C5', y: 130 },
    { id: 'C6', label: 'C6', y: 150 },
    { id: 'C7', label: 'C7', y: 170 },
    { id: 'T1', label: 'T1', y: 200 },
    { id: 'T2', label: 'T2', y: 220 },
    { id: 'T3', label: 'T3', y: 240 },
    { id: 'T4', label: 'T4', y: 260 },
    { id: 'T5', label: 'T5', y: 280 },
    { id: 'T6', label: 'T6', y: 300 },
    { id: 'T7', label: 'T7', y: 320 },
    { id: 'T8', label: 'T8', y: 340 },
    { id: 'T9', label: 'T9', y: 360 },
    { id: 'T10', label: 'T10', y: 380 },
    { id: 'T11', label: 'T11', y: 400 },
    { id: 'T12', label: 'T12', y: 420 },
    { id: 'L1', label: 'L1', y: 450 },
    { id: 'L2', label: 'L2', y: 475 },
    { id: 'L3', label: 'L3', y: 500 },
    { id: 'L4', label: 'L4', y: 525 },
    { id: 'L5', label: 'L5', y: 550 },
    { id: 'S1', label: 'S', y: 580 },
  ];

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm text-gray-200">Diagrama de columna</h3>
        {curveType ? (
          <span className="text-xs text-gray-400 uppercase tracking-[0.12em]">
            {curveType}
          </span>
        ) : null}
      </div>
      <div className="flex justify-center">
        <svg width="200" height="620" viewBox="0 0 200 620">
          <defs>
            <linearGradient id="spineGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.3" />
            </linearGradient>
          </defs>

          <path
            d="M 100 40 Q 90 200 100 360 Q 110 520 100 600"
            stroke="url(#spineGradient)"
            strokeWidth="8"
            fill="none"
            strokeLinecap="round"
          />

          {vertebrae.map((vertebra) => {
            const isHighlighted = highlightedVertebrae.includes(vertebra.id);
            return (
              <g key={vertebra.id}>
                <circle
                  cx="100"
                  cy={vertebra.y}
                  r={isHighlighted ? 8 : 6}
                  fill={isHighlighted ? '#3b82f6' : '#6b7280'}
                  stroke={isHighlighted ? '#60a5fa' : '#9ca3af'}
                  strokeWidth={isHighlighted ? 2 : 1}
                  className="transition-all"
                />
                <text
                  x={vertebra.id.startsWith('C') ? 70 : 130}
                  y={vertebra.y + 4}
                  fontSize="10"
                  fill={isHighlighted ? '#60a5fa' : '#9ca3af'}
                  textAnchor={vertebra.id.startsWith('C') ? 'end' : 'start'}
                  className="transition-colors"
                >
                  {vertebra.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
