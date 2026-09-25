import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import api from '../api/client';
import { User, Calendar, ShieldCheck, Heart, MapPin, Phone, Hospital, RefreshCw, CheckCircle2 } from 'lucide-react';
import './pages.css';

const PatientRegistrationPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const editPatientId = searchParams.get('edit');

  const [generatedId, setGeneratedId] = useState('');
  const [formData, setFormData] = useState({
    infant_name: '',
    gender: 'Male',
    mother_name: '',
    father_name: '',
    date_of_birth: '',
    gestational_age_weeks: 28,
    gestational_age_days: 0,
    birth_weight_grams: 1100,
    hospital_name: '',
    city_town_village: '',
    contact_number: '',
    clinical_notes: '',
  });

  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState('');
  const [validationErrors, setValidationErrors] = useState({});

  // Fetch preview ID or existing patient for editing
  useEffect(() => {
    const initData = async () => {
      setFetching(true);
      try {
        if (editPatientId) {
          const res = await api.get(`/patients/${editPatientId}`);
          const p = res.data;
          setGeneratedId(p.patient_id);
          setFormData({
            infant_name: p.infant_name || '',
            gender: p.gender || 'Male',
            mother_name: p.mother_name || '',
            father_name: p.father_name || '',
            date_of_birth: p.date_of_birth || '',
            gestational_age_weeks: p.gestational_age_weeks ?? 28,
            gestational_age_days: p.gestational_age_days ?? 0,
            birth_weight_grams: p.birth_weight_grams ?? 1100,
            hospital_name: p.hospital_name || '',
            city_town_village: p.city_town_village || '',
            contact_number: p.contact_number || '',
            clinical_notes: p.clinical_notes || p.clinical_history || '',
          });
        } else {
          const res = await api.get('/patients/next-id');
          setGeneratedId(res.data.patient_id);
        }
      } catch (err) {
        console.error('Failed to initialize registration form', err);
      } finally {
        setFetching(false);
      }
    };
    initData();
  }, [editPatientId]);

  const handleRefreshId = async () => {
    if (editPatientId) return;
    try {
      const res = await api.get('/patients/next-id');
      setGeneratedId(res.data.patient_id);
    } catch (err) {
      console.error('Failed to refresh ID', err);
    }
  };

  const handleChange = (e) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'number' ? (value !== '' ? Number(value) : '') : value
    }));
    // Clear validation error on change
    if (validationErrors[name]) {
      setValidationErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  // Premature baby clinical age calculations
  const clinicalAges = useMemo(() => {
    if (!formData.date_of_birth) return null;
    const dob = new Date(formData.date_of_birth);
    const today = new Date();
    const diffTime = today - dob;
    if (diffTime < 0) return null;

    const chronoDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    const chronoWeeks = Math.floor(chronoDays / 7);
    const chronoRemDays = chronoDays % 7;

    const gaWeeks = Number(formData.gestational_age_weeks) || 0;
    const gaDays = Number(formData.gestational_age_days) || 0;

    const totalPmaDays = (gaWeeks * 7 + gaDays) + chronoDays;
    const pmaWeeks = Math.floor(totalPmaDays / 7);
    const pmaRemDays = totalPmaDays % 7;

    let correctedStr = '';
    if (pmaWeeks >= 40) {
      const corrDays = totalPmaDays - 280;
      const corrWeeks = Math.floor(corrDays / 7);
      const corrRem = corrDays % 7;
      correctedStr = `${corrWeeks} wks ${corrRem} days corrected`;
    } else {
      const wksUntilTerm = 40 - pmaWeeks;
      correctedStr = `Preterm (${wksUntilTerm} wks before 40w term equivalent)`;
    }

    return {
      chronoDays,
      chronoStr: `${chronoWeeks} weeks ${chronoRemDays} days (${chronoDays} days)`,
      gaStr: `${gaWeeks} weeks ${gaDays} days`,
      pmaStr: `${pmaWeeks} weeks ${pmaRemDays} days`,
      correctedStr,
    };
  }, [formData.date_of_birth, formData.gestational_age_weeks, formData.gestational_age_days]);

  const validateForm = () => {
    const errors = {};
    const todayStr = new Date().toISOString().split('T')[0];

    if (!formData.gender || !['Male', 'Female'].includes(formData.gender)) {
      errors.gender = 'Gender is required';
    }
    if (!formData.mother_name.trim()) {
      errors.mother_name = "Mother's name is required";
    }
    if (!formData.date_of_birth) {
      errors.date_of_birth = 'Date of birth is required';
    } else if (formData.date_of_birth > todayStr) {
      errors.date_of_birth = 'Date of birth cannot be in the future';
    }

    if (formData.gestational_age_weeks < 22 || formData.gestational_age_weeks > 42) {
      errors.gestational_age_weeks = 'Gestational age must be between 22 and 42 weeks';
    }
    if (formData.gestational_age_days < 0 || formData.gestational_age_days > 6) {
      errors.gestational_age_days = 'Days must be between 0 and 6';
    }
    if (formData.birth_weight_grams < 200 || formData.birth_weight_grams > 5000) {
      errors.birth_weight_grams = 'Birth weight must be between 200g and 5000g';
    }
    if (!formData.hospital_name.trim()) {
      errors.hospital_name = 'Hospital or screening center name is required';
    }
    if (!formData.city_town_village.trim()) {
      errors.city_town_village = 'City, town, or village is required';
    }
    if (!formData.contact_number.trim()) {
      errors.contact_number = 'Contact number is required';
    } else {
      const cleanDigits = formData.contact_number.replace(/\D/g, '');
      if (cleanDigits.length < 7 || cleanDigits.length > 15) {
        errors.contact_number = 'Please enter a valid phone number (7–15 digits)';
      }
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) {
      setError('Please resolve the highlighted errors before continuing.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const payload = {
        infant_name: formData.infant_name?.trim() || null,
        gender: formData.gender,
        mother_name: formData.mother_name.trim(),
        father_name: formData.father_name?.trim() || null,
        date_of_birth: formData.date_of_birth,
        gestational_age_weeks: Number(formData.gestational_age_weeks),
        gestational_age_days: Number(formData.gestational_age_days),
        birth_weight_grams: Number(formData.birth_weight_grams),
        postnatal_age_days: clinicalAges ? clinicalAges.chronoDays : null,
        hospital_name: formData.hospital_name.trim(),
        city_town_village: formData.city_town_village.trim(),
        contact_number: formData.contact_number.trim(),
        clinical_notes: formData.clinical_notes?.trim() || null,
        clinical_history: formData.clinical_notes?.trim() || null,
      };

      if (editPatientId) {
        // Update existing patient
        await api.put(`/patients/${editPatientId}`, payload);
        navigate(-1);
      } else {
        // Register new patient
        const patientRes = await api.post(`/patients/?patient_id=${generatedId}`, payload);
        const patientId = patientRes.data.patient_id;

        // Automatically start screening session
        const sessionRes = await api.post(`/screening/start?patient_id=${patientId}`);
        const sessionId = sessionRes.data.session_id;

        // Navigate directly to New Screening Page
        navigate(`/screening/${sessionId}`);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save patient information');
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">
            {editPatientId ? t('patient.edit_title') : t('patient.registration')}
          </h1>
          <p className="page-subtitle text-muted">
            {editPatientId
              ? `Updating records for Patient ID: ${editPatientId}`
              : 'Register newborn for AI-assisted Retinopathy of Prematurity screening'}
          </p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: '900px', margin: '0 auto' }}>
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <User className="text-primary" size={20} />
            <h2 className="card-title">{t('patient.info')}</h2>
          </div>
          <div className="patient-id-badge" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: '500', color: '#64748B' }}>
              {t('patient.auto_generated')}:
            </span>
            <span className="badge badge-primary" style={{ fontSize: '13px', padding: '4px 10px' }}>
              {generatedId || 'Generating...'}
            </span>
            {!editPatientId && (
              <button
                type="button"
                className="btn-icon"
                onClick={handleRefreshId}
                title="Regenerate ID"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}
              >
                <RefreshCw size={14} />
              </button>
            )}
          </div>
        </div>

        <div className="card-body">
          {error && <div className="login-error mb-16">{error}</div>}

          <form onSubmit={handleSubmit}>
            {/* Section 1: Demographics */}
            <div className="form-section-title">
              <Heart size={16} /> Infant & Parent Demographics
            </div>

            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">{t('patient.baby_name')}</label>
                <input
                  type="text"
                  name="infant_name"
                  className="form-input"
                  value={formData.infant_name}
                  onChange={handleChange}
                  placeholder="e.g. Baby of Revathi"
                />
              </div>

              <div className="form-group">
                <label className="form-label">
                  {t('patient.gender')} <span className="text-danger">*</span>
                </label>
                <select
                  name="gender"
                  className={`form-input ${validationErrors.gender ? 'input-error' : ''}`}
                  value={formData.gender}
                  onChange={handleChange}
                  required
                >
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                </select>
                {validationErrors.gender && (
                  <span className="form-error">{validationErrors.gender}</span>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">
                  {t('patient.mother_name')} <span className="text-danger">*</span>
                </label>
                <input
                  type="text"
                  name="mother_name"
                  className={`form-input ${validationErrors.mother_name ? 'input-error' : ''}`}
                  value={formData.mother_name}
                  onChange={handleChange}
                  placeholder="Mother's full name"
                  required
                />
                {validationErrors.mother_name && (
                  <span className="form-error">{validationErrors.mother_name}</span>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">{t('patient.father_name')}</label>
                <input
                  type="text"
                  name="father_name"
                  className="form-input"
                  value={formData.father_name}
                  onChange={handleChange}
                  placeholder="Father's full name"
                />
              </div>

              <div className="form-group">
                <label className="form-label">
                  {t('patient.contact_number')} <span className="text-danger">*</span>
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="tel"
                    name="contact_number"
                    className={`form-input ${validationErrors.contact_number ? 'input-error' : ''}`}
                    value={formData.contact_number}
                    onChange={handleChange}
                    placeholder="e.g. 9876543210"
                    required
                  />
                </div>
                {validationErrors.contact_number && (
                  <span className="form-error">{validationErrors.contact_number}</span>
                )}
              </div>
            </div>

            {/* Section 2: Birth Parameters */}
            <div className="form-section-title mt-24">
              <Calendar size={16} /> Gestational & Birth Parameters
            </div>

            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">
                  {t('patient.dob')} <span className="text-danger">*</span>
                </label>
                <input
                  type="date"
                  name="date_of_birth"
                  className={`form-input ${validationErrors.date_of_birth ? 'input-error' : ''}`}
                  value={formData.date_of_birth}
                  onChange={handleChange}
                  max={new Date().toISOString().split('T')[0]}
                  required
                />
                {validationErrors.date_of_birth && (
                  <span className="form-error">{validationErrors.date_of_birth}</span>
                )}
              </div>

              <div className="form-group row-group">
                <div style={{ flex: 1 }}>
                  <label className="form-label">
                    {t('patient.gestational_age')} ({t('patient.weeks')}) <span className="text-danger">*</span>
                  </label>
                  <input
                    type="number"
                    name="gestational_age_weeks"
                    className={`form-input ${validationErrors.gestational_age_weeks ? 'input-error' : ''}`}
                    value={formData.gestational_age_weeks}
                    onChange={handleChange}
                    min="22"
                    max="42"
                    required
                  />
                  {validationErrors.gestational_age_weeks && (
                    <span className="form-error">{validationErrors.gestational_age_weeks}</span>
                  )}
                </div>
                <div style={{ flex: 1 }}>
                  <label className="form-label">
                    ({t('patient.days')})
                  </label>
                  <input
                    type="number"
                    name="gestational_age_days"
                    className="form-input"
                    value={formData.gestational_age_days}
                    onChange={handleChange}
                    min="0"
                    max="6"
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">
                  {t('patient.birth_weight')} <span className="text-danger">*</span>
                </label>
                <input
                  type="number"
                  name="birth_weight_grams"
                  className={`form-input ${validationErrors.birth_weight_grams ? 'input-error' : ''}`}
                  value={formData.birth_weight_grams}
                  onChange={handleChange}
                  min="200"
                  max="5000"
                  placeholder="e.g. 1100"
                  required
                />
                {validationErrors.birth_weight_grams && (
                  <span className="form-error">{validationErrors.birth_weight_grams}</span>
                )}
              </div>
            </div>

            {/* Clinical Age Calculations Display Box */}
            {clinicalAges && (
              <div className="clinical-ages-card mt-16 p-16" style={{
                background: '#F0FDF4',
                border: '1px solid #BBF7D0',
                borderRadius: '8px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: '#166534', fontWeight: '600', fontSize: '13px' }}>
                  <CheckCircle2 size={16} /> {t('patient.clinical_age_title')}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', fontSize: '12.5px' }}>
                  <div>
                    <span className="text-muted" style={{ display: 'block' }}>{t('patient.gestational_age')}:</span>
                    <strong>{clinicalAges.gaStr}</strong>
                  </div>
                  <div>
                    <span className="text-muted" style={{ display: 'block' }}>{t('patient.chronological_age')}:</span>
                    <strong>{clinicalAges.chronoStr}</strong>
                  </div>
                  <div>
                    <span className="text-muted" style={{ display: 'block' }}>{t('patient.postmenstrual_age')}:</span>
                    <strong style={{ color: '#0369A1' }}>{clinicalAges.pmaStr}</strong>
                  </div>
                  <div>
                    <span className="text-muted" style={{ display: 'block' }}>{t('patient.corrected_age')}:</span>
                    <strong>{clinicalAges.correctedStr}</strong>
                  </div>
                </div>
              </div>
            )}

            {/* Section 3: Facility & Location */}
            <div className="form-section-title mt-24">
              <Hospital size={16} /> Center, Location & Clinical Notes
            </div>

            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">
                  {t('patient.hospital')} <span className="text-danger">*</span>
                </label>
                <input
                  type="text"
                  name="hospital_name"
                  className={`form-input ${validationErrors.hospital_name ? 'input-error' : ''}`}
                  value={formData.hospital_name}
                  onChange={handleChange}
                  placeholder="e.g. Government Rajaji Hospital, NICU Ward"
                  required
                />
                {validationErrors.hospital_name && (
                  <span className="form-error">{validationErrors.hospital_name}</span>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">
                  {t('patient.city_town_village')} <span className="text-danger">*</span>
                </label>
                <input
                  type="text"
                  name="city_town_village"
                  className={`form-input ${validationErrors.city_town_village ? 'input-error' : ''}`}
                  value={formData.city_town_village}
                  onChange={handleChange}
                  placeholder="e.g. Madurai"
                  required
                />
                {validationErrors.city_town_village && (
                  <span className="form-error">{validationErrors.city_town_village}</span>
                )}
              </div>
            </div>

            <div className="form-group mt-16">
              <label className="form-label">{t('patient.clinical_notes')}</label>
              <textarea
                name="clinical_notes"
                className="form-input"
                rows="3"
                value={formData.clinical_notes}
                onChange={handleChange}
                placeholder="Oxygen therapy history, respiratory distress syndrome, blood transfusions, sepsis, or other neonatal risk factors..."
              ></textarea>
            </div>

            {/* Action Buttons */}
            <div className="form-actions mt-24" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => navigate(-1)}
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
              >
                {loading
                  ? t('common.loading')
                  : editPatientId
                  ? t('patient.save_changes')
                  : t('patient.save_proceed')}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default PatientRegistrationPage;
