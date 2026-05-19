import { useState, useRef, useEffect } from 'react';
import { RotateCcw } from 'lucide-react';

interface HeatmapVisualizationProps {
  data?: number[][];
  title?: string;
}

export function HeatmapVisualization({
  data,
  title = 'Vista 3D - Análisis de calor'
}: HeatmapVisualizationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [rotation, setRotation] = useState(0);

  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    const rows = data?.length ?? 24;
    const cols = data?.[0]?.length ?? 12;
    const cellWidth = width / cols;
    const cellHeight = height / rows;

    const heatmapData = data ?? Array.from({ length: rows }, (_, row) =>
      Array.from({ length: cols }, (_, col) =>
        (Math.sin((row / rows) * Math.PI * 2 + rotation / 50) + 1) / 2
      )
    );

    for (let row = 0; row < heatmapData.length; row++) {
      for (let col = 0; col < (heatmapData[row]?.length ?? 0); col++) {
        const intensity = heatmapData[row][col] ?? 0;
        ctx.fillStyle = getHeatmapColor(intensity);
        ctx.fillRect(col * cellWidth, row * cellHeight, cellWidth, cellHeight);
      }
    }

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 1;

    for (let row = 1; row < rows; row++) {
      ctx.beginPath();
      ctx.moveTo(0, row * cellHeight);
      ctx.lineTo(width, row * cellHeight);
      ctx.stroke();
    }

    for (let col = 1; col < cols; col++) {
      ctx.beginPath();
      ctx.moveTo(col * cellWidth, 0);
      ctx.lineTo(col * cellWidth, height);
      ctx.stroke();
    }
  }, [data, rotation]);

  const getHeatmapColor = (value: number): string => {
    if (value < 0.2) return '#1e3a8a';
    if (value < 0.4) return '#3b82f6';
    if (value < 0.6) return '#10b981';
    if (value < 0.8) return '#fbbf24';
    return '#ef4444';
  };

  const handleReset = () => setRotation(0);

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
      <div className="bg-gray-800 px-4 py-3 border-b border-gray-700 flex items-center justify-between">
        <h3 className="text-sm text-gray-200">{title}</h3>
        <button
          onClick={handleReset}
          className="p-1.5 hover:bg-gray-700 rounded transition-colors"
          title="Resetear rotación"
        >
          <RotateCcw className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      <div className="p-4 bg-black">
        <canvas
          ref={canvasRef}
          width={400}
          height={500}
          className="w-full cursor-grab active:cursor-grabbing"
          onMouseDown={(e) => {
            const startX = e.clientX;
            const startRotation = rotation;

            const handleMouseMove = (moveEvent: MouseEvent) => {
              const delta = moveEvent.clientX - startX;
              setRotation(startRotation + delta * 0.5);
            };

            const handleMouseUp = () => {
              document.removeEventListener('mousemove', handleMouseMove);
              document.removeEventListener('mouseup', handleMouseUp);
            };

            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
          }}
        />
      </div>

      <div className="bg-gray-800 px-4 py-3 border-t border-gray-700">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-400">Menor intensidad</span>
          <div className="flex gap-1">
            <div className="w-8 h-3 bg-[#1e3a8a] rounded" />
            <div className="w-8 h-3 bg-[#3b82f6] rounded" />
            <div className="w-8 h-3 bg-[#10b981] rounded" />
            <div className="w-8 h-3 bg-[#fbbf24] rounded" />
            <div className="w-8 h-3 bg-[#ef4444] rounded" />
          </div>
          <span className="text-gray-400">Mayor intensidad</span>
        </div>
      </div>
    </div>
  );
}
