interface Props {
  data: { year: number; month: number; return_pct: number }[];
}

const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

function getColor(val: number): string {
  if (val > 5) return 'bg-green-600 text-white';
  if (val > 2) return 'bg-green-400 text-white';
  if (val > 0) return 'bg-green-100 text-green-900';
  if (val === 0) return 'bg-gray-100 text-gray-500';
  if (val > -2) return 'bg-red-100 text-red-900';
  if (val > -5) return 'bg-red-400 text-white';
  return 'bg-red-600 text-white';
}

export default function MonthlyHeatmap({ data }: Props) {
  if (!data.length) {
    return <div className="text-gray-400 text-sm py-12 text-center">No monthly data.</div>;
  }

  const years = Array.from(new Set(data.map((d) => d.year))).sort();
  const lookup = new Map(data.map((d) => [`${d.year}-${d.month}`, d.return_pct]));

  return (
    <div className="overflow-x-auto thin-scroll">
      <table className="text-xs w-full min-w-[520px] border-separate border-spacing-1">
        <thead>
          <tr>
            <th className="p-1 w-10"></th>
            {MONTHS.map((m) => (
              <th key={m} className="p-1 text-center text-gray-500 font-medium">
                {m}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {years.map((year) => (
            <tr key={year}>
              <td className="p-1 font-medium text-gray-600 text-right">{year}</td>
              {Array.from({ length: 12 }, (_, i) => {
                const val = lookup.get(`${year}-${i + 1}`);
                return (
                  <td
                    key={i}
                    className={`p-1.5 text-center rounded font-medium ${
                      val !== undefined ? getColor(val) : 'bg-gray-50 text-gray-300'
                    }`}
                  >
                    {val !== undefined
                      ? `${val > 0 ? '+' : ''}${val.toFixed(1)}%`
                      : '—'}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
