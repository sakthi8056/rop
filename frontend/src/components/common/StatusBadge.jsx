import React from 'react';

const StatusBadge = ({ status, type = 'result' }) => {
  let badgeClass = 'badge-gray';
  let label = status || '—';

  if (type === 'quality') {
    const q = status?.toUpperCase() || '';
    if (q === 'ACCEPTABLE' || q === 'GOOD') {
      badgeClass = 'badge-success';
      label = 'GOOD';
    } else if (q === 'POOR') {
      badgeClass = 'badge-warning';
      label = 'POOR';
    } else if (q === 'UNGRADABLE') {
      badgeClass = 'badge-danger';
      label = 'UNGRADABLE';
    }
  } else if (type === 'result' || type === 'canonical') {
    const s = status?.toLowerCase() || '';
    if (s.includes('positive') || s.includes('detected') && !s.includes('no rop') && !s.includes('not detected')) {
      badgeClass = 'badge-danger';
    } else if (s.includes('negative') || s.includes('no rop')) {
      badgeClass = 'badge-success';
    } else if (s.includes('inconclusive') || s.includes('ungradable')) {
      badgeClass = 'badge-warning';
    } else if (s.includes('demo') || s.includes('simulated')) {
      badgeClass = 'badge-warning';
    } else if (s.includes('normal')) {
      badgeClass = 'badge-success';
    } else if (s.includes('mild') || s.includes('pre-plus')) {
      badgeClass = 'badge-warning';
    } else if (s.includes('severe') || s.includes('plus')) {
      badgeClass = 'badge-danger';
    }
  } else if (type === 'session') {
    const s = status?.toLowerCase() || '';
    if (s === 'completed') badgeClass = 'badge-success';
    else if (s === 'created') badgeClass = 'badge-primary';
    else if (s === 'demo') badgeClass = 'badge-warning';
    else if (s === 'manual_review') badgeClass = 'badge-warning';
    else if (s === 'failed') badgeClass = 'badge-danger';
  }

  return (
    <span className={`badge ${badgeClass}`} style={{ fontWeight: 600, letterSpacing: '0.02em' }}>
      {label}
    </span>
  );
};

export default StatusBadge;
