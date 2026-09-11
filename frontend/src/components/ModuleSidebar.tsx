import type { ModuleStatus, ModuleSummary } from '../types/api'

const STATUS_STYLES: Record<ModuleStatus, string> = {
  pending: 'bg-slate-100 text-slate-500',
  generating: 'bg-amber-100 text-amber-700',
  completed: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700',
}

interface ModuleSidebarProps {
  modules: ModuleSummary[]
  selectedModuleId: number | null
  onSelect: (moduleId: number) => void
}

export function ModuleSidebar({ modules, selectedModuleId, onSelect }: ModuleSidebarProps) {
  return (
    <nav className="w-64 shrink-0 border-r border-slate-200 bg-white">
      <ul className="divide-y divide-slate-100">
        {modules.map((module) => (
          <li key={module.id}>
            <button
              onClick={() => onSelect(module.id)}
              className={`block w-full px-4 py-3 text-left text-sm transition ${
                selectedModuleId === module.id ? 'bg-slate-100' : 'hover:bg-slate-50'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-800">
                  {module.order_index + 1}. {module.title}
                </span>
              </div>
              <span
                className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_STYLES[module.status]}`}
              >
                {module.status}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
