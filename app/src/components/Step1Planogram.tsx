import React, { useState } from 'react';
import { PlanogramItem, Bay } from '../types';
import { Search } from 'lucide-react';

interface Step1PlanogramProps {
  bay: Bay;
  items: PlanogramItem[];
  highlightedSku?: string | null;
  onSelectSku?: (sku: string) => void;
}

export const Step1Planogram: React.FC<Step1PlanogramProps> = ({
  bay,
  items,
  highlightedSku,
  onSelectSku,
}) => {
  const [filter, setFilter] = useState<'all' | 'stocked' | 'phantom'>('all');
  const [search, setSearch] = useState('');

  const filteredItems = items.filter((item) => {
    const matchesSearch =
      item.title.toLowerCase().includes(search.toLowerCase()) ||
      (item.author && item.author.toLowerCase().includes(search.toLowerCase())) ||
      item.sku.toLowerCase().includes(search.toLowerCase());

    if (!matchesSearch) return false;
    if (filter === 'stocked') return item.simulated_on_hand > 0;
    if (filter === 'phantom') return item.system_status === 'phantom';
    return true;
  });

  const totalAssigned = items.length;
  const inStockRecord = items.filter((i) => i.simulated_on_hand > 0).length;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden flex flex-col h-full">
      {/* Step Header */}
      <div className="p-4 border-b border-slate-100 bg-slate-50/70">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold">
              1
            </span>
            <h2 className="text-sm font-bold text-slate-900 tracking-tight">Demo Shelf Catalogue</h2>
          </div>
          <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-200/70 text-slate-700">
            {bay.code} · {bay.section}
          </span>
        </div>
        <p className="text-xs text-slate-500">
          Simulated title assignments for this shelf. Exact slot positions and physical copy counts are not specified.
        </p>

        {/* Quick KPI stats */}
        <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-200/60">
          <div className="bg-white p-2.5 rounded-lg border border-slate-200/80">
            <div className="text-xs text-slate-500 font-medium">Assigned Titles</div>
            <div className="text-lg font-bold text-slate-900 tabular-nums">{totalAssigned}</div>
          </div>
          <div className="bg-white p-2.5 rounded-lg border border-slate-200/80">
            <div className="text-xs text-slate-500 font-medium">Titles with Stock Records</div>
            <div className="text-lg font-bold text-blue-600 tabular-nums">{inStockRecord} in stock</div>
          </div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="p-3 border-b border-slate-100 bg-white flex flex-col sm:flex-row gap-2">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
          <input
            type="text"
            aria-label="Search shelf catalogue" placeholder="Search titles, authors, SKU…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-md focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div className="flex space-x-1">
          <button
            onClick={() => setFilter('all')}
            className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
              filter === 'all'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            All ({items.length})
          </button>
          <button
            onClick={() => setFilter('stocked')}
            className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
              filter === 'stocked'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Record &gt; 0
          </button>
        </div>
      </div>

      {/* Planogram Items List */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-100 max-h-64 lg:max-h-[580px]">
        {filteredItems.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">No matching planogram titles found.</div>
        ) : (
          filteredItems.map((item) => {
            const isHighlighted = highlightedSku === item.sku;
            const isZeroRecord = item.simulated_on_hand === 0;

            return (
              <div
                key={item.sku}
                onClick={() => onSelectSku && onSelectSku(item.sku)}
                className={`p-3 transition-colors cursor-pointer text-left ${
                  isHighlighted
                    ? 'bg-blue-50/80 border-l-4 border-blue-600'
                    : 'hover:bg-slate-50/80'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="pr-2 flex-1">
                    <div className="text-xs font-semibold text-slate-900 line-clamp-1">{item.title}</div>
                    <div className="text-xs text-slate-500 line-clamp-1">{item.author || 'Author unspecified'}</div>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-[10px] font-mono text-slate-400">{item.sku}</span>
                      <span className="text-[10px] font-semibold text-slate-600">${item.price.toFixed(2)}</span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold tabular-nums ${
                        isZeroRecord
                          ? 'bg-slate-100 text-slate-500 border border-slate-200'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      }`}
                    >
                      {item.simulated_on_hand} in record
                    </span>
                    <div className="text-[10px] text-slate-400 mt-1">
                      {item.sales_velocity_units_per_day} units/day
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer Note */}
      <div className="p-2.5 bg-slate-50 border-t border-slate-200 text-center">
        <span className="text-[11px] text-slate-500 font-medium">
          Source: Simulated demo catalogue · No live ERP connection
        </span>
      </div>
    </div>
  );
};
