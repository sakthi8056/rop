import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import api, { BACKEND_URL } from '../api/client';
import StatusBadge from '../components/common/StatusBadge';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { UploadCloud, CheckCircle, Eye, X, Play, AlertCircle, Info, Calendar, Hospital, User } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import './screening.css';

const ScreeningPage = () => {
  const { sessionId } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [patient, setPatient] = useState(null);
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [eyeSelection, setEyeSelection] = useState('unspecified');

  const fetchSessionData = useCallback(async () => {
    try {
      const resultsRes = await api.get(`/screening/${sessionId}/results`);
      setSession(resultsRes.data.session);
      setPatient(resultsRes.data.patient);
      setImages(resultsRes.data.images || []);

      // If already analyzed and completed, redirect to results
      if (['completed', 'demo', 'failed', 'manual_review'].includes(resultsRes.data.session.status)) {
        navigate(`/results/${sessionId}`);
      }
    } catch (err) {
      if (err.response?.status === 404) {
        try {
          const imgRes = await api.get(`/images/session/${sessionId}`);
          setImages(imgRes.data);
        } catch {
          setError('Failed to load screening session');
        }
      } else {
        setError(err.response?.data?.detail || 'Failed to load session');
      }
    } finally {
      setLoading(false);
    }
  }, [sessionId, navigate]);

  useEffect(() => {
    fetchSessionData();
  }, [fetchSessionData]);

  const onDrop = async (acceptedFiles) => {
    if (!acceptedFiles || acceptedFiles.length === 0) return;

    setError('');
    setUploading(true);
    const file = acceptedFiles[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('eye_label', eyeSelection);

    try {
      const res = await api.post(`/images/upload/${sessionId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setImages(prev => [...prev, res.data]);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload retinal image');
    } finally {
      setUploading(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/jpeg': ['.jpeg', '.jpg'], 'image/png': ['.png'] },
    maxSize: 10 * 1024 * 1024, // 10MB
    multiple: false
  });

  const handleDeleteImage = async (imageId) => {
    try {
      await api.delete(`/images/${imageId}`);
      setImages(prev => prev.filter(img => img.image_id !== imageId));
    } catch {
      setError('Failed to delete image');
    }
  };

  const handleProcessScreening = async () => {
    if (images.length === 0) {
      setError('Please upload at least one retinal fundus scan before processing.');
      return;
    }

    setAnalyzing(true);
    setError('');

    try {
      await api.post(`/screening/${sessionId}/analyze`);
      // Step 7: Display screening result immediately after processing
      navigate(`/results/${sessionId}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Screening processing failed');
      setAnalyzing(false);
    }
  };

  if (loading) return <LoadingSpinner message="Loading screening workspace..." />;

  const hasImages = images.length > 0;
  const ungradableOnly = hasImages && images.every(img => img.quality_status === 'UNGRADABLE');

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('screening.title')}</h1>
          <p className="page-subtitle text-muted">Session ID: {sessionId}</p>
        </div>
      </div>

      {/* Patient Information Banner */}
      {patient && (
        <div className="patient-banner card mb-20 p-16" style={{
          background: '#F8FAFC',
          borderLeft: '4px solid #0284C7',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '20px',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ background: '#E0F2FE', padding: '10px', borderRadius: '50%', color: '#0369A1' }}>
              <User size={22} />
            </div>
            <div>
              <div style={{ fontSize: '15px', fontWeight: '600', color: '#0F172A' }}>
                {patient.infant_name || "Newborn Patient"}
                {patient.mother_name && <span style={{ fontWeight: 'normal', color: '#475569' }}> (Mother: {patient.mother_name})</span>}
              </div>
              <div style={{ fontSize: '12px', color: '#64748B' }}>
                ID: <strong>{patient.patient_id}</strong> &bull; {patient.gender && <>Gender: <strong>{patient.gender}</strong> &bull; </>}DOB: {patient.date_of_birth} &bull; GA: {patient.gestational_age_weeks}w {patient.gestational_age_days}d &bull; Weight: {patient.birth_weight_grams}g
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px', color: '#475569' }}>
            {patient.hospital_name && (
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Hospital size={14} /> {patient.hospital_name}
              </span>
            )}
            {patient.city_town_village && (
              <span>({patient.city_town_village})</span>
            )}
          </div>
        </div>
      )}

      {error && <div className="login-error mb-16">{error}</div>}

      <div className="screening-layout">
        {/* Main Content Area: Upload & Previews */}
        <div className="screening-main">
          <div className="card">
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 className="card-title">{t('screening.upload_instructions')}</h2>

              <div className="eye-selector">
                <button
                  type="button"
                  className={`btn ${eyeSelection === 'left' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setEyeSelection('left')}
                >
                  {t('screening.left_eye')}
                </button>
                <button
                  type="button"
                  className={`btn ${eyeSelection === 'right' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setEyeSelection('right')}
                >
                  {t('screening.right_eye')}
                </button>
                <button
                  type="button"
                  className={`btn ${eyeSelection === 'unspecified' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setEyeSelection('unspecified')}
                >
                  {t('screening.unspecified_eye')}
                </button>
              </div>
            </div>

            <div className="card-body">
              <div
                {...getRootProps()}
                className={`dropzone ${isDragActive ? 'active' : ''} ${uploading ? 'disabled' : ''}`}
                style={{ cursor: uploading ? 'wait' : 'pointer' }}
              >
                <input {...getInputProps()} />
                <UploadCloud size={44} className="dropzone-icon" />
                <p className="dropzone-text" style={{ fontSize: '15px', fontWeight: '500', marginBottom: '4px' }}>
                  {uploading ? 'Uploading & checking quality...' : t('screening.dropzone_prompt')}
                </p>
                <p className="dropzone-hint" style={{ fontSize: '12px', color: '#64748B' }}>
                  {t('screening.supported_formats')}
                </p>
              </div>
            </div>
          </div>

          {/* Uploaded Retinal Scan Previews */}
          {images.length > 0 && (
            <div className="card mt-24">
              <div className="card-header">
                <h3 className="card-title">Uploaded Retinal Scans ({images.length})</h3>
              </div>
              <div className="card-body">
                <div className="image-grid">
                  {images.map(img => (
                    <div key={img.image_id} className="image-card" style={{
                      position: 'relative',
                      borderRadius: '8px',
                      overflow: 'hidden',
                      border: '1px solid #E2E8F0',
                      background: '#0F172A'
                    }}>
                      <button
                        type="button"
                        className="btn-delete-img"
                        onClick={() => handleDeleteImage(img.image_id)}
                        title="Remove image"
                        style={{
                          position: 'absolute',
                          top: '8px',
                          right: '8px',
                          background: 'rgba(0,0,0,0.6)',
                          color: '#fff',
                          border: 'none',
                          borderRadius: '50%',
                          width: '28px',
                          height: '28px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          cursor: 'pointer',
                          zIndex: 2
                        }}
                      >
                        <X size={15} />
                      </button>

                      <img
                        src={`${BACKEND_URL}${img.preview_url}`}
                        alt="Retinal Fundus Scan"
                        style={{ width: '100%', height: '180px', objectFit: 'cover' }}
                      />

                      <div className="image-card-info" style={{
                        padding: '10px 12px',
                        background: '#FFFFFF',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center'
                      }}>
                        <div className="image-label" style={{ fontSize: '13px', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Eye size={15} /> {img.eye_label?.toUpperCase()} EYE
                        </div>
                        <StatusBadge status={img.quality_status} type="quality" />
                      </div>

                      {img.quality_details?.message && (
                        <div style={{ padding: '6px 12px', fontSize: '11px', background: '#F8FAFC', color: '#64748B', borderTop: '1px solid #F1F5F9' }}>
                          {img.quality_details.message}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar: Step status and Process Action */}
        <div className="screening-sidebar">
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Screening Workflow</h2>
            </div>
            <div className="card-body">
              {analyzing ? (
                <div style={{ textAlign: 'center', padding: '24px 0' }}>
                  <LoadingSpinner message={t('screening.progress.analyzing')} />
                  <p style={{ fontSize: '12px', color: '#64748B', marginTop: '12px' }}>
                    Running neural network inference &amp; vascular Grad-CAM...
                  </p>
                </div>
              ) : (
                <div className="status-container">
                  <div className={`status-step ${hasImages ? 'active' : ''}`}>
                    <CheckCircle size={18} /> 1. Upload Retinal Scan
                  </div>
                  <div className={`status-step ${hasImages ? 'active' : ''}`}>
                    <CheckCircle size={18} /> 2. Automated Quality Check
                  </div>
                  <div className="status-step">
                    <CheckCircle size={18} /> 3. AI Inference &amp; Attention
                  </div>

                  {ungradableOnly && (
                    <div style={{
                      margin: '16px 0',
                      padding: '10px',
                      borderRadius: '6px',
                      background: '#FEF2F2',
                      border: '1px solid #FCA5A5',
                      fontSize: '12px',
                      color: '#991B1B'
                    }}>
                      <AlertCircle size={14} style={{ display: 'inline', marginRight: '4px' }} />
                      Image quality is UNGRADABLE. Processing will record an Inconclusive Referral recommendation.
                    </div>
                  )}

                  {/* Clear Process Screening Button */}
                  <button
                    type="button"
                    className="btn btn-primary w-100 mt-24"
                    onClick={handleProcessScreening}
                    disabled={!hasImages || analyzing}
                    style={{
                      height: '46px',
                      fontSize: '15px',
                      fontWeight: '600',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px'
                    }}
                  >
                    <Play size={18} />
                    {t('screening.process_screening')}
                  </button>

                  {!hasImages && (
                    <div className="text-muted text-center mt-8" style={{ fontSize: '12px' }}>
                      Upload at least 1 image to process
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScreeningPage;
