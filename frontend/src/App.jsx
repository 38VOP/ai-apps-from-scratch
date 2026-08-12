import React, { useState, useEffect } from 'react'
import { 
  Box, Search, RefreshCw, ExternalLink, Plus, Settings, 
  Trash2, Edit2, Eye, EyeOff, ArrowUp, ArrowDown, Radio, CheckCircle, 
  AlertCircle, ShieldCheck, Layers, RadioTower, Check, X
} from 'lucide-react'

export default function App() {
  const [activeTab, setActiveTab] = useState('catalog') // 'catalog' | 'sources'
  
  // Catalog State
  const [models, setModels] = useState([])
  const [categories, setCategories] = useState([])
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [totalModels, setTotalModels] = useState(0)
  const [loadingModels, setLoadingModels] = useState(false)
  const [selectedModel, setSelectedModel] = useState(null)

  // Sources State
  const [accounts, setAccounts] = useState([])
  const [channels, setChannels] = useState([])
  const [syncingChannelId, setSyncingChannelId] = useState(null)
  const [globalSyncMsg, setGlobalSyncMsg] = useState('')

  // Modals
  const [showCatManagerModal, setShowCatManagerModal] = useState(false)
  const [showAddAccountModal, setShowAddAccountModal] = useState(false)
  const [showAddChannelModal, setShowAddChannelModal] = useState(false)

  // Forms State
  const [newCatName, setNewCatName] = useState('')

  // Account Form
  const [accForm, setAccForm] = useState({ name: 'Основний акаунт', api_id: '', api_hash: '', phone_number: '' })
  const [accStep, setAccStep] = useState('config') // 'config' | 'code'
  const [accCreatedId, setAccCreatedId] = useState(null)
  const [accCode, setAccCode] = useState('')
  const [accMsg, setAccMsg] = useState('')

  // Channel Form
  const [chForm, setChForm] = useState({ telegram_id: '', title: '', account_id: '' })

  useEffect(() => {
    fetchUserCategories()
    fetchAccounts()
    fetchChannels()
  }, [])

  useEffect(() => {
    if (activeTab === 'catalog') {
      fetchModels()
    }
  }, [activeTab, selectedCategory, searchQuery])

  // --- API CALLS ---

  const fetchModels = async () => {
    setLoadingModels(true)
    try {
      const params = new URLSearchParams()
      if (searchQuery) params.append('search', searchQuery)
      if (selectedCategory) params.append('category_id', selectedCategory)

      const res = await fetch(`/api/models?${params.toString()}`)
      const data = await res.json()
      setModels(data.items || [])
      setTotalModels(data.total || 0)
    } catch (err) {
      console.error('Error fetching models:', err)
    } finally {
      setLoadingModels(false)
    }
  }

  const fetchUserCategories = async (all = false) => {
    try {
      const res = await fetch(`/api/categories?visible_only=${all ? 'false' : 'true'}`)
      const data = await res.json()
      setCategories(data)
    } catch (err) {
      console.error('Error fetching categories:', err)
    }
  }

  const fetchAccounts = async () => {
    try {
      const res = await fetch('/api/accounts')
      const data = await res.json()
      setAccounts(data)
    } catch (err) {
      console.error('Error fetching accounts:', err)
    }
  }

  const fetchChannels = async () => {
    try {
      const res = await fetch('/api/channels')
      const data = await res.json()
      setChannels(data)
    } catch (err) {
      console.error('Error fetching channels:', err)
    }
  }

  // --- HANDLERS ---

  const handleSyncChannel = async (channelId) => {
    setSyncingChannelId(channelId)
    try {
      const res = await fetch(`/api/channels/${channelId}/sync`, { method: 'POST' })
      const data = await res.json()
      setGlobalSyncMsg(data.message)
      fetchChannels()
      fetchModels()
      fetchUserCategories()
    } catch (err) {
      setGlobalSyncMsg('Помилка під час синхронізації')
    } finally {
      setSyncingChannelId(null)
      setTimeout(() => setGlobalSyncMsg(''), 4000)
    }
  }

  const handleToggleChannelEnabled = async (channelId, currentVal) => {
    try {
      await fetch(`/api/channels/${channelId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !currentVal })
      })
      fetchChannels()
    } catch (err) {
      console.error('Error toggling channel:', err)
    }
  }

  const handleChangeChannelAccount = async (channelId, accountId) => {
    try {
      await fetch(`/api/channels/${channelId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: Number(accountId) })
      })
      fetchChannels()
    } catch (err) {
      console.error('Error updating channel account:', err)
    }
  }

  const handleDeleteChannel = async (channelId) => {
    if (!window.confirm('Видалити цей канал з моніторингу?')) return
    try {
      await fetch(`/api/channels/${channelId}`, { method: 'DELETE' })
      fetchChannels()
    } catch (err) {
      console.error('Error deleting channel:', err)
    }
  }

  const handleAddAccountSubmit = async (e) => {
    e.preventDefault()
    setAccMsg('Збереження акаунту...')
    try {
      const res = await fetch('/api/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(accForm)
      })
      const data = await res.json()
      if (res.ok) {
        setAccCreatedId(data.id)
        setAccStep('code')
        setAccMsg('Акаунт створено. Для підключення натисніть «Запитати код»')
        fetchAccounts()
      } else {
        setAccMsg(data.detail || 'Помилка створення')
      }
    } catch (err) {
      setAccMsg('Помилка зєднання')
    }
  }

  const handleRequestAccCode = async () => {
    if (!accCreatedId) return
    setAccMsg('Надсилання коду у Telegram...')
    try {
      const res = await fetch(`/api/accounts/${accCreatedId}/request-code`, { method: 'POST' })
      const data = await res.json()
      setAccMsg(data.message)
    } catch (err) {
      setAccMsg('Помилка надсилання коду')
    }
  }

  const handleVerifyAccCode = async (e) => {
    e.preventDefault()
    setAccMsg('Перевірка коду...')
    try {
      const res = await fetch(`/api/accounts/${accCreatedId}/sign-in`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: accCode })
      })
      const data = await res.json()
      setAccMsg(data.message)
      if (data.success) {
        fetchAccounts()
        setTimeout(() => {
          setShowAddAccountModal(false)
          setAccStep('config')
          setAccMsg('')
        }, 1200)
      }
    } catch (err) {
      setAccMsg('Помилка підтвердження коду')
    }
  }

  const handleDeleteAccount = async (accId) => {
    if (!window.confirm('Видалити цей Telegram-акаунт?')) return
    try {
      await fetch(`/api/accounts/${accId}`, { method: 'DELETE' })
      fetchAccounts()
      fetchChannels()
    } catch (err) {
      console.error('Error deleting account:', err)
    }
  }

  const handleAddChannelSubmit = async (e) => {
    e.preventDefault()
    if (!chForm.telegram_id.trim()) return
    try {
      const res = await fetch('/api/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          telegram_id_or_username: chForm.telegram_id,
          title: chForm.title || undefined,
          account_id: chForm.account_id ? Number(chForm.account_id) : undefined
        })
      })
      if (res.ok) {
        setShowAddChannelModal(false)
        setChForm({ telegram_id: '', title: '', account_id: '' })
        fetchChannels()
      }
    } catch (err) {
      console.error('Error adding channel:', err)
    }
  }

  // --- CATEGORIES MANAGEMENT HANDLERS ---

  const handleToggleCategoryVisibility = async (catId, currentVal) => {
    try {
      await fetch(`/api/categories/${catId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_visible: !currentVal })
      })
      fetchUserCategories(true)
    } catch (err) {
      console.error('Error toggling visibility:', err)
    }
  }

  const handleMoveCategoryOrder = async (catId, direction) => {
    const idx = categories.findIndex(c => c.id === catId)
    if (idx === -1) return
    const newIdx = direction === 'up' ? idx - 1 : idx + 1
    if (newIdx < 0 || newIdx >= categories.length) return

    const newCats = [...categories]
    const temp = newCats[idx]
    newCats[idx] = newCats[newIdx]
    newCats[newIdx] = temp

    setCategories(newCats)
    
    // Save reorder to backend
    const ids = newCats.map(c => c.id)
    try {
      await fetch('/api/categories/reorder', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category_ids: ids })
      })
    } catch (err) {
      console.error('Error saving reorder:', err)
    }
  }

  const handleCreateNewCategory = async (e) => {
    e.preventDefault()
    if (!newCatName.trim()) return
    try {
      const res = await fetch('/api/categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newCatName })
      })
      if (res.ok) {
        setNewCatName('')
        fetchUserCategories(true)
      }
    } catch (err) {
      console.error('Error creating category:', err)
    }
  }

  const handleDeleteCategory = async (catId) => {
    if (!window.confirm('Видалити цю категорію? Моделі будуть перенесені в "Інше"')) return
    try {
      await fetch(`/api/categories/${catId}`, { method: 'DELETE' })
      fetchUserCategories(true)
    } catch (err) {
      console.error('Error deleting category:', err)
    }
  }

  const handleUpdateModelCategory = async (modelId, newCatId) => {
    try {
      await fetch(`/api/models/${modelId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category_id: newCatId })
      })
      fetchModels()
      fetchUserCategories()
      setSelectedModel(prev => prev ? { ...prev, category_id: newCatId } : null)
    } catch (err) {
      console.error('Error updating category:', err)
    }
  }

  return (
    <div className="app-container">
      {/* HEADER */}
      <header className="app-header">
        <div className="logo-group">
          <div className="logo-icon">
            <Box size={24} />
          </div>
          <div>
            <h1 className="logo-title">3D Hub Aggregator</h1>
            <p className="logo-subtitle">Каталог моделей з Telegram для 3ds Max</p>
          </div>
        </div>

        {/* TABS NAVIGATION */}
        <div className="nav-tabs">
          <button 
            className={`tab-btn ${activeTab === 'catalog' ? 'active' : ''}`}
            onClick={() => { setActiveTab('catalog'); fetchUserCategories(); }}
          >
            <Box size={18} />
            <span>Каталог моделей</span>
          </button>

          <button 
            className={`tab-btn ${activeTab === 'sources' ? 'active' : ''}`}
            onClick={() => { setActiveTab('sources'); fetchAccounts(); fetchChannels(); }}
          >
            <RadioTower size={18} />
            <span>Джерела Telegram</span>
          </button>
        </div>

        {/* SEARCH & ACTIONS */}
        {activeTab === 'catalog' ? (
          <div className="search-box">
            <Search className="search-icon" />
            <input
              type="text"
              className="search-input"
              placeholder="Пошук моделей..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        ) : (
          <button className="btn btn-primary" onClick={() => setShowAddChannelModal(true)}>
            <Plus size={18} />
            <span>Додати канал</span>
          </button>
        )}
      </header>

      {/* SYNC TOAST */}
      {globalSyncMsg && (
        <div style={{
          background: 'var(--primary)', color: '#fff', padding: '10px 24px',
          textAlign: 'center', fontSize: '0.88rem', fontWeight: 600
        }}>
          {globalSyncMsg}
        </div>
      )}

      {/* MAIN CONTENT AREA */}
      {activeTab === 'catalog' ? (
        <div className="main-layout">
          {/* USER CUSTOMIZABLE SIDEBAR */}
          <aside className="sidebar">
            <div>
              <div className="sidebar-title">Мої Категорії</div>
              
              <ul className="nav-list">
                <li 
                  className={`nav-item ${selectedCategory === null ? 'active' : ''}`}
                  onClick={() => setSelectedCategory(null)}
                >
                  <span>Усі категорії</span>
                  <span className="badge-count">{totalModels}</span>
                </li>

                {categories.filter(c => c.is_visible).map(cat => (
                  <li
                    key={cat.id}
                    className={`nav-item ${selectedCategory === cat.id ? 'active' : ''}`}
                    onClick={() => setSelectedCategory(cat.id)}
                  >
                    <span>{cat.name}</span>
                    <span className="badge-count">{cat.count}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* CONFIGURE CATEGORIES BUTTON */}
            <button 
              className="btn btn-secondary" 
              style={{ width: '100%', marginTop: 24, justifyContent: 'center' }}
              onClick={() => { fetchUserCategories(true); setShowCatManagerModal(true); }}
            >
              <Settings size={16} />
              <span>Налаштувати категорії</span>
            </button>
          </aside>

          {/* CATALOG MODELS GRID */}
          <main className="content-area">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                Каталог моделей <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)', fontWeight: 500 }}>({models.length})</span>
              </h2>
            </div>

            {loadingModels ? (
              <div className="empty-state">
                <RefreshCw size={36} className="spin" />
                <p>Завантаження моделей...</p>
              </div>
            ) : models.length === 0 ? (
              <div className="empty-state">
                <Box size={48} />
                <h3>Моделей не знайдено</h3>
                <p>Спробуйте обрати іншу категорію або додайте нові канали у розділі «Джерела Telegram»</p>
              </div>
            ) : (
              <div className="models-grid">
                {models.map(model => (
                  <div 
                    key={model.id} 
                    className="model-card"
                    onClick={() => setSelectedModel(model)}
                    style={{ cursor: 'pointer' }}
                  >
                    <div className="card-media">
                      <img 
                        src={model.preview_path || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&q=80'} 
                        alt={model.title} 
                        className="card-img" 
                      />
                      <div className="card-badge">{model.category_name}</div>
                    </div>

                    <div className="card-body">
                      <h3 className="card-title">{model.title}</h3>

                      <div className="card-footer" onClick={e => e.stopPropagation()}>
                        <span className="channel-badge">{model.channel_title}</span>
                        <a 
                          href={model.telegram_post_url} 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className="btn-tg-link"
                        >
                          В Telegram ↗
                        </a>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </main>
        </div>
      ) : (
        /* TELEGRAM SOURCES MANAGEMENT VIEW */
        <main className="content-area" style={{ maxWidth: 1100, margin: '0 auto', width: '100%' }}>
          <div className="sources-container">
            {/* SECTION 1: TELEGRAM ACCOUNTS */}
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

            {/* SECTION 2: TELEGRAM CHANNELS */}
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
                            ch.status === 'initial_scan' ? 'idle' : 
                            ch.status === 'syncing' ? 'idle' : 
                            ch.status === 'up_to_date' || ch.status === 'active' ? 'active' : 
                            ch.status === 'error' ? 'error' : 'idle'
                          }`}>
                            {ch.status === 'initial_scan' ? '🔵 Initial Scan' : 
                             ch.status === 'syncing' ? '🟡 Syncing' : 
                             ch.status === 'up_to_date' || ch.status === 'active' ? '🟢 Up to Date' : 
                             ch.status === 'error' ? '🔴 Error' : '⚪ Idle'}
                          </span>
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
      )}

      {/* MODAL 1: CATEGORIES MANAGER (USER CONTROLLED) */}
      {showCatManagerModal && (
        <div className="modal-overlay" onClick={() => setShowCatManagerModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Налаштування моєї панелі категорій</h2>
              <button className="btn-close" onClick={() => setShowCatManagerModal(false)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateNewCategory} style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
              <input 
                type="text" 
                className="form-input" 
                placeholder="Назва нової категорії..."
                value={newCatName}
                onChange={(e) => setNewCatName(e.target.value)}
              />
              <button type="submit" className="btn btn-primary" style={{ flexShrink: 0 }}>
                <Plus size={16} />
                <span>Створити</span>
              </button>
            </form>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {categories.map((cat, idx) => (
                <div key={cat.id} className="cat-manage-item">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <button 
                      type="button"
                      className="btn-close" 
                      onClick={() => handleToggleCategoryVisibility(cat.id, cat.is_visible)}
                      title={cat.is_visible ? "Приховати з моєї панелі" : "Показувати в моїй панелі"}
                    >
                      {cat.is_visible ? <Eye size={18} className="text-primary" /> : <EyeOff size={18} style={{ opacity: 0.4 }} />}
                    </button>
                    <span style={{ fontWeight: 600, opacity: cat.is_visible ? 1 : 0.4 }}>{cat.name}</span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <button 
                      type="button" 
                      className="btn-close"
                      disabled={idx === 0}
                      onClick={() => handleMoveCategoryOrder(cat.id, 'up')}
                    >
                      <ArrowUp size={16} />
                    </button>
                    <button 
                      type="button" 
                      className="btn-close"
                      disabled={idx === categories.length - 1}
                      onClick={() => handleMoveCategoryOrder(cat.id, 'down')}
                    >
                      <ArrowDown size={16} />
                    </button>
                    {cat.is_custom && (
                      <button 
                        type="button" 
                        className="btn-close" 
                        onClick={() => handleDeleteCategory(cat.id)}
                        style={{ color: 'var(--rose)' }}
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 24 }}>
              <button className="btn btn-primary" onClick={() => { fetchUserCategories(); setShowCatManagerModal(false); }}>
                Готово
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: ADD TELEGRAM ACCOUNT */}
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
                padding: 10, borderRadius: 'var(--radius-md)',
                background: 'rgba(139, 92, 246, 0.15)', color: 'var(--primary-light)',
                marginBottom: 16, fontSize: '0.85rem'
              }}>
                {accMsg}
              </div>
            )}

            {accStep === 'config' ? (
              <form onSubmit={handleAddAccountSubmit}>
                <div className="form-group">
                  <label className="form-label">Назва акаунту (для вас):</label>
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
                  <label className="form-label">Номер телефону (з кодом країни):</label>
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

      {/* MODAL 3: ADD TELEGRAM CHANNEL */}
      {showAddChannelModal && (
        <div className="modal-overlay" onClick={() => setShowAddChannelModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Додати Telegram-канал для моніторингу</h2>
              <button className="btn-close" onClick={() => setShowAddChannelModal(false)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleAddChannelSubmit}>
              <div className="form-group">
                <label className="form-label">Username або посилання каналу:</label>
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
                <label className="form-label">Прив'язати до Telegram-акаунту:</label>
                <select 
                  className="form-select"
                  value={chForm.account_id}
                  onChange={e => setChForm({ ...chForm, account_id: e.target.value })}
                >
                  <option value="">Автоматично (Основний акаунт)</option>
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

      {/* MODAL 4: MODEL DETAIL & CATEGORY MOVE */}
      {selectedModel && (
        <div className="modal-overlay" onClick={() => setSelectedModel(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 680 }}>
            <div className="modal-header">
              <h2 className="modal-title">Деталі моделі</h2>
              <button className="btn-close" onClick={() => setSelectedModel(null)}>
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', gap: 20, marginBottom: 20 }}>
              <img 
                src={selectedModel.preview_path || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&q=80'} 
                alt={selectedModel.title}
                style={{ width: 220, height: 180, objectFit: 'cover', borderRadius: 'var(--radius-md)' }} 
              />
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>{selectedModel.title}</h3>

                <div className="form-group">
                  <label className="form-label">Перенести в категорію:</label>
                  <select 
                    className="form-select"
                    value={selectedModel.category_id}
                    onChange={(e) => handleUpdateModelCategory(selectedModel.id, Number(e.target.value))}
                  >
                    {categories.map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Опис з Telegram:</label>
              <p style={{ 
                fontSize: '0.88rem', color: 'var(--text-muted)', 
                background: 'rgba(0,0,0,0.3)', padding: 12, 
                borderRadius: 'var(--radius-md)', whiteSpace: 'pre-wrap' 
              }}>
                {selectedModel.description || 'Опис відсутній'}
              </p>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20, alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                Джерело: {selectedModel.channel_title}
              </span>
              <a 
                href={selectedModel.telegram_post_url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="btn btn-primary"
              >
                <ExternalLink size={16} />
                <span>Відкрити пост в Telegram</span>
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
