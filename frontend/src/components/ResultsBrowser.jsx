import React, { useState, useEffect } from 'react';
import axios from 'axios';

// Status legend definitions — what each tag means
const STATUS_LEGEND = [
  {
    key: 'Settled',
    color: '#047857',
    bg: '#D1FAE5',
    border: '#10b981',
    icon: '✓',
    title: 'Settled',
    desc: 'Transaction confirmed in all present sources. PG is settled, AFC gate scan recorded. No action needed.',
  },
  {
    key: 'Liable for Refund',
    color: '#B45309',
    bg: '#FEF3C7',
    border: '#f59e0b',
    icon: '!',
    title: 'Liable for Refund',
    desc: 'Present in App and PG (payment collected) but not scanned at AFC gate. Passenger may not have travelled — refund may be owed.',
  },
  {
    key: 'Failed Transaction',
    color: '#991B1B',
    bg: '#FEE2E2',
    border: '#ef4444',
    icon: '✕',
    title: 'Failed Transaction',
    desc: 'Either only in App (payment never reached PG) OR only in PG with no App or AFC match. Indicates a failed, aborted, or orphaned payment.',
  },
  {
    key: 'Refunded',
    color: '#6B21A8',
    bg: '#F3E8FF',
    border: '#8b5cf6',
    icon: '↺',
    title: 'Refunded',
    desc: 'A refund record exists in PG, or the App has marked this ticket as REFUNDED. Money has been returned to the customer.',
  },
  {
    key: 'Discrepancy',
    color: '#475569',
    bg: '#F1F5F9',
    border: '#94a3b8',
    icon: '?',
    title: 'Discrepancy',
    desc: 'Could not be classified under known rules. Requires manual investigation.',
  },
];

// Source chip colours
const SOURCE_STYLES = {
  App:  { color: '#0058be', bg: '#d8e2ff', border: '#adc6ff' },
  PG:   { color: '#171c1f', bg: '#dfe3e7', border: '#c6c6cd' },
  AFC:  { color: '#047857', bg: '#d1fae5', border: '#10b981' },
};

const ALL_SOURCES = ['App', 'PG', 'AFC'];

// Render small source presence chips
const DataSourceChips = ({ dataSources }) => {
  const present = dataSources ? dataSources.split(',').map(s => s.trim()) : [];
  return (
    <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
      {ALL_SOURCES.map(src => {
        const has = present.includes(src);
        const s = SOURCE_STYLES[src];
        return (
          <span
            key={src}
            title={has ? `Found in ${src}` : `Not found in ${src}`}
            style={{
              fontSize: '0.68rem',
              fontWeight: 700,
              fontFamily: 'monospace',
              padding: '0.1rem 0.45rem',
              borderRadius: '0px',
              border: `1px solid ${has ? s.border : 'rgba(255,255,255,0.08)'}`,
              background: has ? s.bg : 'transparent',
              color: has ? s.color : 'rgba(255,255,255,0.18)',
              letterSpacing: '0.02em',
              textDecoration: has ? 'none' : 'line-through',
              transition: 'all 0.15s ease',
            }}
          >
            {src}
          </span>
        );
      })}
    </div>
  );
};

