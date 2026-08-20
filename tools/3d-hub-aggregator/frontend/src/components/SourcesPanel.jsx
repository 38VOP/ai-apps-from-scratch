import React from 'react'
import { ShieldCheck, RadioTower, Plus, Trash2, RefreshCw, X } from 'lucide-react'

export default function SourcesPanel({
  activeTab,
  accounts,
  channels,
  syncingChannelId,
  showAddAccountModal,
  setShowAddAccountModal,
  showAddChannelModal,
  setShowAddChannelModal,
  accForm,
  setAccForm,
  accStep,
  setAccStep,
  accCode,
  setAccCode,
  accMsg,
  setAccMsg,
  chForm,
  setChForm,
  handleAddAccountSubmit,
  handleVerifyAccCode,
  handleRequestAccCode,
  handleDeleteAccount,
  handleAddChannelSubmit,
  handleToggleChannelEnabled,
  handleChangeChannelAccount,
  handleDeleteChannel,
  handleSyncChannel,
  getStatusLabel
}) {
  if (activeTab !== 'sources') return null

  return (
    <>
      <main className="content-area" style={{ maxWidth: 1100, margin: '0 auto', width: '100%' }}>
        <div className="sources-container">
          <div className="sources-section">
            <div className="section-header">
              <div className="section-title">
                <ShieldCheck className="text-primary" size={22} />
                <span>Telegram-акаунти</span>
              </div>
              <button className="btn btn-primary" onClick={() => setShowAddAccountModal(true)}>
                <Plus size={16} />
                <span>Додати акаунт</span>
              </button>
            </div>

            {accounts.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Немає підключених акаунтів</p>
            ) : (
              <div className="accounts-grid">
                {accounts.map(acc => (
                  <div key={acc.id} className="account-card">
                    <div className="account-header">
                      <span className="account-name">{acc.name}</span>
                      <span className={`status-pill ${acc.is_authorized ? 'active' : 'idle'}`}>
                        {acc.is_authorized ? '🟢 З\'єднано' : '⚪ Не авторизовано'}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      Телефон: {acc.phone_number || 'Не вказано'}
                    </div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--text-dim)' }}>
                      Прив'язано каналів: {acc.channels_count}
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDeleteAccount(acc.id)}>
                        <Trash2 size={14} />
                        <span>Видалити</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="sources-section">
            <div className="section-header">
              <div className="section-title">
                <RadioTower className="text-cyan" size={22} />
                <span>Telegram-канали для моніторингу</span>
              </div>
              <button className="btn btn-secondary" onClick={() => setShowAddChannelModal(true)}>
                <Plus size={16} />
                <span>Додати канал</span>
              </button>
            </div>

            {channels.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Список каналів порожній</p>
            ) : (
              <table className="channels-table">
                <thead>
                  <tr>
                    <th>Назва каналу</th>
                    <th>Прив'язаний акаунт</th>
                    <th>Статус</th>
                    <th>Прогрес</th>
                    <th>Останнє оновлення</th>
                    <th>Моделей</th>
                    <th>Моніторинг</th>
                    <th style={{ textAlign: 'right' }}>Дії</th>
                  </tr>
                </thead>
                <tbody>
                  {channels.map(ch => (
                    <tr key={ch.id}>
                      <td style={{ fontWeight: 600 }}>
                        {ch.title}
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 400 }}>
                          @{ch.username || ch.telegram_id}
                        </div>
                      </td>

                      <td>
                        <select
                          className="form-select"
                          style={{ padding: '6px 10px', fontSize: '0.82rem' }}
                          value={ch.account_id || ''}
                          onChange={(e) => handleChangeChannelAccount(ch.id, e.target.value)}
                        >
                          <option value="">Не призначено</option>
                          {accounts.map(acc => (
                            <option key={acc.id} value={acc.id}>{acc.name}</option>
                          ))}
                        </select>
                      </td>

                      <td>
                        <span className={`status-pill ${
                          ch.status === 'queued' ? 'idle' :
                          ch.status === 'backlog' ? 'idle' :
                          ch.status === 'monitoring' || ch.status === 'up_to_date' ? 'active' :
                          ch.status === 'error' ? 'error' : 'idle'
                        }`}>
                          {getStatusLabel(ch.status)}
                        </span>
                      </td>

                      <td>
                        {ch.total_posts > 0 && (
                          <div className="progress-bar">
                            <div
                              className="progress-fill"
                              style={{ width: `${Math.round((ch.processed_count / ch.total_posts) * 100)}%` }}
                            />
                            <span className="progress-text">
                              {Math.round((ch.processed_count / ch.total_posts) * 100)}%
                            </span>
                          </div>
                        )}
                      </td>

                      <td style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                        {ch.last_synced_at ? new Date(ch.last_synced_at).toLocaleString('uk-UA') : 'Ніколи'}
                      </td>

                      <td>
                        <span className="badge-count" style={{ fontSize: '0.85rem' }}>{ch.processed_count}</span>
                      </td>

                      <td>
                        <label className="switch">
                          <input
                            type="checkbox"
                            checked={ch.enabled}
                            onChange={() => handleToggleChannelEnabled(ch.id, ch.enabled)}
                          />
                          <span className="slider"></span>
                        </label>
                      </td>

                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => handleSyncChannel(ch.id)}
                            disabled={syncingChannelId === ch.id || !ch.enabled}
                          >
                            <RefreshCw size={14} className={syncingChannelId === ch.id ? 'spin' : ''} />
                            <span>Синхронізувати</span>
                          </button>

                          <button className="btn btn-danger btn-sm" onClick={() => handleDeleteChannel(ch.id)}>
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </main>

      {showAddAccountModal && (
        <div className="modal-overlay" onClick={() => setShowAddAccountModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Підключити Telegram-акаунт</h2>
              <button className="btn-close" onClick={() => setShowAddAccountModal(false)}>
                <X size={20} />
              </button>
            </div>

            {accMsg && (
              <div style={{
                padding: 10,
                borderRadius: 'var(--radius-md)',
                background: 'rgba(139, 92, 246, 0.15)',
                color: 'var(--primary-light)',
                marginBottom: 16,
                fontSize: '0.85rem'
              }}>
                {accMsg}
              </div>
            )}

            {accStep === 'config' ? (
              <form onSubmit={handleAddAccountSubmit}>
                <div className="form-group">
                  <label className="form-label">Назва акаунту:</label>
                  <input
                    type="text"
                    className="form-input"
                    value={accForm.name}
                    onChange={e => setAccForm({ ...accForm, name: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">API ID (з my.telegram.org):</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="12345678"
                    value={accForm.api_id}
                    onChange={e => setAccForm({ ...accForm, api_id: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">API Hash (з my.telegram.org):</label>
                  <input
                    type="password"
                    className="form-input"
                    placeholder="abcdef123456..."
                    value={accForm.api_hash}
                    onChange={e => setAccForm({ ...accForm, api_hash: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Номер телефону:</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="+380991234567"
                    value={accForm.phone_number}
                    onChange={e => setAccForm({ ...accForm, phone_number: e.target.value })}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setShowAddAccountModal(false)}>
                    Скасувати
                  </button>
                  <button type="submit" className="btn btn-primary">
                    Зберегти та продовжити
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleVerifyAccCode}>
                <div className="form-group">
                  <label className="form-label">Код підтвердження з Telegram:</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="12345"
                    value={accCode}
                    onChange={e => setAccCode(e.target.value)}
                    autoFocus
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24 }}>
                  <button type="button" className="btn btn-secondary" onClick={handleRequestAccCode}>
                    Запитати код
                  </button>
                  <button type="submit" className="btn btn-primary">
                    Підтвердити та увійти
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {showAddChannelModal && (
        <div className="modal-overlay" onClick={() => setShowAddChannelModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Додати Telegram-канал</h2>
              <button className="btn-close" onClick={() => setShowAddChannelModal(false)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleAddChannelSubmit}>
              <div className="form-group">
                <label className="form-label">Username або посилання:</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="@3d_models_free або t.me/3d_models_free"
                  value={chForm.telegram_id}
                  onChange={e => setChForm({ ...chForm, telegram_id: e.target.value })}
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label className="form-label">Назва каналу (необов'язково):</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="3D Free Models Catalog"
                  value={chForm.title}
                  onChange={e => setChForm({ ...chForm, title: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Прив'язати до акаунту:</label>
                <select
                  className="form-select"
                  value={chForm.account_id}
                  onChange={e => setChForm({ ...chForm, account_id: e.target.value })}
                >
                  <option value="">Автоматично</option>
                  {accounts.map(acc => (
                    <option key={acc.id} value={acc.id}>{acc.name}</option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowAddChannelModal(false)}>
                  Скасувати
                </button>
                <button type="submit" className="btn btn-primary">
                  Додати канал
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}

