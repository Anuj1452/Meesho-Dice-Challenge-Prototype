import React, { useState, useEffect } from 'react';
import CustomerChat from './components/CustomerChat';
import RiderApp from './components/RiderApp';
import OpsDashboard from './components/OpsDashboard';
import './index.css';

function App() {
  const [activeTab, setActiveTab] = useState('ops');
  const [theme, setTheme] = useState('light');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="brand-title">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="currentColor"/>
            <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Valmo Mitra AI <span className="badge simulated" style={{marginLeft: 8}}>Prototype</span>
        </div>
        
        <div className="tabs-container">
          <button 
            className={`tab-btn ${activeTab === 'customer' ? 'active' : ''}`}
            onClick={() => setActiveTab('customer')}
          >
            Customer Chat (WA)
          </button>
          <button 
            className={`tab-btn ${activeTab === 'rider' ? 'active' : ''}`}
            onClick={() => setActiveTab('rider')}
          >
            Rider PWA
          </button>
          <button 
            className={`tab-btn ${activeTab === 'ops' ? 'active' : ''}`}
            onClick={() => setActiveTab('ops')}
          >
            Ops Control Tower
          </button>
        </div>

        <button className="tab-btn" onClick={toggleTheme} title="Toggle Theme">
          {theme === 'light' ? '🌙 Dark Mode' : '☀️ Light Mode'}
        </button>
      </header>

      <main className="app-content">
        {activeTab === 'customer' && <CustomerChat />}
        {activeTab === 'rider' && <RiderApp />}
        {activeTab === 'ops' && <OpsDashboard />}
      </main>
    </div>
  );
}

export default App;
