import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import api, { BACKEND_URL } from '../api/client';
import StatusBadge from '../components/common/StatusBadge';
import LoadingSpinner from '../components/common/LoadingSpinner';
import {
  AlertTriangle,
  FileDown,
  ChevronLeft,
  ChevronRight,
  Eye,
  Edit,
  Trash2,
  CheckCircle2,
  AlertOctagon,
  HelpCircle,
  Hospital,
  User,
  Calendar,
  Phone,
  MapPin,
  FileText
} from 'lucide-react';
import './results.css';

const ResultsPage = () => {
  const { sessionId } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [currentResultIndex, setCurrentResultIndex] = useState(0);
  const [viewMode, setViewMode] = useState('heatmap'); // 'original', 'heatmap', 'overlay'
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  // Edit screening modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [editNotes, setEditNotes] = useState('');
  const [editDate, setEditDate] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);

  // Delete confirmation modal state
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const fetchResults = async () => {
    try {
      const res = await api.get(`/screening/${sessionId}/results`);
      setData(res.data);
      if (res.data.session) {
        setEditNotes(res.data.session.notes || '');
        setEditDate(res.data.session.screening_date || '');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load results');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResults();
  }, [sessionId]);

  // Handle genuine PDF Report generation and download
  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    setError('');
    try {
      const res = await api.post(`/reports/generate/${sessionId}?language=en`);
      const downloadUrl = `${BACKEND_URL}${res.data.download_url}`;
      // Direct PDF download trigger
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.setAttribute('download', `${res.data.report_id}.pdf`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate PDF report');
    } finally {
      setDownloadingPdf(false);
    }
  };

  // Save edited screening notes
  const handleSaveScreeningNotes = async (e) => {
    e.preventDefault();
    setSavingEdit(true);
    try {
      await api.put(`/screening/${sessionId}`, {
        notes: editNotes,
        screening_date: editDate
      });
      setShowEditModal(false);
      fetchResults();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update screening session');
    } finally {
      setSavingEdit(false);
    }
  };

  // Delete screening session with confirmation
  const handleConfirmDelete = async () => {
    setDeleting(true);
    try {
      await api.delete(`/screening/${sessionId}?confirm=true`);
      navigate('/history');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete screening session');
      setDeleting(false);
      setShowDeleteModal(false);
    }
  };

  if (loading) return <LoadingSpinner message="Loading screening results..." />;
  if (error && !data) return <div className="page-container"><div className="login-error">{error}</div></div>;
  if (!data) return null;

  const currentResult = data.results && data.results[currentResultIndex];
  const currentImage = data.images && data.images.find(img => img.image_id === currentResult?.image_id);
  const isDemo = data.is_demo || Boolean(currentResult?.is_demo);
  const patient = data.patient || {};
  const canonicalStatus = currentResult?.canonical_status || data.canonical_status || 'SCREENING COMPLETED';

  // Determine banner styling based on canonical screening status
  let statusBannerClass = 'canonical-banner-gray';
  let StatusIcon = HelpCircle;
  if (canonicalStatus.includes('POSITIVE') || canonicalStatus.includes('கண்டறியப்பட்டது')) {
    statusBannerClass = 'canonical-banner-danger';
    StatusIcon = AlertOctagon;
  } else if (canonicalStatus.includes('NEGATIVE') || canonicalStatus.includes('கண்டறியப்படவில்லை')) {
    statusBannerClass = 'canonical-banner-success';
    StatusIcon = CheckCircle2;
  } else if (canonicalStatus.includes('INCONCLUSIVE') || canonicalStatus.includes('UNGRADABLE') || canonicalStatus.includes('முடிவற்றது')) {
    statusBannerClass = 'canonical-banner-warning';
    StatusIcon = AlertTriangle;
  } else if (isDemo) {
    statusBannerClass = 'canonical-banner-demo';
    StatusIcon = AlertTriangle;
  }

  return (
    <div className="page-container">
      {/* Top Header & Actions */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 className="page-title">{t('results.title')}</h1>
          <p className="page-subtitle text-muted">
            Session: <strong>{sessionId}</strong> &bull; Date: {data.session?.screening_date}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate(`/register?edit=${patient.patient_id}`)}
            title="Edit Patient Details"
          >
            <Edit size={16} /> {t('results.edit_patient')}
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setShowEditModal(true)}
            title="Edit Screening Notes"
          >
            <FileText size={16} /> {t('results.edit_screening')}
          </button>

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleDownloadPdf}
            disabled={downloadingPdf}
            style={{ fontWeight: '600' }}
          >
            <FileDown size={18} />
            {downloadingPdf ? t('common.loading') : t('results.generate_report')}
          </button>

          <button
            type="button"
            className="btn btn-danger"
            onClick={() => setShowDeleteModal(true)}
            title="Delete this session"
            style={{ background: '#FEE2E2', color: '#B91C1C', border: '1px solid #FCA5A5' }}
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      {error && <div className="login-error mb-16">{error}</div>}

      {/* Prominent Canonical Clinical Status Banner */}
      <div className={`canonical-status-banner mb-20 ${statusBannerClass}`} style={{
        padding: '16px 20px',
        borderRadius: '8px',
        display: 'flex',
        alignItems: 'center',
        gap: '14px',
        color: '#FFFFFF'
      }}>
        <StatusIcon size={32} />
        <div>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', opacity: 0.9 }}>
            {t('results.canonical_status')}
          </div>
          <div style={{ fontSize: '20px', fontWeight: 'bold' }}>
            {canonicalStatus}
          </div>
        </div>
      </div>

      {/* Patient Demographic Summary Card */}
      <div className="card mb-20 p-16" style={{ background: '#F8FAFC', border: '1px solid #E2E8F0' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', fontSize: '13px' }}>
          <div>
            <span className="text-muted" style={{ display: 'block', fontSize: '11.5px' }}>{t('patient.patient_id')}</span>
            <strong>{patient.patient_id}</strong>
          </div>
          <div>
            <span className="text-muted" style={{ display: 'block', fontSize: '11.5px' }}>{t('patient.baby_name')}</span>
            <strong>{patient.infant_name || '—'}</strong>
          </div>
          <div>
            <span className="text-muted" style={{ display: 'block', fontSize: '11.5px' }}>{t('patient.gender') || 'Gender'}</span>
            <strong>{patient.gender || '—'}</strong>
          </div>
          <div>
            <span className="text-muted" style={{ display: 'block', fontSize: '11.5px' }}>{t('patient.mother_name')}</span>
            <strong>{patient.mother_name || '—'}</strong>
          </div>
          <div>
            <span className="text-muted" style={{ display: 'block', fontSize: '11.5px' }}>{t('patient.dob')}</span>
            <strong>{patient.date_of_birth || '—'}</strong>
          </div>
          <div>
            <span className="text-muted" style={{ display: 'block', fontSize: '11.5px' }}>{t('patient.gestational_age')}</span>
            <strong>{patient.gestational_age_weeks}w {patient.gestational_age_days}d ({patient.birth_weight_grams}g)</strong>
          </div>
          <div>
            <span className="text-muted" style={{ display: 'block', fontSize: '11.5px' }}>{t('patient.hospital')}</span>
            <strong>{patient.hospital_name || '—'}</strong>
          </div>
          <div>
            <span className="text-muted" style={{ display: 'block', fontSize: '11.5px' }}>{t('patient.city_town_village')}</span>
            <strong>{patient.city_town_village || '—'}</strong>
          </div>
          <div>
            <span className="text-muted" style={{ display: 'block', fontSize: '11.5px' }}>{t('patient.contact_number')}</span>
            <strong>{patient.contact_number || '—'}</strong>
          </div>
        </div>

        {data.session?.notes && (
          <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid #E2E8F0', fontSize: '12.5px' }}>
            <span className="text-muted">Screening Notes: </span>
            <span>{data.session.notes}</span>
          </div>
        )}
      </div>

      <div className="results-layout">
        {/* Left Column: Visualizations (Original, Heatmap, Overlay) */}
        <div className="results-visuals">
          {data.results && data.results.length > 1 && (
            <div className="image-navigator mb-12" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                className="btn btn-secondary btn-sm"
                disabled={currentResultIndex === 0}
                onClick={() => setCurrentResultIndex(prev => prev - 1)}
              >
                <ChevronLeft size={16} /> Prev
              </button>
              <span style={{ fontSize: '13px' }}>Image {currentResultIndex + 1} of {data.results.length}</span>
              <button
                className="btn btn-secondary btn-sm"
                disabled={currentResultIndex === data.results.length - 1}
                onClick={() => setCurrentResultIndex(prev => prev + 1)}
              >
                Next <ChevronRight size={16} />
              </button>
            </div>
          )}

          <div className="card visualization-card">
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 className="card-title" style={{ fontSize: '14px' }}>
                {currentImage?.eye_label?.toUpperCase()} Eye ({currentImage?.quality_status})
              </h2>

              <div className="view-toggle">
                <button
                  type="button"
                  className={`btn btn-sm ${viewMode === 'original' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setViewMode('original')}
                >
                  {t('results.original_image')}
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${viewMode === 'heatmap' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setViewMode('heatmap')}
                >
                  {t('results.heatmap')}
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${viewMode === 'overlay' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setViewMode('overlay')}
                >
                  {t('results.overlay')}
                </button>
              </div>
            </div>

            <div className="card-body img-display-container" style={{ textAlign: 'center', background: '#0F172A', minHeight: '320px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {viewMode === 'original' && currentImage && (
                <img src={`${BACKEND_URL}${currentImage.preview_url}`} alt="Original Fundus" style={{ maxWidth: '100%', maxHeight: '420px', objectFit: 'contain' }} />
              )}
              {viewMode === 'heatmap' && currentResult?.heatmap_url && (
                <img src={`${BACKEND_URL}${currentResult.heatmap_url}`} alt="Attention Heatmap" style={{ maxWidth: '100%', maxHeight: '420px', objectFit: 'contain' }} />
              )}
              {viewMode === 'overlay' && currentResult?.overlay_url && (
                <img src={`${BACKEND_URL}${currentResult.overlay_url}`} alt="Grad-CAM Overlay" style={{ maxWidth: '100%', maxHeight: '420px', objectFit: 'contain' }} />
              )}
              {(!currentImage && !currentResult) && (
                <span className="text-muted">No image visualization available</span>
              )}
            </div>

            {currentResult?.xai_explanation && (
              <div style={{ padding: '10px 14px', background: '#F8FAFC', fontSize: '12px', color: '#475569', borderTop: '1px solid #E2E8F0' }}>
                <strong>Vascular Attention:</strong> {currentResult.xai_explanation}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Detailed Findings & Clinical Recommendations */}
        <div className="results-details">
          {/* Findings Card */}
          <div className="card mb-20">
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 className="card-title">Detailed Assessment Findings</h2>
              <StatusBadge status={currentResult?.quality_status} type="quality" />
            </div>

            <div className="card-body">
              <div className="result-metric-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="result-metric">
                  <div className="metric-label">{t('results.classification')}</div>
                  <div className="metric-value classification" style={{ fontSize: '16px', fontWeight: '600' }}>
                    {currentResult?.severity || currentResult?.classification || '—'}
                  </div>
                </div>

                <div className="result-metric">
                  <div className="metric-label">{t('results.plus_status')}</div>
                  <div className="metric-value" style={{ fontSize: '16px', fontWeight: '600' }}>
                    {currentResult?.plus_disease_status || '—'}
                  </div>
                </div>

                <div className="result-metric">
                  <div className="metric-label">{t('results.image_quality')}</div>
                  <div className="metric-value">
                    <StatusBadge status={currentResult?.quality_status || currentImage?.quality_status} type="quality" />
                  </div>
                </div>

                <div className="result-metric">
                  <div className="metric-label">{t('results.confidence')}</div>
                  <div className="metric-value" style={{ fontSize: '15px' }}>
                    {isDemo ? (
                      <span className="badge badge-warning" style={{ fontSize: '11.5px' }}>DEMO (No Model)</span>
                    ) : currentResult?.confidence != null ? (
                      `${(currentResult.confidence * 100).toFixed(1)}%`
                    ) : (
                      '—'
                    )}
                  </div>
                </div>
              </div>

              {/* Class Probability Distribution (only when genuine) */}
              {!isDemo && currentResult?.probabilities && (
                <div className="probabilities-bar mt-16 pt-16" style={{ borderTop: '1px solid #E2E8F0' }}>
                  <div style={{ fontSize: '12px', fontWeight: '600', marginBottom: '8px', color: '#475569' }}>
                    Neural Network Class Probabilities:
                  </div>
                  {Object.entries(currentResult.probabilities).map(([label, prob]) => (
                    <div key={label} className="prob-item mb-8">
                      <div className="prob-label" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                        <span>{label}</span>
                        <strong>{(prob * 100).toFixed(1)}%</strong>
                      </div>
                      <div className="prob-track" style={{ background: '#E2E8F0', height: '6px', borderRadius: '3px', overflow: 'hidden' }}>
                        <div
                          className={`prob-fill ${label.includes('Normal') ? 'fill-success' : label.includes('Mild') ? 'fill-warning' : 'fill-danger'}`}
                          style={{
                            width: `${Math.min(prob * 100, 100)}%`,
                            height: '100%',
                            background: label.includes('Normal') ? '#16A34A' : label.includes('Mild') ? '#EAB308' : '#DC2626'
                          }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Recommendation Card */}
          <div className="card recommendation-card mb-20" style={{
            borderLeft: `4px solid ${
              currentResult?.recommendation_urgency === 'urgent' ? '#DC2626' :
              currentResult?.recommendation_urgency === 'elevated' ? '#EAB308' :
              currentResult?.recommendation_urgency === 'routine' ? '#16A34A' : '#0284C7'
            }`
          }}>
            <div className="card-header">
              <h2 className="card-title">{t('results.recommendation')}</h2>
              {currentResult?.recommendation_urgency && (
                <span className="badge badge-secondary" style={{ textTransform: 'uppercase', fontSize: '11px' }}>
                  Urgency: {currentResult.recommendation_urgency}
                </span>
              )}
            </div>
            <div className="card-body">
              <p className="recommendation-text" style={{ fontSize: '14.5px', lineHeight: '1.6' }}>
                {currentResult?.recommendation || 'No recommendation specified.'}
              </p>
            </div>
          </div>

          {/* Clinical Disclaimer Box */}
          <div className="card limitations-card p-12" style={{ background: '#F8FAFC', border: '1px dashed #CBD5E1', fontSize: '11.5px', color: '#64748B' }}>
            <strong>{t('results.limitations')}:</strong>{' '}
            {currentResult?.screening_limitations ||
              'This AI screening tool is for decision-support and research evaluation. It does NOT replace dilated indirect ophthalmoscopy by a qualified ophthalmologist.'}
          </div>
        </div>
      </div>

      {/* Edit Screening Notes Modal */}
      {showEditModal && (
        <div className="modal-overlay" style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div className="modal-card card" style={{ width: '460px', maxWidth: '90%' }}>
            <div className="card-header">
              <h3 className="card-title">Edit Screening Notes</h3>
            </div>
            <form onSubmit={handleSaveScreeningNotes}>
              <div className="card-body">
                <div className="form-group mb-16">
                  <label className="form-label">Screening Date</label>
                  <input
                    type="date"
                    className="form-input"
                    value={editDate}
                    onChange={(e) => setEditDate(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Screening Notes / Clinical Impressions</label>
                  <textarea
                    className="form-input"
                    rows="4"
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    placeholder="Enter clinical notes, pupil dilation notes, equipment used..."
                  ></textarea>
                </div>
              </div>
              <div className="card-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', padding: '12px 16px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowEditModal(false)}
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={savingEdit}
                >
                  {savingEdit ? t('common.loading') : t('common.save')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="modal-overlay" style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div className="modal-card card" style={{ width: '420px', maxWidth: '90%' }}>
            <div className="card-header" style={{ background: '#FEF2F2' }}>
              <h3 className="card-title" style={{ color: '#B91C1C' }}>
                <AlertOctagon size={18} style={{ display: 'inline', marginRight: '6px' }} />
                {t('history.confirm_delete_title')}
              </h3>
            </div>
            <div className="card-body" style={{ padding: '16px' }}>
              <p style={{ fontSize: '14px', color: '#334155' }}>
                Are you sure you want to delete screening session <strong>{sessionId}</strong>? This action cannot be undone.
              </p>
            </div>
            <div className="card-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', padding: '12px 16px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowDeleteModal(false)}
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

export default ResultsPage;
