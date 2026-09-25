import React from 'react';
import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LayoutDashboard, UserPlus, History } from 'lucide-react';
import './layout.css';

const Sidebar = () => {
  const { t } = useTranslation();

  const navItems = [
    { to: "/", icon: <LayoutDashboard size={20} />, label: "nav.dashboard" },
    { to: "/register", icon: <UserPlus size={20} />, label: "nav.new_screening" },
    { to: "/history", icon: <History size={20} />, label: "nav.history" },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon">ROP</div>
        <span className="logo-text">AI Screener</span>
      </div>
      
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink 
            key={item.to} 
            to={item.to}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            {item.icon}
            <span>{t(item.label)}</span>
          </NavLink>
        ))}
      </nav>
      
      <div className="sidebar-footer">
        <div className="prototype-badge">
          {t('prototype_notice', 'Research Prototype')}
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
