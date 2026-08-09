import React, { useState, useEffect } from 'react'
import { 
  Search, RefreshCw, Box, ExternalLink, Filter, Plus, 
  Settings, FolderPlus, CheckCircle, AlertCircle, X, Edit2, Trash2
} from 'lucide-react'

export default function App() {
  const [models, setModels] = useState([])
  const [categories, setCategories] = useState([])
  const [channels, setChannels] = useState([])
  const [totalModels, setTotalModels] = useState(0)
  
  // Filters state
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [selectedFormat, setSelectedFormat] = useState(null)
  const [selectedRender, setSelectedRender] = useState(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncMessage, setSyncMessage] = useState('')

  // Modals state
  const [selectedModel, setSelectedModel] = useState(null)
  const [showCategoryModal, setShowCategoryModal] = useState(false)
  const [showTelegramModal, setShowTelegramModal] = useState(false)
  
  // Telegram form state
  const [tgConfig, setTgConfig] = useState({ api_id: '', api_hash: '', phone_number: '', is_authorized: false })
  const [tgCode, setTgCode] = useState('')
  const [tgStep, setTgStep] = useState('config') // 'config' | 'code'
  const [tgStatusMsg, setTgStatusMsg] = useState('')

  // New category form state
  const [newCatName, setNewCatName] = useState('')

  // Fetch initial data
  useEffect(() => {
    fetchCategories()
    fetchChannels()
    fetchTelegramConfig()
  }, [])

  // Fetch models whenever filters change
  useEffect(() => {
    fetchModels()
  }, [selectedCategory, selectedFormat, selectedRender, searchQuery])

  const fetchModels = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (searchQuery) params.append('search', searchQuery)
      if (selectedCategory) params.append('category_id', selectedCategory)
      if (selectedFormat) params.append('file_format', selectedFormat)
      if (selectedRender) params.append('render_engine', selectedRender)

      const res = await fetch(`/api/models?${params.toString()}`)
      const data = await res.json()
      setModels(data.items || [])
      setTotalModels(data.total || 0)
    } catch (err) {
      console.error('Error loading models:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchCategories = async () => {
    try {
      const res = await fetch('/api/categories')
      const data = await res.json()
      setCategories(data)
    } catch (err) {
      console.error('Error loading categories:', err)
    }
  }

  const fetchChannels = async () => {
    try {
      const res = await fetch('/api/channels')
      const data = await res.json()
      setChannels(data)
    } catch (err) {
      console.error('Error loading channels:', err)
    }
  }

  const fetchTelegramConfig = async () => {
    try {
      const res = await fetch('/api/telegram/config')
      const data = await res.json()
      setTgConfig(data)
    } catch (err) {
      console.error('Error loading TG config:', err)
    }
  }

  const handleSyncAll = async () => {
    if (channels.length === 0) return
    setSyncing(true)
    setSyncMessage('Синхронізація з Telegram-каналами...')
    try {
      const firstChannel = channels[0]
      const res = await fetch(`/api/channels/${firstChannel.id}/sync`, { method: 'POST' })
      const data = await res.json()
      setSyncMessage(data.message)
      fetchModels()
      fetchCategories()
    } catch (err) {
      setSyncMessage('Помилка під час синхронізації')
    } finally {
      setSyncing(false)
      setTimeout(() => setSyncMessage(''), 4000)
    }
  }

  const handleUpdateModelCategory = async (modelId, newCatId) => {
    try {
      const res = await fetch(`/api/models/${modelId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category_id: newCatId })
      })
      if (res.ok) {
        fetchModels()
        fetchCategories()
        setSelectedModel(prev => prev ? { ...prev, category_id: newCatId } : null)
      }
    } catch (err) {
      console.error('Error updating category:', err)
    }
  }

  const handleCreateCategory = async (e) => {
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
        setShowCategoryModal(false)
        fetchCategories()
      }
    } catch (err) {
      console.error('Error creating category:', err)
    }
  }

  const handleSaveTgConfig = async (e) => {
    e.preventDefault()
    setTgStatusMsg('')
    try {
      const res = await fetch('/api/telegram/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_id: tgConfig.api_id,
          api_hash: tgConfig.api_hash,
          phone_number: tgConfig.phone_number
        })
      })
      const data = await res.json()
      setTgStatusMsg(data.message)
    } catch (err) {
      setTgStatusMsg('Помилка збереження налаштувань')
    }
  }

  const handleRequestCode = async () => {
    setTgStatusMsg('Надсилання коду у Telegram...')
    try {
      const res = await fetch('/api/telegram/request-code', { method: 'POST' })
      const data = await res.json()
      setTgStatusMsg(data.message)
      if (data.success) {
        setTgStep('code')
      }
    } catch (err) {
      setTgStatusMsg('Помилка при запиті коду')
    }
  }

  const handleSignInCode = async (e) => {
    e.preventDefault()
    setTgStatusMsg('Перевірка коду...')
    try {
      const res = await fetch('/api/telegram/sign-in', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: tgCode })
      })
      const data = await res.json()
      setTgStatusMsg(data.message)
      if (data.success) {
        setTgConfig(prev => ({ ...prev, is_authorized: true }))
        setTimeout(() => setShowTelegramModal(false), 1500)
      }
    } catch (err) {
      setTgStatusMsg('Помилка входу')
    }
  }

  const formatList = ['3ds Max', 'FBX', 'OBJ', 'Blender']
  const renderList = ['Corona', 'V-Ray', 'Cycles']

  return (
    <div className="app-container">
      {/* HEADER */}
      <header className="app-header">
        <div className="logo-group">
          <div className="logo-icon">
            <Box size={24} />
          </div>
          <div>
            <h1 className="logo-title">3D Hub Catalog</h1>
            <p className="logo-subtitle">Агрегатор Telegram-моделей для 3ds Max</p>
          </div>
        </div>

        {/* SEARCH BOX */}
        <div className="search-box">
          <Search className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Пошук за назвою або описом..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {/* ACTIONS */}
        <div className="header-actions">
          <button 
            className="btn btn-secondary"
            onClick={() => setShowTelegramModal(true)}
            title="Налаштування Telegram підключення"
          >
            <Settings size={18} />
            <span>Telegram</span>
            {tgConfig.is_authorized ? (
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981' }} />
            ) : null}
          </button>

          <button 
            className="btn btn-primary"
            onClick={handleSyncAll}
            disabled={syncing}
          >
            <RefreshCw size={18} className={syncing ? 'spin' : ''} />
            <span>{syncing ? 'Синхронізація...' : 'Синхронізувати'}</span>
          </button>
        </div>
      </header>

      {/* SYNC NOTIFICATION TOAST */}
      {syncMessage && (
        <div style={{
          background: 'var(--primary)',
          color: '#fff',
          padding: '10px 24px',
          textAlign: 'center',
          fontSize: '0.88rem',
          fontWeight: 600
        }}>
          {syncMessage}
        </div>
      )}

      {/* MAIN CONTENT LAYOUT */}
      <div className="main-layout">
        {/* SIDEBAR */}
        <aside className="sidebar">
          {/* CATEGORIES */}
          <div>
            <div className="sidebar-section-title">
              <span>Категорії</span>
              <button 
                onClick={() => setShowCategoryModal(true)}
                style={{ background: 'none', border: 'none', color: 'var(--primary-light)', cursor: 'pointer' }}
                title="Додати категорію"
              >
                <Plus size={16} />
              </button>
            </div>
            
            <ul className="nav-list">
              <li 
                className={`nav-item ${selectedCategory === null ? 'active' : ''}`}
                onClick={() => setSelectedCategory(null)}
              >
                <span>Усі категорії</span>
                <span className="badge-count">{totalModels}</span>
              </li>

              {categories.map(cat => (
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

          {/* FILE FORMAT FILTER */}
          <div>
            <div className="sidebar-section-title">Формат файлу</div>
            <div className="tags-cloud">
              {formatList.map(fmt => (
                <button
                  key={fmt}
                  className={`tag-btn ${selectedFormat === fmt ? 'active' : ''}`}
                  onClick={() => setSelectedFormat(selectedFormat === fmt ? null : fmt)}
                >
                  .{fmt.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* RENDER ENGINE FILTER */}
          <div>
            <div className="sidebar-section-title">Рендер Рушій</div>
            <div className="tags-cloud">
              {renderList.map(rnd => (
                <button
                  key={rnd}
                  className={`tag-btn ${selectedRender === rnd ? 'active' : ''}`}
                  onClick={() => setSelectedRender(selectedRender === rnd ? null : rnd)}
                >
                  {rnd}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* CONTENT AREA */}
        <main className="content-area">
          <div className="content-header">
            <div>
              <span className="results-info">Каталог моделей</span>
              <span className="results-count">({models.length} з {totalModels})</span>
            </div>
          </div>

          {loading ? (
            <div className="empty-state">
              <RefreshCw size={36} className="spin" />
              <p>Завантаження моделей...</p>
            </div>
          ) : models.length === 0 ? (
            <div className="empty-state">
              <Box className="empty-icon" />
              <h3>Моделей не знайдено</h3>
              <p>Спробуйте змінити параметри пошуку або натисніть «Синхронізувати»</p>
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
                    <div className="card-overlay-badge">
                      {model.category_name}
                    </div>
                  </div>

                  <div className="card-body">
                    <h3 className="card-title">{model.title}</h3>
                    
                    <div className="card-tags">
                      {model.file_formats.map(fmt => (
                        <span key={fmt} className="badge-format">.{fmt}</span>
                      ))}
                      {model.render_engines.map(rnd => (
                        <span key={rnd} className="badge-render">{rnd}</span>
                      ))}
                    </div>

                    <div className="card-footer" onClick={(e) => e.stopPropagation()}>
                      <span className="channel-name">{model.channel_title}</span>
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

      {/* MODEL DETAIL & CATEGORY CHANGER MODAL */}
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
                  <label className="form-label">Змінити категорію моделі:</label>
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

                <div className="card-tags">
                  {selectedModel.file_formats.map(fmt => (
                    <span key={fmt} className="badge-format">.{fmt}</span>
                  ))}
                  {selectedModel.render_engines.map(rnd => (
                    <span key={rnd} className="badge-render">{rnd}</span>
                  ))}
                </div>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Опис з Telegram:</label>
              <p style={{ 
                fontSize: '0.88rem', 
                color: 'var(--text-muted)', 
                background: 'rgba(0,0,0,0.3)', 
                padding: 12, 
                borderRadius: 'var(--radius-md)', 
                whiteSpace: 'pre-wrap' 
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

      {/* CREATE CATEGORY MODAL */}
      {showCategoryModal && (
        <div className="modal-overlay" onClick={() => setShowCategoryModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Створити нову категорію</h2>
              <button className="btn-close" onClick={() => setShowCategoryModal(false)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateCategory}>
              <div className="form-group">
                <label className="form-label">Назва категорії:</label>
                <input 
                  type="text" 
                  className="form-input" 
                  placeholder="наприклад: Сантехніка, Текстиль..." 
                  value={newCatName}
                  onChange={(e) => setNewCatName(e.target.value)}
                  autoFocus
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowCategoryModal(false)}>
                  Скасувати
                </button>
                <button type="submit" className="btn btn-primary">
                  Створити
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* TELEGRAM CONFIG & AUTH MODAL */}
      {showTelegramModal && (
        <div className="modal-overlay" onClick={() => setShowTelegramModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Налаштування Telegram API</h2>
              <button className="btn-close" onClick={() => setShowTelegramModal(false)}>
                <X size={20} />
              </button>
            </div>

            {tgStatusMsg && (
              <div style={{
                padding: 10,
                borderRadius: 'var(--radius-md)',
                background: 'rgba(139, 92, 246, 0.15)',
                color: 'var(--primary-light)',
                marginBottom: 16,
                fontSize: '0.85rem'
              }}>
                {tgStatusMsg}
              </div>
            )}

            {tgStep === 'config' ? (
              <form onSubmit={handleSaveTgConfig}>
                <div className="form-group">
                  <label className="form-label">API ID (з my.telegram.org):</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    value={tgConfig.api_id}
                    onChange={(e) => setTgConfig({ ...tgConfig, api_id: e.target.value })}
                    placeholder="12345678"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">API Hash (з my.telegram.org):</label>
                  <input 
                    type="password" 
                    className="form-input" 
                    value={tgConfig.api_hash}
                    onChange={(e) => setTgConfig({ ...tgConfig, api_hash: e.target.value })}
                    placeholder="abcdef1234567890..."
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Номер телефону (міжнародний формат):</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    value={tgConfig.phone_number}
                    onChange={(e) => setTgConfig({ ...tgConfig, phone_number: e.target.value })}
                    placeholder="+380991234567"
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginTop: 24 }}>
                  <button type="submit" className="btn btn-secondary">
                    Зберегти дані
                  </button>

                  <button type="button" className="btn btn-primary" onClick={handleRequestCode}>
                    Отримати код авторизації
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleSignInCode}>
                <div className="form-group">
                  <label className="form-label">Код підтвердження з Telegram:</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    value={tgCode}
                    onChange={(e) => setTgCode(e.target.value)}
                    placeholder="12345"
                    autoFocus
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginTop: 24 }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setTgStep('config')}>
                    Назад
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
    </div>
  )
}
