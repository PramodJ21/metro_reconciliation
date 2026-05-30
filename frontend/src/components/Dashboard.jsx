import React from 'react';

const Dashboard = ({ dbStatus, summaries = [] }) => {
  // Compute aggregate reconciliation metrics
  const totalRecords = (summaries || []).reduce((acc, curr) => acc + (curr.total_records || 0), 0);
  const totalSettled = (summaries || []).reduce((acc, curr) => acc + (curr.settled || 0), 0);
  const totalFailed = (summaries || []).reduce((acc, curr) => acc + (curr.failed_transaction || 0), 0);
  const totalLiable = (summaries || []).reduce((acc, curr) => acc + (curr.liable_for_refund || 0), 0);
  const totalRefunded = (summaries || []).reduce((acc, curr) => acc + (curr.refunded || 0), 0);

  // Compute aggregate revenue metrics
  const totalMobileRevenue = (summaries || []).reduce((acc, curr) => acc + (curr.revenue || 0), 0);
  const totalSettledRevenue = (summaries || []).reduce((acc, curr) => acc + (curr.settled_revenue || 0), 0);
  const totalAfcRevenue = (summaries || []).reduce((acc, curr) => acc + (curr.afc_revenue || 0), 0);
  const totalRefundAmount = (summaries || []).reduce((acc, curr) => acc + (curr.refund_amount || 0), 0);
  const netRevenue = totalSettledRevenue - totalRefundAmount;

  const getAppSummary = (appName) => {
    return (summaries || []).find(s => s.app_source === appName) || {
      total_records: 0,
      settled: 0,
      liable_for_refund: 0,
      failed_transaction: 0,
      refunded: 0,
      discrepancy: 0,
      revenue: 0,
      settled_revenue: 0,
      afc_revenue: 0,
      refund_amount: 0
    };
  };

  const m1 = getAppSummary('MumbaiOne');
  const mc3 = getAppSummary('MetroConnect3');
  const ondc = getAppSummary('ONDC');

  // Dynamic formatting for counts in Indian Numbering System (Lakh / Crore)
  const formatCount = (num) => {
    if (num >= 10000000) { // 1 Crore = 10,000,000
      return (num / 10000000).toFixed(2).replace(/\.00$/, '') + ' Cr';
    }
    if (num >= 100000) { // 1 Lakh = 100,000
      return (num / 100000).toFixed(2).replace(/\.00$/, '') + ' L';
    }
    return new Intl.NumberFormat('en-IN').format(num);
  };

  // Dynamic formatting for Rupees in Indian Numbering System (Lakh / Crore)
  const formatRupeeAbbr = (val) => {
    if (val >= 10000000) { // 1 Crore = 10,000,000
      return `₹${(val / 10000000).toFixed(2).replace(/\.00$/, '')} Cr`;
    }
    if (val >= 100000) { // 1 Lakh = 100,000
      return `₹${(val / 100000).toFixed(2).replace(/\.00$/, '')} L`;
    }
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val || 0);
  };


  const getAppLineStyle = (appName) => {
    const name = appName ? appName.toLowerCase() : '';
    if (name.includes('connect')) {
      return {
        backgroundColor: '#e0f2fe',
        color: '#0369a1',
        border: '1px solid #93c5fd'
      };
    } else if (name.includes('mumbai') || name.includes('one')) {
      return {
        backgroundColor: '#eef2ff',
        color: '#4338ca',
        border: '1px solid #c7d2fe'
      };
    } else {
      // ONDC Hub (Distinct Salmon/Peach tint)
      return {
        backgroundColor: '#ffecd2',
        color: '#7c2d12',
        border: '1px solid #fdba74'
      };
    }
  };

  const getAppLineDisplayName = (appName) => {
    const name = appName ? appName.toLowerCase() : '';
    if (name.includes('connect')) return 'Metro Connect';
    if (name.includes('mumbai') || name.includes('one')) return 'Mumbai One';
    return 'ONDC Hub';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3rem', fontFamily: 'Outfit, sans-serif' }}>
      
      {/* SECTION A: TRANSACTION OVERVIEW */}
      <section>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h3 style={{
            fontSize: '16px',
            lineHeight: '1',
            letterSpacing: '0.08em',
            fontWeight: '700',
            color: '#0F172A',
            textTransform: 'uppercase',
            marginRight: '1rem',
            whiteSpace: 'nowrap'
          }}>
            Transaction Overview
          </h3>
          <div style={{ flex: 1, height: '1px', backgroundColor: '#C6C6CD' }}></div>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '1rem'
        }}>
          {/* Card 1: Total Transactions */}
          <div className="bg-surface-container-lowest" style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            padding: '1.25rem 1.5rem', 
            border: '1px solid #C6C6CD', 
            borderLeft: '4px solid #64748B',
            borderRadius: '0px',
            backgroundColor: '#ffffff'
          }}>
            <span style={{ fontSize: '10px', lineHeight: '1', letterSpacing: '0.06em', fontWeight: '700', color: '#64748B', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Total Transactions
            </span>
            <span style={{ fontSize: '32px', lineHeight: '1.2', letterSpacing: '0.03em', fontWeight: '600', color: '#0F172A' }}>
              {formatCount(totalRecords)}
            </span>
          </div>

          {/* Card 2: Settled Transactions */}
          <div className="bg-surface-container-lowest" style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            padding: '1.25rem 1.5rem', 
            border: '1px solid #C6C6CD', 
            borderLeft: '4px solid #10B981',
            borderRadius: '0px',
            backgroundColor: '#ffffff'
          }}>
            <span style={{ fontSize: '10px', lineHeight: '1', letterSpacing: '0.06em', fontWeight: '700', color: '#64748B', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Settled Transactions
            </span>
            <span style={{ fontSize: '32px', lineHeight: '1.2', letterSpacing: '0.03em', fontWeight: '600', color: '#047857' }}>
              {formatCount(totalSettled)}
            </span>
          </div>

          {/* Card 3: Refund Liable */}
          <div className="bg-surface-container-lowest" style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            padding: '1.25rem 1.5rem', 
            border: '1px solid #C6C6CD', 
            borderLeft: '4px solid #F59E0B',
            borderRadius: '0px',
            backgroundColor: '#ffffff'
          }}>
            <span style={{ fontSize: '10px', lineHeight: '1', letterSpacing: '0.06em', fontWeight: '700', color: '#64748B', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Refund Liable
            </span>
            <span style={{ fontSize: '32px', lineHeight: '1.2', letterSpacing: '0.03em', fontWeight: '600', color: '#B45309' }}>
              {formatCount(totalLiable)}
            </span>
          </div>

          {/* Card 4: Refunded */}
          <div className="bg-surface-container-lowest" style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            padding: '1.25rem 1.5rem', 
            border: '1px solid #C6C6CD', 
            borderLeft: '4px solid #3B82F6',
            borderRadius: '0px',
            backgroundColor: '#ffffff'
          }}>
            <span style={{ fontSize: '10px', lineHeight: '1', letterSpacing: '0.06em', fontWeight: '700', color: '#64748B', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Refunded
            </span>
            <span style={{ fontSize: '32px', lineHeight: '1.2', letterSpacing: '0.03em', fontWeight: '600', color: '#1D4ED8' }}>
              {formatCount(totalRefunded)}
            </span>
          </div>

          {/* Card 5: Incomplete */}
          <div className="bg-surface-container-lowest" style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            padding: '1.25rem 1.5rem', 
            border: '1px solid #C6C6CD', 
            borderLeft: '4px solid #EF4444',
            borderRadius: '0px',
            backgroundColor: '#ffffff'
          }}>
            <span style={{ fontSize: '10px', lineHeight: '1', letterSpacing: '0.06em', fontWeight: '700', color: '#64748B', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Incomplete
            </span>
            <span style={{ fontSize: '32px', lineHeight: '1.2', letterSpacing: '0.03em', fontWeight: '600', color: '#B91C1C' }}>
              {formatCount(totalFailed)}
            </span>
          </div>
        </div>
      </section>

      {/* SECTION B: REVENUE SUMMARY */}
      <section>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h3 style={{
            fontSize: '16px',
            lineHeight: '1',
            letterSpacing: '0.08em',
            fontWeight: '700',
            color: '#0F172A',
            textTransform: 'uppercase',
            marginRight: '1rem',
            whiteSpace: 'nowrap'
          }}>
            Revenue Summary
          </h3>
          <div style={{ flex: 1, height: '1px', backgroundColor: '#C6C6CD' }}></div>
        </div>

        <div className="revenue-summary-wrapper" style={{ border: '1px solid #C6C6CD', padding: '1.5rem', backgroundColor: '#ffffff' }}>
          <div className="revenue-summary-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1.5rem' }}>
            {/* Column 1: Total AFC Revenue */}
            <div style={{ borderLeft: '3px solid #64748B', paddingLeft: '1rem', display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '10px', lineHeight: '1', letterSpacing: '0.06em', fontWeight: '700', color: '#64748B', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                Total AFC Revenue
              </span>
              <span style={{ fontSize: '24px', lineHeight: '1.2', letterSpacing: '0.02em', fontWeight: '600', color: '#0F172A' }}>
                {formatRupeeAbbr(totalAfcRevenue)}
              </span>
            </div>

            {/* Column 2: Total Mobile Revenue */}
            <div style={{ borderLeft: '3px solid #64748B', paddingLeft: '1rem', display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '10px', lineHeight: '1', letterSpacing: '0.06em', fontWeight: '700', color: '#64748B', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                Total Mobile Revenue
              </span>
              <span style={{ fontSize: '24px', lineHeight: '1.2', letterSpacing: '0.02em', fontWeight: '600', color: '#0F172A' }}>
                {formatRupeeAbbr(totalMobileRevenue)}
              </span>
            </div>

            {/* Column 3: Total Settled Revenue */}
            <div style={{ borderLeft: '3px solid #10B981', paddingLeft: '1rem', display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '10px', lineHeight: '1', letterSpacing: '0.06em', fontWeight: '700', color: '#64748B', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                Total Settled Revenue
              </span>
              <span style={{ fontSize: '24px', lineHeight: '1.2', letterSpacing: '0.02em', fontWeight: '600', color: '#047857' }}>
                {formatRupeeAbbr(totalSettledRevenue)}
              </span>
            </div>

            {/* Column 4: Total Refund Amount */}
            <div style={{ borderLeft: '3px solid #64748B', paddingLeft: '1rem', display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '10px', lineHeight: '1', letterSpacing: '0.06em', fontWeight: '700', color: '#64748B', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                Total Refund Amount
              </span>
              <span style={{ fontSize: '24px', lineHeight: '1.2', letterSpacing: '0.02em', fontWeight: '600', color: '#0F172A' }}>
                {formatRupeeAbbr(totalRefundAmount)}
              </span>
            </div>

            {/* Column 5: Net Revenue Balance */}
            <div style={{ borderLeft: '3px solid #3B82F6', paddingLeft: '1rem', display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '10px', lineHeight: '1', letterSpacing: '0.06em', fontWeight: '700', color: '#64748B', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                Net Revenue Balance
              </span>
              <span style={{ fontSize: '24px', lineHeight: '1.2', letterSpacing: '0.02em', fontWeight: '700', color: '#1D4ED8' }}>
                {formatRupeeAbbr(netRevenue)}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION C: APPLICATION PERFORMANCE */}
      <section>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h3 style={{
            fontSize: '16px',
            lineHeight: '1',
            letterSpacing: '0.08em',
            fontWeight: '700',
            color: '#0F172A',
            textTransform: 'uppercase',
            marginRight: '1rem',
            whiteSpace: 'nowrap'
          }}>
            Application Performance
          </h3>
          <div style={{ flex: 1, height: '1px', backgroundColor: '#C6C6CD' }}></div>
        </div>

        <div className="bg-surface-container-lowest" style={{ 
          padding: '0px', 
          border: '1px solid #C6C6CD', 
          borderRadius: '0px', 
          overflow: 'hidden',
          backgroundColor: '#ffffff'
        }}>
          {totalRecords === 0 ? (
            <div style={{ padding: '3.5rem 1.5rem', textAlign: 'center', color: '#45464D' }}>
              <div style={{ fontSize: '18px', fontWeight: '600', color: '#000000', marginBottom: '0.5rem' }}>No Active Ingested Logs</div>
              <p style={{ fontSize: '16px', maxWidth: '380px', margin: '0 auto', lineHeight: 1.5 }}>
                Stage reports in the **Network Ingestion Depot** and trigger classification to view system analytics.
              </p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
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
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Application Name</th>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500, textAlign: 'right' }}>Total Trans.</th>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500, textAlign: 'right' }}>Total Revenue</th>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500, textAlign: 'right' }}>Refund Count</th>
                    <th style={{ padding: '1rem', fontWeight: 500, textAlign: 'right' }}>Total Refunded</th>
                  </tr>
                </thead>
                <tbody style={{ fontSize: '14px', color: '#000000' }}>
                  {/* Metro Connect */}
                  <tr className="staged-row-hover" style={{ borderBottom: '1px solid #c6c6cd', transition: 'background-color 0.15s ease', verticalAlign: 'middle' }}>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '115px',
                        height: '24px',
                        boxSizing: 'border-box',
                        fontSize: '11px',
                        fontFamily: "'Outfit', 'Inter', -apple-system, sans-serif",
                        fontWeight: 600,
                        letterSpacing: '0.02em',
                        ...getAppLineStyle('MetroConnect3')
                      }}>
                        {getAppLineDisplayName('MetroConnect3')}
                      </span>
                    </td>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatCount(mc3.total_records)}
                    </td>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatRupeeAbbr(mc3.revenue)}
                    </td>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatCount(mc3.refunded)}
                    </td>
                    <td style={{ padding: '1rem', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatRupeeAbbr(mc3.refund_amount)}
                    </td>
                  </tr>

                  {/* Mumbai One */}
                  <tr className="staged-row-hover" style={{ borderBottom: '1px solid #c6c6cd', transition: 'background-color 0.15s ease', verticalAlign: 'middle' }}>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '115px',
                        height: '24px',
                        boxSizing: 'border-box',
                        fontSize: '11px',
                        fontFamily: "'Outfit', 'Inter', -apple-system, sans-serif",
                        fontWeight: 600,
                        letterSpacing: '0.02em',
                        ...getAppLineStyle('MumbaiOne')
                      }}>
                        {getAppLineDisplayName('MumbaiOne')}
                      </span>
                    </td>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatCount(m1.total_records)}
                    </td>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatRupeeAbbr(m1.revenue)}
                    </td>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatCount(m1.refunded)}
                    </td>
                    <td style={{ padding: '1rem', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatRupeeAbbr(m1.refund_amount)}
                    </td>
                  </tr>

                  {/* ONDC */}
                  <tr className="staged-row-hover" style={{ transition: 'background-color 0.15s ease', verticalAlign: 'middle' }}>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '115px',
                        height: '24px',
                        boxSizing: 'border-box',
                        fontSize: '11px',
                        fontFamily: "'Outfit', 'Inter', -apple-system, sans-serif",
                        fontWeight: 600,
                        letterSpacing: '0.02em',
                        ...getAppLineStyle('ONDC')
                      }}>
                        {getAppLineDisplayName('ONDC')}
                      </span>
                    </td>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatCount(ondc.total_records)}
                    </td>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatRupeeAbbr(ondc.revenue)}
                    </td>
                    <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatCount(ondc.refunded)}
                    </td>
                    <td style={{ padding: '1rem', textAlign: 'right', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontWeight: 600, color: '#000000' }}>
                      {formatRupeeAbbr(ondc.refund_amount)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>


    </div>
  );
};

export default Dashboard;
