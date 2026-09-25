import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Download } from 'lucide-react';
import { BACKEND_URL } from '../api/client';
import './pages.css';

const ReportPage = () => {
  const { reportId } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  
  const [loading, setLoading] = useState(true);
  
  const previewUrl = `${BACKEND_URL}/api/reports/preview/${reportId}`;
  const downloadUrl = `${BACKEND_URL}/api/reports/download/${reportId}`;

  return (
    <div className="page-container" style={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button className="btn btn-secondary" onClick={() => navigate(-1)}>
            <ArrowLeft size={18} /> {t('common.back')}
          </button>
          <div>
            <h1 className="page-title">Screening Report (PDF)</h1>
            <p className="page-subtitle text-muted" style={{ margin: 0 }}>Report ID: {reportId}</p>
          </div>
        </div>
        
        <a
          href={downloadUrl}
          download={`${reportId}.pdf`}
          className="btn btn-primary"
          style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <Download size={18} /> {t('history.download_report')}
        </a>
      </div>

      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {loading && (
          <div style={{ padding: '24px', textAlign: 'center', color: '#64748B' }}>
            Loading PDF preview...
          </div>
        )}
        <object
          data={previewUrl}
          type="application/pdf"
          style={{ width: '100%', height: '100%', border: 'none', background: '#525659' }}
          onLoad={() => setLoading(false)}
        >
          <div style={{ padding: '24px', textAlign: 'center' }}>
            <p>Your browser does not support embedded PDF viewing.</p>
            <a href={downloadUrl} className="btn btn-primary">
              <Download size={16} /> Download PDF File
            </a>
          </div>
        </object>
      </div>
    </div>
  );
};

export default ReportPage;
