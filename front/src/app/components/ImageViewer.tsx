import { useState } from 'react';
import { ZoomIn, ZoomOut, RotateCw } from 'lucide-react';

interface ImageViewerProps {
  src: string;
  alt: string;
  title?: string;
  showControls?: boolean;
}

export function ImageViewer({ src, alt, title, showControls = true }: ImageViewerProps) {
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);

  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.25, 3));
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 0.25, 0.5));
  const handleRotate = () => setRotation(prev => (prev + 90) % 360);

  return (
    <div className="bg-gray-900 rounded-lg overflow-hidden border border-gray-700">
      {title && (
        <div className="bg-gray-800 px-4 py-2 border-b border-gray-700">
          <h3 className="text-sm text-gray-200">{title}</h3>
        </div>
      )}

      <div className="relative aspect-[3/4] flex items-center justify-center overflow-hidden">
        <img
          src={src}
          alt={alt}
          className="max-w-full max-h-full object-contain transition-transform"
          style={{
            transform: `scale(${zoom}) rotate(${rotation}deg)`,
          }}
        />
      </div>

      {showControls && (
        <div className="bg-gray-800 px-4 py-2 flex items-center justify-center gap-2 border-t border-gray-700">
          <button
            onClick={handleZoomOut}
            className="p-2 hover:bg-gray-700 rounded transition-colors"
            title="Zoom out"
          >
            <ZoomOut className="w-4 h-4 text-gray-300" />
          </button>
          <span className="text-xs text-gray-400 min-w-[60px] text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={handleZoomIn}
            className="p-2 hover:bg-gray-700 rounded transition-colors"
            title="Zoom in"
          >
            <ZoomIn className="w-4 h-4 text-gray-300" />
          </button>
          <div className="w-px h-4 bg-gray-600 mx-2" />
          <button
            onClick={handleRotate}
            className="p-2 hover:bg-gray-700 rounded transition-colors"
            title="Rotate"
          >
            <RotateCw className="w-4 h-4 text-gray-300" />
          </button>
        </div>
      )}
    </div>
  );
}
