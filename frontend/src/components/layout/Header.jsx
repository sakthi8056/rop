import React from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../context/AuthContext';
import { LogOut, Globe } from 'lucide-react';
import './layout.css';

const Header = () => {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'ta' : 'en';
    i18n.changeLanguage(newLang);
  };

  return (
    <header className="header">
      <div className="header-left">
        {/* Placeholder for optional breadcrumbs or page title */}
      </div>

      <div className="header-right">
        <button className="lang-toggle" onClick={toggleLanguage} title={t('common.change_language')}>
          <Globe size={18} />
          <span>{i18n.language === 'en' ? 'தமிழ்' : 'English'}</span>
        </button>

        {user && (
          <div className="user-profile">
            <div className="user-info">
              <span className="user-name">{user.full_name}</span>
              <span className="user-role">{t(`roles.${user.role}`, user.role)}</span>
            </div>
            <button className="btn-logout" onClick={logout} title={t('common.logout')}>
              <LogOut size={18} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;
