interface Measurement {
  parameter: string;
  value: number | string;
  unit?: string;
  normalRange?: string;
  status?: 'normal' | 'warning' | 'critical';
}

interface MeasurementsTableProps {
  measurements: Measurement[];
  title?: string;
}

export function MeasurementsTable({ measurements, title = 'Mediciones' }: MeasurementsTableProps) {
  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'normal':
        return 'text-green-400';
      case 'warning':
        return 'text-yellow-400';
      case 'critical':
        return 'text-red-400';
      default:
        return 'text-gray-300';
    }
  };

  const getStatusBadge = (status?: string) => {
    if (!status) return null;

    const colors = {
      normal: 'bg-green-900 text-green-300 border-green-700',
      warning: 'bg-yellow-900 text-yellow-300 border-yellow-700',
      critical: 'bg-red-900 text-red-300 border-red-700',
    };

    const labels = {
      normal: 'Normal',
      warning: 'Advertencia',
      critical: 'Crítico',
    };

    return (
      <span className={`px-2 py-1 rounded text-xs border ${colors[status]}`}>
        {labels[status]}
      </span>
    );
  };

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
      <div className="bg-gray-800 px-4 py-3 border-b border-gray-700">
        <h3 className="text-sm text-gray-200">{title}</h3>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-800 border-b border-gray-700">
            <tr>
              <th className="px-4 py-2 text-left text-xs text-gray-400">Parámetro</th>
              <th className="px-4 py-2 text-right text-xs text-gray-400">Valor</th>
              <th className="px-4 py-2 text-left text-xs text-gray-400">Rango normal</th>
              <th className="px-4 py-2 text-center text-xs text-gray-400">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {measurements.map((measurement, index) => (
              <tr key={index} className="hover:bg-gray-800/50 transition-colors">
                <td className="px-4 py-3 text-sm text-gray-300">
                  {measurement.parameter}
                </td>
                <td className={`px-4 py-3 text-sm text-right ${getStatusColor(measurement.status)}`}>
                  {measurement.value}
                  {measurement.unit && (
                    <span className="ml-1 text-gray-500">{measurement.unit}</span>
                  )}
                </td>
                <td className="px-4 py-3 text-sm text-gray-400">
                  {measurement.normalRange || '-'}
                </td>
                <td className="px-4 py-3 text-center">
                  {getStatusBadge(measurement.status)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
