import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import api, { BACKEND_URL } from '../api/client';
import StatusBadge from '../components/common/StatusBadge';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { Search, Filter, Eye, FileDown, Edit, Trash2, AlertOctagon } from 'lucide-react';
import './pages.css';

const HistoryPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  const [filters, setFilters] = useState({
    patient_id: '',
    date_from: '',
    date_to: ''
  });

  // Deletion modal state
  const [sessionToDelete, setSessionToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.patient_id) params.append('patient_id', filters.patient_id);
      if (filters.date_from) params.append('date_from', filters.date_from);
      if (filters.date_to) params.append('date_to', filters.date_to);

      const res = await api.get(`/history/?${params.toString()}`);
      setHistory(res.data);
    } catch (err) {
      console.error('Failed to fetch history', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleSearch = (e) => {
    e.preventDefault();
    fetchHistory();
  };

  // Direct genuine PDF download
  const handleDownloadReport = async (e, sessionId, reportId) => {
    e.stopPropagation();
    try {
      let targetReportId = reportId;
      if (!targetReportId) {
        const res = await api.post(`/reports/generate/${sessionId}?language=en`);
        targetReportId = res.data.report_id;
      }
      const downloadUrl = `${BACKEND_URL}/api/reports/download/${targetReportId}`;
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.setAttribute('download', `${targetReportId}.pdf`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      console.error('Failed to download report', err);
    }
  };

  const openDeleteModal = (e, session) => {
    e.stopPropagation();
    setSessionToDelete(session);
    setDeleteError('');
  };

  const handleConfirmDelete = async () => {
    if (!sessionToDelete) return;
    setDeleting(true);
    setDeleteError('');
    try {
      await api.delete(`/screening/${sessionToDelete.session_id}?confirm=true`);
      setSessionToDelete(null);
      fetchHistory();
    } catch (err) {
      setDeleteError(err.response?.data?.detail || 'Failed to delete record');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="page-title">{t('history.title')}</h1>
          <p className="page-subtitle text-muted">Review, filter, edit, or download past screening sessions</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/register')}>
          + {t('nav.new_screening')}
        </button>
      </div>

      <div className="card mb-24">
        <div className="card-body">
          <form className="history-filters" onSubmit={handleSearch}>
            <div className="filter-group flex-2">
              <label className="form-label">{t('patient.patient_id')} / Name / Location</label>
              <div className="search-input-wrapper">
                <Search size={18} className="search-icon" />
                <input
                  type="text"
                  name="patient_id"
                  className="form-input with-icon"
                  placeholder={t('history.search_placeholder')}
                  value={filters.patient_id}
                  onChange={handleFilterChange}
                />
              </div>
            </div>
            <div className="filter-group flex-1">
              <label className="form-label">{t('history.filter_date_from')}</label>
              <input
                type="date"
                name="date_from"
                className="form-input"
                value={filters.date_from}
                onChange={handleFilterChange}
              />
            </div>
            <div className="filter-group flex-1">
              <label className="form-label">{t('history.filter_date_to')}</label>
              <input
                type="date"
                name="date_to"
                className="form-input"
                value={filters.date_to}
                onChange={handleFilterChange}
              />
            </div>
            <div className="filter-group filter-actions">
              <button type="submit" className="btn btn-primary" style={{ height: '42px', alignSelf: 'flex-end' }}>
                <Filter size={18} /> {t('common.search')}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="card">
        <div className="card-body p-0">
          {loading ? (
            <LoadingSpinner />
          ) : (
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t('history.date')}</th>
                    <th>{t('patient.patient_id')}</th>
                    <th>Infant / Mother</th>
                    <th>Hospital / Center</th>
                    <th>{t('results.classification')}</th>
                    <th>{t('history.status')}</th>
                    <th className="text-right">{t('history.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="text-center py-4 text-muted">
                        {t('history.no_records')}
                      </td>
                    </tr>
                  ) : (
                    history.map(session => (
                      <tr
                        key={session.session_id}
                        onClick={() => navigate(`/results/${session.session_id}`)}
                        className="cursor-pointer hover-bg"
                      >
                        <td>{session.screening_date}</td>
                        <td><span className="fw-500">{session.patient_id}</span></td>
                        <td>
                          <div style={{ fontWeight: '500' }}>
                            {session.infant_name || '—'}
                            {session.gender && <span className="text-muted" style={{ fontSize: '11.5px', marginLeft: '6px' }}>({session.gender})</span>}
                          </div>
                          {session.mother_name && (
                            <div style={{ fontSize: '11.5px', color: '#64748B' }}>M: {session.mother_name}</div>
                          )}
                        </td>
                        <td>
                          <div>{session.hospital_name || '—'}</div>
                          {session.city_town_village && (
                            <div style={{ fontSize: '11.5px', color: '#64748B' }}>{session.city_town_village}</div>
                          )}
                        </td>
                        <td>{session.latest_classification || 'Pending Analysis'}</td>
                        <td><StatusBadge status={session.status} type="session" /></td>
                        <td className="text-right">
                          <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                            {/* View Results Button */}
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              title={t('history.view_details')}
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/results/${session.session_id}`);
                              }}
                            >
                              <Eye size={15} />
                            </button>

                            {/* Download PDF Button */}
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              title={t('results.generate_report')}
                              onClick={(e) => handleDownloadReport(e, session.session_id, session.report_id)}
                            >
                              <FileDown size={15} />
                            </button>

                            {/* Edit Patient Button */}
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              title={t('history.edit_patient')}
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/register?edit=${session.patient_id}`);
                              }}
                            >
                              <Edit size={15} />
                            </button>

                            {/* Delete Session Button */}
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              title={t('history.delete_screening')}
                              onClick={(e) => openDeleteModal(e, session)}
                              style={{ color: '#DC2626' }}
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {sessionToDelete && (
        <div className="modal-overlay" style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div className="modal-card card" style={{ width: '440px', maxWidth: '90%' }}>
            <div className="card-header" style={{ background: '#FEF2F2' }}>
              <h3 className="card-title" style={{ color: '#B91C1C', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertOctagon size={18} />
                {t('history.confirm_delete_title')}
              </h3>
            </div>
            <div className="card-body" style={{ padding: '18px' }}>
              {deleteError && <div className="login-error mb-12">{deleteError}</div>}
              <p style={{ fontSize: '14px', color: '#334155', lineHeight: '1.5' }}>
                Are you sure you want to delete screening record <strong>{sessionToDelete.session_id}</strong> for patient <strong>{sessionToDelete.patient_id}</strong>?
              </p>
              <p style={{ fontSize: '12px', color: '#64748B', marginTop: '6px' }}>
                This record will be safely soft-deleted from active clinical workflows and reporting.
              </p>
            </div>
            <div className="card-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', padding: '12px 18px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSessionToDelete(null)}
                disabled={deleting}
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleConfirmDelete}
                disabled={deleting}
              >
                {deleting ? t('common.loading') : t('common.delete')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HistoryPage;
