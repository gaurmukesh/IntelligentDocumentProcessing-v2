import { Outlet, NavLink } from 'react-router-dom'

const navItems = [
  { to: '/',                 label: 'Dashboard'         },
  { to: '/new-application',  label: 'New Application'   },
  { to: '/applications',     label: 'Applications'      },
  { to: '/pipeline-status',  label: 'Pipeline Status'   },
  { to: '/report',           label: 'Verification Report'},
]

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-60 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-6 py-5 border-b border-gray-200">
          <h1 className="text-lg font-bold text-gray-900">IDP</h1>
          <p className="text-xs text-gray-500 mt-0.5">Document Verification</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-8">
        <Outlet />
      </main>
    </div>
  )
}
