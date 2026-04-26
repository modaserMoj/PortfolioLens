import { Link, NavLink, useLocation } from 'react-router-dom';
import { BarChart3 } from 'lucide-react';
import { clsx } from 'clsx';

const TABS = [
  { to: '', label: 'Dashboard', end: true },
  { to: '/risk', label: 'Risk' },
  { to: '/trades', label: 'Trades' },
  { to: '/insights', label: 'Insights' },
  { to: '/progress', label: 'Progress' },
];

export default function Navbar() {
  const { pathname, search } = useLocation();
  const match = pathname.match(/^\/portfolio\/([^/]+)/);
  const id = match?.[1];
  const params = new URLSearchParams(search);
  const hasPrevious = Boolean(params.get('previous'));
  const visibleTabs = hasPrevious ? TABS : TABS.filter((tab) => tab.label !== 'Progress');

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <Link
          to="/"
          className="flex items-center gap-2 text-xl font-bold text-primary-700"
        >
          <BarChart3 size={22} />
          <span>PortfolioLens</span>
        </Link>

        {id && (
          <div className="flex gap-1 text-sm font-medium">
            {visibleTabs.map((tab) => (
              <NavLink
                key={tab.label}
                to={{
                  pathname: `/portfolio/${id}${tab.to}`,
                  search,
                }}
                end={tab.end}
                className={({ isActive }) =>
                  clsx(
                    'px-3 py-1.5 rounded-md transition-colors',
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:text-primary-700 hover:bg-gray-100',
                  )
                }
              >
                {tab.label}
              </NavLink>
            ))}
          </div>
        )}
      </div>
    </nav>
  );
}