// Status legend card
const StatusLegendPanel = () => (
  <div style={{
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
    gap: '0.65rem',
    marginBottom: '1.5rem',
  }}>
    {STATUS_LEGEND.map(l => (
      <div
        key={l.key}
        style={{
          background: l.bg,
          border: `1px solid ${l.border}`,
          borderRadius: '0px',
          padding: '0.65rem 0.85rem',
          display: 'flex',
          gap: '0.6rem',
          alignItems: 'flex-start',
        }}
      >
        <span style={{
          flexShrink: 0,
          width: '22px',
          height: '22px',
          borderRadius: '50%',
          background: l.color,
          color: '#0a0a0a',
          fontWeight: 800,
          fontSize: '0.7rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          {l.icon}
        </span>
        <div>
          <div style={{ fontWeight: 700, fontSize: '0.78rem', color: l.color, marginBottom: '0.2rem' }}>
            {l.title}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
            {l.desc}
          </div>
        </div>
      </div>
    ))}
  </div>
);

const ResultsBrowser = ({ refreshTrigger }) => {
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const [limitInputVal, setLimitInputVal] = useState('10');

  // Filters and Search (Active)
  const [appFilter, setAppFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSources, setSelectedSources] = useState([]);

  // Pending Filters (Local to popover, committed on "Apply now")
  const [pendingAppFilter, setPendingAppFilter] = useState('');
  const [pendingStatusFilter, setPendingStatusFilter] = useState('');
  const [pendingSearchQuery, setPendingSearchQuery] = useState('');
  const [pendingSelectedSources, setPendingSelectedSources] = useState([]);

  const [pageInputVal, setPageInputVal] = useState('1');
  const [loading, setLoading] = useState(false);
  const [showLegend, setShowLegend] = useState(true);
  const [showFiltersPanel, setShowFiltersPanel] = useState(false);

  // Synchronize pending state whenever the popover opens
  useEffect(() => {
    if (showFiltersPanel) {
      setPendingAppFilter(appFilter);
      setPendingStatusFilter(statusFilter);
      setPendingSearchQuery(searchQuery);
      setPendingSelectedSources(selectedSources);
    }
  }, [showFiltersPanel]);

  const clearAllFilters = () => {
    setAppFilter('');
    setStatusFilter('');
    setSearchQuery('');
    setSelectedSources([]);
    setPendingAppFilter('');
    setPendingStatusFilter('');
    setPendingSearchQuery('');
    setPendingSelectedSources([]);
    setPage(1);
  };

  const fetchResults = async () => {
    setLoading(true);
    try {
      const params = { page, limit };
      if (appFilter) params.app = appFilter;
      if (statusFilter) params.status = statusFilter;
      if (searchQuery) params.search = searchQuery;
      if (selectedSources.length > 0) params.sources = selectedSources.join(',');

      const response = await axios.get('http://127.0.0.1:8000/api/reconcile/results', { params });
      setResults(response.data.results);
      setTotal(response.data.total);
    } catch (err) {
      console.error('Failed to fetch results', err);
    } finally {
      setLoading(false);
    }
  };

  // Debounced search query trigger
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      fetchResults();
    }, 400);

    return () => clearTimeout(delayDebounceFn);
  }, [page, limit, appFilter, statusFilter, searchQuery, selectedSources, refreshTrigger]);

  const toggleSourceFilter = (src) => {
    setPage(1);
    setSelectedSources(prev => 
      prev.includes(src) ? prev.filter(s => s !== src) : [...prev, src]
    );
  };

  // Keep custom page input synced with page state changes
  useEffect(() => {
    setPageInputVal(page.toString());
  }, [page]);

  // Keep custom limit input synced with limit state changes
  useEffect(() => {
    setLimitInputVal(limit.toString());
  }, [limit]);

  const handleAppFilterChange = (e) => { setAppFilter(e.target.value); setPage(1); };
  const handleStatusFilterChange = (e) => { setStatusFilter(e.target.value); setPage(1); };
  
  const handleSearchChange = (e) => {
    setSearchQuery(e.target.value);
    setPage(1);
  };

  const handlePageInputChange = (e) => {
    setPageInputVal(e.target.value);
  };

  const handlePageInputBlur = () => {
    let p = parseInt(pageInputVal, 10);
    if (isNaN(p) || p < 1) {
      p = 1;
    } else if (p > totalPages) {
      p = totalPages;
    }
    setPage(p);
    setPageInputVal(p.toString());
  };

  const handlePageInputKeyDown = (e) => {
    if (e.key === 'Enter') {
      handlePageInputBlur();
    }
  };

  const handleLimitInputChange = (e) => {
    setLimitInputVal(e.target.value);
  };

  const handleLimitInputBlur = () => {
    let l = parseInt(limitInputVal, 10);
    if (isNaN(l) || l < 1) {
      l = 10;
    } else if (l > 500) {
      l = 500;
    }
    setLimit(l);
    setLimitInputVal(l.toString());
    setPage(1);
  };

  const handleLimitInputKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleLimitInputBlur();
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / limit));

  const getStatusStyle = (status) => {
    const legend = STATUS_LEGEND.find(l => l.key === status);
    if (!legend) return {};
    return {
      background: legend.bg,
      border: `1px solid ${legend.border}`,
      color: legend.color,
      borderRadius: '0px',
      padding: '0.2rem 0.55rem',
      fontSize: '0.72rem',
      fontWeight: 700,
      letterSpacing: '0.02em',
      whiteSpace: 'nowrap',
      display: 'inline-block',
    };
  };

  const getAppLineStyle = (appName) => {
    const name = appName ? appName.toLowerCase() : '';
    if (name.includes('connect')) {
      return {
        backgroundColor: '#d8e2ff',
        color: '#001a42',
        border: '1px solid #adc6ff'
      };
    } else if (name.includes('mumbai') || name.includes('one')) {
      return {
        backgroundColor: '#dfe3e7',
        color: '#171c1f',
        border: '1px solid #c6c6cd'
      };
    } else {
      // ONDC
      return {
        backgroundColor: '#ffdbca',
        color: '#341100',
        border: '1px solid #ffb690'
      };
    }
  };

  const getAppLineDisplayName = (appName) => {
    const name = appName ? appName.toLowerCase() : '';
    if (name.includes('connect')) return 'Metro Connect';
    if (name.includes('mumbai') || name.includes('one')) return 'Mumbai One';
    return 'ONDC Hub';
  };

  const getAppBadge = (app) => {
    const style = getAppLineStyle(app);
    const displayName = getAppLineDisplayName(app);
    return (
      <span style={{
        display: 'inline-block',
        padding: '0.25rem 0.5rem',
        fontSize: '12px',
        fontFamily: 'Outfit, sans-serif',
        fontWeight: 600,
        letterSpacing: '0.02em',
        ...style
      }}>
        {displayName}
      </span>
    );
  };

  return (
    <div className="widget-card">
      <div className="widget-card-title" style={{ margin: 0, padding: 0 }}>
        <span>Reconciliation Ledger</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            type="button"
            onClick={() => setShowLegend(v => !v)}
            style={{
              background: showLegend ? 'rgba(255,255,255,0.08)' : 'transparent',
              border: '1px solid rgba(255,255,255,0.15)',
              color: 'var(--text-muted)',
              fontSize: '0.75rem',
              padding: '0.25rem 0.7rem',
              borderRadius: '0px',
              cursor: 'pointer',
              fontWeight: 600,
              transition: 'all 0.15s ease',
            }}
          >
            {showLegend ? 'Hide' : 'Show'} Legend
          </button>
          <span style={{ fontSize: '0.9rem' }}>☵</span>
        </div>
      </div>

      {/* Source presence key */}
      <div style={{
        display: 'flex',
        gap: '0.5rem',
        alignItems: 'center',
        marginTop: '1rem',
        padding: '0.5rem 0.75rem',
        background: 'rgba(255,255,255,0.03)',
        borderRadius: '0px',
        border: '1px solid rgba(255,255,255,0.06)',
        flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, marginRight: '0.25rem' }}>
          SOURCE KEY:
        </span>
        {ALL_SOURCES.map(src => {
          const s = SOURCE_STYLES[src];
          return (
            <span key={src} style={{
              fontSize: '0.7rem',
              fontWeight: 700,
              padding: '0.1rem 0.5rem',
              borderRadius: '0px',
              border: `1px solid ${s.border}`,
              background: s.bg,
              color: s.color,
              fontFamily: 'monospace',
            }}>
              {src}
            </span>
          );
        })}
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
          Strikethrough = not present in that source
        </span>
      </div>

      {/* Status legend */}
      {showLegend && (
        <div style={{ marginTop: '1rem' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.6rem', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Status Definitions
          </div>
          <StatusLegendPanel />
        </div>
      )}

      {/* Filters Toolbar and Popover Anchor */}
      <div className="filters-row" style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Ledger View
          </span>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', position: 'relative' }}>
          <button
            type="button"
            className="btn-secondary-outline"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.45rem 1rem',
              fontSize: '0.8rem',
              fontWeight: 600,
              borderRadius: '0px',
              border: '1px solid var(--color-border)',
              background: 'var(--color-panel-bg)',
              color: 'var(--color-primary)',
              cursor: 'pointer',
            }}
          >
            ⇅ Sort by
          </button>

          <button
            type="button"
            onClick={() => setShowFiltersPanel(v => !v)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.45rem 1rem',
              fontSize: '0.8rem',
              fontWeight: 600,
              borderRadius: '0px',
              border: showFiltersPanel ? '1px solid #0f766e' : '1px solid var(--color-border)',
              background: showFiltersPanel ? 'rgba(15, 118, 110, 0.05)' : 'var(--color-panel-bg)',
              color: showFiltersPanel ? '#0f766e' : 'var(--color-primary)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            ⚙ Filter
            {((appFilter ? 1 : 0) + (statusFilter ? 1 : 0) + (selectedSources.length > 0 ? 1 : 0) + (searchQuery ? 1 : 0)) > 0 && (
              <span style={{
                backgroundColor: '#0f766e',
                color: '#ffffff',
                borderRadius: '50%',
                width: '18px',
                height: '18px',
                fontSize: '0.7rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                marginLeft: '0.25rem',
              }}>
                {(appFilter ? 1 : 0) + (statusFilter ? 1 : 0) + (selectedSources.length > 0 ? 1 : 0) + (searchQuery ? 1 : 0)}
              </span>
            )}
          </button>

          {/* Premium Filter Popover modeled 100% on the User's Screenshot */}
          {showFiltersPanel && (
            <div className="filter-popover" style={{
              position: 'absolute',
              top: 'calc(100% + 8px)',
              right: 0,
              width: '320px',
              maxHeight: '340px',
              overflowY: 'auto',
              background: '#FFFFFF',
              border: '1px solid var(--color-border)',
              borderRadius: '0px',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.15), 0 10px 10px -5px rgba(0, 0, 0, 0.08)',
              zIndex: 1000,
              padding: '1.25rem',
              textAlign: 'left',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
              animation: 'fadeInPanel 0.2s ease-out',
            }}>
              {/* Header */}
              <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--color-primary)', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.65rem' }}>
                Filter
              </div>

              {/* Section 1: Data Sources */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-primary)' }}>Data sources</span>
                  <button
                    type="button"
                    onClick={() => setPendingSelectedSources([])}
                    style={{ background: 'none', border: 'none', color: '#0284c7', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', padding: 0 }}
                  >
                    Reset
                  </button>
                </div>
                <div style={{ display: 'flex', gap: '0.35rem' }}>
                  {ALL_SOURCES.map(src => {
                    const active = pendingSelectedSources.includes(src);
                    const s = SOURCE_STYLES[src];
                    return (
                      <button
                        key={src}
                        type="button"
                        onClick={() => {
                          setPendingSelectedSources(prev => 
                            prev.includes(src) ? prev.filter(x => x !== src) : [...prev, src]
                          );
                        }}
                        style={{
                          fontSize: '0.68rem',
                          fontWeight: 700,
                          fontFamily: 'monospace',
                          padding: '0.35rem 0.65rem',
                          borderRadius: '0px',
                          border: `1px solid ${active ? s.color : 'var(--color-border)'}`,
                          background: active ? s.bg : 'var(--color-panel-bg)',
                          color: active ? s.color : 'var(--text-muted)',
                          cursor: 'pointer',
                          letterSpacing: '0.02em',
                          transition: 'all 0.15s ease',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.2rem',
                        }}
                      >
                        <span style={{ fontSize: '0.5rem', opacity: active ? 1 : 0.4 }}>{active ? '●' : '○'}</span>
                        {src}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Section 2: App Line */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-primary)' }}>App line</span>
                  <button
                    type="button"
                    onClick={() => setPendingAppFilter('')}
                    style={{ background: 'none', border: 'none', color: '#0284c7', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', padding: 0 }}
                  >
                    Reset
                  </button>
                </div>
                <select
                  className="form-select"
                  value={pendingAppFilter}
                  onChange={(e) => setPendingAppFilter(e.target.value)}
                  style={{ width: '100%', height: '36px', fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}
                >
                  <option value="">All App Lines</option>
                  <option value="MumbaiOne">Mumbai One</option>
                  <option value="MetroConnect3">Metro Connect</option>
                  <option value="ONDC">ONDC Hub</option>
                </select>
              </div>

              {/* Section 3: Status */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-primary)' }}>Status</span>
                  <button
                    type="button"
                    onClick={() => setPendingStatusFilter('')}
                    style={{ background: 'none', border: 'none', color: '#0284c7', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', padding: 0 }}
                  >
                    Reset
                  </button>
                </div>
                <select
                  className="form-select"
                  value={pendingStatusFilter}
                  onChange={(e) => setPendingStatusFilter(e.target.value)}
                  style={{ width: '100%', height: '36px', fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}
                >
                  <option value="">All Statuses</option>
                  <option value="Settled">Settled</option>
                  <option value="Failed Transaction">Failed Transaction</option>
                  <option value="Liable for Refund">Liable for Refund</option>
                  <option value="Refunded">Refunded</option>
                  <option value="Discrepancy">Discrepancy</option>
                </select>
              </div>

              {/* Section 4: Keyword Search */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-primary)' }}>Keyword search</span>
                  <button
                    type="button"
                    onClick={() => setPendingSearchQuery('')}
                    style={{ background: 'none', border: 'none', color: '#0284c7', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', padding: 0 }}
                  >
                    Reset
                  </button>
                </div>
                <div style={{ position: 'relative', width: '100%' }}>
                  <span style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', fontSize: '0.85rem' }}>🔍</span>
                  <input
                    type="text"
                    placeholder="Search..."
                    value={pendingSearchQuery}
                    onChange={(e) => setPendingSearchQuery(e.target.value)}
                    style={{
                      width: '100%',
                      height: '36px',
                      padding: '0 0.75rem 0 2rem',
                      fontSize: '0.8rem',
                      backgroundColor: 'var(--color-panel-bg)',
                      border: '1px solid var(--color-border)',
                      borderRadius: '0px',
                      color: 'var(--color-primary)',
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>
              </div>

              {/* Popover Footer modeled on Screenshot */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--color-border)', paddingTop: '0.85rem', marginTop: '0.25rem' }}>
                <button
                  type="button"
                  onClick={() => {
                    setPendingAppFilter('');
                    setPendingStatusFilter('');
                    setPendingSearchQuery('');
                    setPendingSelectedSources([]);
                  }}
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid var(--color-border)',
                    borderRadius: '0px',
                    color: 'var(--color-primary)',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    padding: '0.45rem 0.85rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseOver={(e) => e.target.style.backgroundColor = 'var(--color-neutral)'}
                  onMouseOut={(e) => e.target.style.backgroundColor = '#FFFFFF'}
                >
                  Reset all
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAppFilter(pendingAppFilter);
                    setStatusFilter(pendingStatusFilter);
                    setSearchQuery(pendingSearchQuery);
                    setSelectedSources(pendingSelectedSources);
                    setPage(1);
                    setShowFiltersPanel(false);
                  }}
                  style={{
                    background: '#0f766e',
                    border: 'none',
                    borderRadius: '0px',
                    color: '#FFFFFF',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    padding: '0.45rem 1rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseOver={(e) => e.target.style.background = '#0d5c56'}
                  onMouseOut={(e) => e.target.style.background = '#0f766e'}
                >
                  Apply now
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Premium Active Filter Chips (underneath toolbar) */}
      {((appFilter ? 1 : 0) + (statusFilter ? 1 : 0) + (selectedSources.length > 0 ? 1 : 0) + (searchQuery ? 1 : 0)) > 0 && (
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.5rem', marginBottom: '0.5rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 700 }}>ACTIVE FILTERS:</span>
          {appFilter && (
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#0f766e', backgroundColor: 'rgba(15, 118, 110, 0.08)', border: '1px solid rgba(15, 118, 110, 0.2)', padding: '0.25rem 0.55rem', borderRadius: '0px', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
              App: {appFilter} 
              <b onClick={() => { setAppFilter(''); setPage(1); }} style={{ cursor: 'pointer', marginLeft: '0.25rem', color: '#ef4444' }}>✕</b>
            </span>
          )}
          {statusFilter && (
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#0f766e', backgroundColor: 'rgba(15, 118, 110, 0.08)', border: '1px solid rgba(15, 118, 110, 0.2)', padding: '0.25rem 0.55rem', borderRadius: '0px', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
              Status: {statusFilter} 
              <b onClick={() => { setStatusFilter(''); setPage(1); }} style={{ cursor: 'pointer', marginLeft: '0.25rem', color: '#ef4444' }}>✕</b>
            </span>
          )}
          {searchQuery && (
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#0f766e', backgroundColor: 'rgba(15, 118, 110, 0.08)', border: '1px solid rgba(15, 118, 110, 0.2)', padding: '0.25rem 0.55rem', borderRadius: '0px', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
              Search: "{searchQuery}" 
              <b onClick={() => { setSearchQuery(''); setPage(1); }} style={{ cursor: 'pointer', marginLeft: '0.25rem', color: '#ef4444' }}>✕</b>
            </span>
          )}
          {selectedSources.length > 0 && (
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#0f766e', backgroundColor: 'rgba(15, 118, 110, 0.08)', border: '1px solid rgba(15, 118, 110, 0.2)', padding: '0.25rem 0.55rem', borderRadius: '0px', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
              Sources: {selectedSources.join(',')} 
              <b onClick={() => { setSelectedSources([]); setPage(1); }} style={{ cursor: 'pointer', marginLeft: '0.25rem', color: '#ef4444' }}>✕</b>
            </span>
          )}
          <button
            type="button"
            onClick={clearAllFilters}
            style={{
              background: 'none',
              border: 'none',
              color: '#ef4444',
              fontSize: '0.7rem',
              fontWeight: 700,
              cursor: 'pointer',
              textTransform: 'uppercase',
              marginLeft: '0.5rem',
            }}
          >
            Reset all
          </button>
        </div>
      )}

      {/* Table */}
      <div className="table-wrapper">
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px', color: 'var(--text-muted)' }}>
            Retrieving transaction packets...
          </div>
        ) : results.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px', color: 'var(--text-muted)' }}>
            No records found. Ingest files and run reconciliation to view results.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '1000px' }}>
            <thead style={{
              backgroundColor: '#f6fafe',
              color: '#45464d',
              fontSize: '12px',
              fontWeight: 500,
              letterSpacing: '0.05em',
              position: 'sticky',
              top: 0,
              zIndex: 10,
              boxShadow: 'inset 0 -1px 0 #c6c6cd'
            }}>
              <tr style={{ borderBottom: '1px solid #c6c6cd' }}>
                <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>App Line</th>
                <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Order ID</th>
                <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Ticket No</th>
                <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>PG Ref No</th>
                <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500, textAlign: 'right' }}>Amount</th>
                <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Transaction Time</th>
                <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Status</th>
                <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Sources</th>
                <th style={{ padding: '1rem', fontWeight: 500 }}>Notes</th>
              </tr>
            </thead>
            <tbody style={{ fontSize: '14px', color: '#000000' }}>
              {results.map((row) => (
                <tr 
                  key={row.id} 
                  className="staged-row-hover" 
                  style={{ borderBottom: '1px solid #c6c6cd', transition: 'background-color 0.15s ease', verticalAlign: 'middle' }}
                >
                  <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd' }}>
                    {getAppBadge(row.app_source)}
                  </td>
                  <td style={{
                    padding: '1rem',
                    borderRight: '1px solid #c6c6cd',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                    fontWeight: 600,
                    color: '#000000'
                  }}>
                    {row.order_id || '-'}
                  </td>
                  <td style={{
                    padding: '1rem',
                    borderRight: '1px solid #c6c6cd',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                    fontWeight: 600,
                    color: '#000000'
                  }}>
                    {row.ticket_no || '-'}
                  </td>
                  <td style={{
                    padding: '1rem',
                    borderRight: '1px solid #c6c6cd',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                    fontWeight: 600,
                    color: '#000000'
                  }}>
                    {row.pg_ref_no || '-'}
                  </td>
                  <td style={{
                    padding: '1rem',
                    borderRight: '1px solid #c6c6cd',
                    textAlign: 'right',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                    fontWeight: 600,
                    color: '#000000'
                  }}>
                    {row.amount !== null && row.amount !== undefined
                      ? `₹${row.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                      : '-'}
                  </td>
                  <td style={{
                    padding: '1rem',
                    borderRight: '1px solid #c6c6cd',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                    color: '#45464d'
                  }}>
                    {row.transaction_time || '-'}
                  </td>
                  <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd' }}>
                    <span style={getStatusStyle(row.recon_status)}>
                      {row.recon_status}
                    </span>
                  </td>
                  <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd' }}>
                    <DataSourceChips dataSources={row.data_sources} />
                  </td>
                  <td style={{ padding: '1rem', fontSize: '13px', color: '#45464d', whiteSpace: 'normal', minWidth: '180px', lineHeight: 1.5 }}>
                    {row.notes || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination Footer */}
      <div className="pagination-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
            Showing {results.length > 0 ? (page - 1) * limit + 1 : 0} to {Math.min(total, page * limit)} of {total.toLocaleString()} records
          </p>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', borderLeft: '1px solid var(--color-border)', paddingLeft: '1.25rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.04em' }}>SHOW:</span>
            <input
              type="number"
              min={1}
              max={500}
              value={limitInputVal}
              onChange={handleLimitInputChange}
              onKeyDown={handleLimitInputKeyDown}
              style={{
                width: '56px',
                height: '32px',
                padding: '0 0.35rem',
                fontSize: '0.8rem',
                fontWeight: 700,
                textAlign: 'center',
                backgroundColor: 'var(--color-panel-bg)',
                border: '1px solid var(--color-border)',
                borderRadius: '0px',
                color: 'var(--color-primary)',
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'border-color 0.2s ease',
              }}
              onFocus={(e) => e.target.style.borderColor = 'var(--color-secondary)'}
              onBlur={(e) => {
                e.target.style.borderColor = 'var(--color-border)';
                handleLimitInputBlur();
              }}
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>per page</span>
          </div>
        </div>

        <div className="pagination-btn-group" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <button
            className="page-btn"
            disabled={page <= 1 || loading}
            onClick={() => setPage(prev => Math.max(1, prev - 1))}
          >
            ‹
          </button>

          <button className="page-btn active" type="button">
            {page}
          </button>

          {page < totalPages && (
            <button className="page-btn" type="button" onClick={() => setPage(page + 1)}>
              {page + 1}
            </button>
          )}

          {page + 1 < totalPages && (
            <span style={{ display: 'flex', alignItems: 'center', padding: '0 0.25rem', color: 'var(--text-muted)' }}>...</span>
          )}

          {page < totalPages && page + 1 !== totalPages && (
            <button className="page-btn" type="button" onClick={() => setPage(totalPages)}>
              {totalPages}
            </button>
          )}

          <button
            className="page-btn"
            disabled={page >= totalPages || loading}
            onClick={() => setPage(prev => Math.min(totalPages, prev + 1))}
          >
            ›
          </button>

          {/* Custom typed page navigation */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginLeft: '0.75rem', borderLeft: '1px solid var(--color-border)', paddingLeft: '0.75rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>GO TO:</span>
            <input
              type="number"
              min={1}
              max={totalPages}
              value={pageInputVal}
              onChange={handlePageInputChange}
              onKeyDown={handlePageInputKeyDown}
              style={{
                width: '52px',
                height: '32px',
                padding: '0 0.25rem',
                fontSize: '0.8rem',
                fontWeight: 700,
                textAlign: 'center',
                backgroundColor: 'var(--color-panel-bg)',
                border: '1px solid var(--color-border)',
                borderRadius: '0px',
                color: 'var(--color-primary)',
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'border-color 0.2s ease',
              }}
              onFocus={(e) => e.target.style.borderColor = 'var(--color-secondary)'}
              onBlur={(e) => {
                e.target.style.borderColor = 'var(--color-border)';
                handlePageInputBlur();
              }}
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>/ {totalPages}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResultsBrowser;
