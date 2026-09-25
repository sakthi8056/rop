import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import api from '../api/client';
import StatusBadge from '../components/common/StatusBadge';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { Activity, Users, AlertTriangle, FileText } from 'lucide-react';

const DashboardPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    total: 0, today: 0, pending: 0, urgent: 0, recent: [], isDemo: false
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const response = await api.get('/history?limit=5');
        const history = response.data;
        
        // Check health endpoint for demo mode status
        const health = await api.get('/health');
        
        const today = new Date().toISOString().split('T')[0];
        
        setStats({
          total: history.length, // approximation for demo
          today: history.filter(h => h.screening_date.startsWith(today)).length,
          pending: history.filter(h => h.status === 'created' || h.status === 'manual_review').length,
          urgent: history.filter(h => h.latest_classification?.includes('Severe') || h.latest_classification?.includes('Plus')).length,
          recent: history.slice(0, 5),
          isDemo: health.data.demo_mode
        });
      } catch (error) {
        console.error("Error fetching dashboard data", error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchDashboardData();
  }, []);

  if (loading) return <LoadingSpinner message={t('common.loading')} />;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">{t('dashboard.title')}</h1>
        <button 
          className="btn btn-primary"
          onClick={() => navigate('/register')}
        >
          + {t('nav.new_screening')}
        </button>
      </div>

      {stats.isDemo && (
        <div className="demo-banner">
          <AlertTriangle size={20} />
          <span>{t('demo_mode_banner')}</span>
        </div>
      )}

      <div className="dashboard-grid">
        <div className="stat-card">
          <div className="stat-icon bg-primary-light"><Activity size={24} /></div>
          <div className="stat-content">
            <div className="stat-value">{stats.total}</div>
            <div className="stat-label">{t('dashboard.total_screenings')}</div>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon bg-success-light"><Users size={24} /></div>
          <div className="stat-content">
            <div className="stat-value">{stats.today}</div>
            <div className="stat-label">{t('dashboard.today_screenings')}</div>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon bg-warning-light"><FileText size={24} /></div>
          <div className="stat-content">
            <div className="stat-value">{stats.pending}</div>
            <div className="stat-label">{t('dashboard.pending_reviews')}</div>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon bg-danger-light"><AlertTriangle size={24} /></div>
          <div className="stat-content">
            <div className="stat-value">{stats.urgent}</div>
            <div className="stat-label">{t('dashboard.urgent_referrals')}</div>
          </div>
        </div>
      </div>

      <div className="card mt-24">
        <div className="card-header">
          <h2 className="card-title">{t('dashboard.recent_screenings')}</h2>
          <button className="btn btn-secondary" onClick={() => navigate('/history')}>
            {t('common.search')}
          </button>
        </div>
        <div className="card-body p-0">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t('history.date')}</th>
                <th>{t('patient.patient_id')}</th>
                <th>Infant / Mother</th>
                <th>Hospital / Center</th>
                <th>{t('results.classification')}</th>
                <th>{t('history.status')}</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent.length === 0 ? (
                <tr>
                  <td colSpan="6" className="text-center py-4 text-muted">
                    {t('history.no_records')}
                  </td>
                </tr>
              ) : (
                stats.recent.map(session => (
                  <tr key={session.session_id} onClick={() => navigate(`/results/${session.session_id}`)} className="cursor-pointer hover-bg">
                    <td>{session.screening_date}</td>
                    <td><span className="fw-500">{session.patient_id}</span></td>
                    <td>
                      <div style={{ fontWeight: 500 }}>
                        {session.infant_name || '—'}
                        {session.gender && <span className="text-muted" style={{ fontSize: '11px', marginLeft: '4px' }}>({session.gender})</span>}
                      </div>
                      {session.mother_name && <div style={{ fontSize: '11px', color: '#64748B' }}>M: {session.mother_name}</div>}
                    </td>
                    <td>{session.hospital_name || '—'}</td>
                    <td>{session.latest_classification || 'Pending Analysis'}</td>
                    <td><StatusBadge status={session.status} type="session" /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
