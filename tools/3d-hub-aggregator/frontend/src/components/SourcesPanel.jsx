import React, { useState, useEffect } from 'react'
import { ShieldCheck, RadioTower, Plus, Trash2, RefreshCw, X, ArrowLeft } from 'lucide-react'

export default function SourcesPanel({
  activeTab,
  setActiveTab,
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
  accCreatedId,
  accMsg,
  setAccMsg,
  chForm,
  setChForm,
  handleAddAccountSubmit,
  handleVerifyAccCode,
  handleRequestAccCode,
  openAccountModal,
  closeAccountModal,
  handleDeleteAccount,
  handleAddChannelSubmit,
  handleToggleChannelEnabled,
  handleChangeChannelAccount,
  handleDeleteChannel,
  handleSyncChannel,
  getStatusLabel
}) {
  const [sessionStatuses, setSessionStatuses] = useState({})
  const [cardMessages, setCardMessages] = useState({})

  const handleCardReauth = async (acc) => {
    if (!acc.phone_number) {
      setCardMessages(prev => ({ ...prev, [acc.id]: { type: 'error', text: 'Вкажіть номер телефону в налаштуваннях акаунту' } }))
      return
    }
    setCardMessages(prev => ({ ...prev, [acc.id]: { type: 'info', text: 'Надсилання коду...' } }))
    try {
      const res = await fetch(`/api/accounts/${acc.id}/request-code`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        setCardMessages(prev => ({ ...prev, [acc.id]: { type: 'success', text: 'Код надіслано! Перевірте Telegram.' } }))
      } else {
        setCardMessages(prev => ({ ...prev, [acc.id]: { type: 'error', text: data.message } }))
      }
    } catch (err) {
      setCardMessages(prev => ({ ...prev, [acc.id]: { type: 'error', text: 'Помилка зєднання' } }))
    }
  }

  useEffect(() => {
    accounts.forEach(async (acc) => {
      try {
        const res = await fetch(`/api/accounts/${acc.id}/session-status`)
        const data = await res.json()
        setSessionStatuses(prev => ({ ...prev, [acc.id]: data.status }))
      } catch {
        setSessionStatuses(prev => ({ ...prev, [acc.id]: 'error' }))
      }
    })
  }, [accounts.length])

  if (activeTab !== 'sources') return null

  return (
    <>
      <main className="content-area">
        <button className="back-btn" onClick={() => setActiveTab('catalog')} title="Назад до каталогу">
          <ArrowLeft size={16} />
        </button>
        <div className="sources-container sources-two-col" style={{ maxWidth: '100%' }}>
          <div className="sources-section">
            <div className="section-header">
              <div className="section-title">
                <ShieldCheck className="text-primary" size={22} />
                <span>Telegram-акаунти</span>
              </div>
              <button className="btn btn-primary" onClick={openAccountModal}>
                <Plus size={16} />
                <span>Додати акаунт</span>
              </button>
            </div>

            {accounts.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Немає підключених акаунтів</p>
            ) : (
              <div className="accounts-grid">
                {accounts.map(acc => {
                  const sess = sessionStatuses[acc.id]
                  return (
                    <div key={acc.id} className="account-card">
                      <div className="account-header">
                        <span className="account-name">{acc.name}</span>
                        <span className={`status-pill ${acc.is_authorized ? 'active' : 'idle'}`}>
                          {acc.is_authorized ? '🟢 З\'єднано' : '⚪ Не авторизовано'}
                        </span>
                      </div>

                      {sess === 'expired' && (
                        <div style={{marginTop:6,fontSize:'0.78rem',color:'#f59e0b',display:'flex',alignItems:'center',gap:4}}>
                          ⚠️ Сесія застаріла
                        </div>
                      )}
                      {sess === 'none' && (
                        <div style={{marginTop:6,fontSize:'0.78rem',color:'var(--text-muted)'}}>
                          Сесія відсутня
                        </div>
                      )}

                      {cardMessages[acc.id] && (
                        <div style={{
                          marginTop: 6,
                          fontSize: '0.78rem',
                          color: cardMessages[acc.id].type === 'error' ? '#ef4444' :
                                 cardMessages[acc.id].type === 'success' ? '#22c55e' : 'var(--text-muted)'
                        }}>
                          {cardMessages[acc.id].text}
                        </div>
                      )}

                      <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                        Телефон: {acc.phone_number || 'Не вказано'}
                      </div>
                      <div style={{ fontSize: '0.82rem', color: 'var(--text-dim)' }}>
                        Прив'язано каналів: {acc.channels_count}
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                        <button className="btn btn-secondary btn-sm" style={{fontSize:'0.75rem',padding:'4px 8px'}} onClick={() => handleCardReauth(acc)} disabled={!acc.phone_number}>
                          <RefreshCw size={12} />
                          <span>Переавторизувати</span>
                        </button>
                        <button className="btn btn-danger btn-sm" onClick={() => handleDeleteAccount(acc.id)}>
                          <Trash2 size={14} />
                          <span>Видалити</span>
                        </button>
                      </div>
                    </div>
                  )
                })}
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
              <div className="table-scroll">
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
                        <span
                          className={`status-pill ${
                            ch.status === 'queued' ? 'idle' :
                            ch.status === 'backlog' ? 'idle' :
                            ch.status === 'monitoring' || ch.status === 'up_to_date' ? 'active' :
                            ch.status === 'error' ? 'error' : 'idle'
                          }`}
                          title={ch.status_message || getStatusLabel(ch.status)}
                          style={{ cursor: ch.status_message ? 'help' : 'default' }}
                        >
                          {getStatusLabel(ch.status)}
                          {ch.status_message && ch.status === 'error' && <span style={{marginLeft:4,fontSize:'0.7em'}}>ⓘ</span>}
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
              </div>
            )}
          </div>
        </div>

      </main>

      {showAddAccountModal && (
        <div className="modal-overlay" onClick={closeAccountModal}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Підключити Telegram-акаунт</h2>
              <button className="btn-close" onClick={closeAccountModal}>
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
                  <button type="button" className="btn btn-secondary" onClick={closeAccountModal}>
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
                    placeholder="Введіть код з Telegram"
                    value={accCode}
                    onChange={e => setAccCode(e.target.value)}
                    autoFocus
                  />
                  <div style={{fontSize:'0.75rem',color:'var(--text-muted)',marginTop:6}}>
                    Код дійсний ~120 секунд. Якщо не прийшов — натисніть «Запитати код» знову.
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24 }}>
                  <button type="button" className="btn btn-secondary" onClick={() => handleRequestAccCode(accCreatedId)}>
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

