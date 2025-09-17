import React, { useState } from 'react';

function Settings() {
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState(() => {
    return JSON.parse(localStorage.getItem('pos_settings') || '{}');
  });

  const updateSetting = (key, value) => {
    const newSettings = { ...settings, [key]: value };
    setSettings(newSettings);
    localStorage.setItem('pos_settings', JSON.stringify(newSettings));
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    window.location.reload();
  };

  if (!showSettings) {
    return (
      <button onClick={() => setShowSettings(true)} className="settings-btn">
        ⚙️
      </button>
    );
  }

  return (
    <div className="settings-modal">
      <div className="settings-content">
        <h3>Settings</h3>

        <div className="setting-group">
          <label>
            <input
              type="checkbox"
              checked={settings.darkMode || false}
              onChange={(e) => updateSetting('darkMode', e.target.checked)}
            />
            Dark Mode
          </label>
        </div>

        <div className="setting-group">
          <label>
            <input
              type="checkbox"
              checked={settings.autoSync || true}
              onChange={(e) => updateSetting('autoSync', e.target.checked)}
            />
            Auto-sync when online
          </label>
        </div>

        <div className="setting-group">
          <label>
            <input
              type="checkbox"
              checked={settings.soundEnabled || true}
              onChange={(e) => updateSetting('soundEnabled', e.target.checked)}
            />
            Enable sounds
          </label>
        </div>

        <div className="setting-group">
          <label>
            Receipt Printer:
            <select
              value={settings.printer || 'default'}
              onChange={(e) => updateSetting('printer', e.target.value)}
            >
              <option value="default">Default Printer</option>
              <option value="thermal">Thermal Printer</option>
              <option value="laser">Laser Printer</option>
            </select>
          </label>
        </div>

        <div className="setting-group">
          <label>
            Tax Rate (%):
            <input
              type="number"
              value={settings.taxRate || 10}
              onChange={(e) => updateSetting('taxRate', parseFloat(e.target.value))}
              step="0.1"
              min="0"
              max="100"
            />
          </label>
        </div>

        <div className="settings-actions">
          <button onClick={() => setShowSettings(false)} className="close-btn">
            Close
          </button>
          <button onClick={handleLogout} className="logout-btn">
            Logout
          </button>
        </div>
      </div>
    </div>
  );
}

export default Settings;