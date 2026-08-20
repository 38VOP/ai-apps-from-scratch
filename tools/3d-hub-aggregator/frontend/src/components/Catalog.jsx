import React from 'react'
import { Search, RefreshCw, ExternalLink, Plus, ShoppingCart, Box, Settings, X, Trash2 } from 'lucide-react'

export default function Catalog({
  activeTab, models, categories, selectedCategory, searchQuery, totalModels,
  loadingModels, selectedModel, currentPage, totalPages, catsExpanded,
  setCatsExpanded, setShowCatManagerModal, fetchUserCategories,
  setSelectedCategory, setSearchQuery, setCurrentPage, setSelectedModel,
  handleAddToCart, handleUpdateModelCategory, handleDeleteModel, handleRefreshPreview
}) {
  if (activeTab !== 'catalog') return null

  return (
    <>
      <div className="main-layout">
        <aside className="sidebar">
          <div>
            <div className="sidebar-section">
              <div className="sidebar-section-header" onClick={() => setCatsExpanded(!catsExpanded)}>
                <div className="sidebar-title" style={{ marginBottom: 0 }}>Мої Категорії</div>
                <span className="collapse-icon">{catsExpanded ? '−' : '+'}</span>
              </div>
              {catsExpanded && (
                <>
                  <ul className="nav-list">
                    <li className={"nav-item " + (selectedCategory === null ? 'active' : '')} onClick={() => { setSelectedCategory(null); setCurrentPage(1); }}>
                      <span>Усі категорії</span><span className="badge-count">{totalModels}</span>
                    </li>
                    {categories.filter(c => c.is_visible).map(cat => (
                      <li key={cat.id} className={"nav-item " + (selectedCategory === cat.id ? 'active' : '')} onClick={() => { setSelectedCategory(cat.id); setCurrentPage(1); }}>
                        <span>{cat.name}</span><span className="badge-count">{cat.count}</span>
                      </li>
                    ))}
                  </ul>
                  <button className="btn btn-secondary btn-sm" style={{ width: '100%', marginTop: 12, justifyContent: 'center' }} onClick={() => { fetchUserCategories(true); setShowCatManagerModal(true); }}>
                    <Settings size={14} /><span>Налаштувати</span>
                  </button>
                </>
              )}
            </div>
          </div>
        </aside>

        <main className="content-area">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>
              Каталог моделей <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)', fontWeight: 500 }}>({totalModels})</span>
            </h2>
          </div>

          {loadingModels ? (
            <div className="empty-state"><RefreshCw size={36} className="spin" /><p>Завантаження моделей...</p></div>
          ) : models.length === 0 ? (
            <div className="empty-state"><Box size={48} /><h3>Моделей не знайдено</h3><p>Спробуйте обрати іншу категорію або додайте нові канали у розділі «Джерела»</p></div>
          ) : (
            <>
              <div className="models-grid">
                {models.map(model => (
                  <div key={model.id} className="model-card" onClick={() => setSelectedModel(model)}>
                    <div className="card-media">
                      <img src={model.preview_path || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&q=80'} alt={model.title} className="card-img" />
                      <div className="card-badge">{model.category_name}</div>
                    </div>
                    <div className="card-body">
                      <h3 className="card-title">{model.title}</h3>
                      {(model.file_formats?.length > 0 || model.render_engines?.length > 0 || model.archive_types?.length > 0) && (
                        <div className="card-tags">
                          {model.file_formats?.map(f => <span key={"fmt-" + f} className="meta-tag meta-tag-format">{f}</span>)}
                          {model.render_engines?.map(r => <span key={"ren-" + r} className="meta-tag meta-tag-render">{r}</span>)}
                          {model.archive_types?.map(a => <span key={"arc-" + a} className="meta-tag meta-tag-archive">{a}</span>)}
                        </div>
                      )}
                      <div className="card-footer">
                        <span className="channel-badge">{model.channel_title}</span>
                        <button className="btn btn-primary btn-sm" onClick={(e) => { e.stopPropagation(); handleAddToCart(model.id); }}>
                          <ShoppingCart size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {totalPages > 1 && (
                <div className="pagination">
                  <button className="btn btn-secondary btn-sm" disabled={currentPage === 1} onClick={() => setCurrentPage(p => p - 1)}>Попередня</button>
                  <span className="page-info">Сторінка {currentPage} з {totalPages}</span>
                  <button className="btn btn-secondary btn-sm" disabled={currentPage === totalPages} onClick={() => setCurrentPage(p => p + 1)}>Наступна</button>
                </div>
              )}
            </>
          )}
        </main>
      </div>

      {selectedModel && (
        <div className="modal-overlay" onClick={() => setSelectedModel(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 700 }}>
            <div className="modal-header"><h2 className="modal-title">Деталі моделі</h2><button className="btn-close" onClick={() => setSelectedModel(null)}><X size={20} /></button></div>
            <div className="model-detail">
              <div className="detail-media"><img src={selectedModel.preview_path || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&q=80'} alt={selectedModel.title} className="detail-img" /></div>
              <div className="detail-info">
                <h3>{selectedModel.title}</h3>
                <div className="detail-meta">
                  <span><strong>Категорія:</strong> {selectedModel.category_name}</span>
                  <span><strong>Джерело:</strong> {selectedModel.channel_title}</span>
                  {selectedModel.post_date && <span><strong>Дата посту:</strong> {new Date(selectedModel.post_date).toLocaleDateString('uk-UA')}</span>}
                </div>
                {(selectedModel.file_formats?.length > 0 || selectedModel.render_engines?.length > 0 || selectedModel.archive_types?.length > 0) && (
                  <div className="card-tags">
                    {selectedModel.file_formats?.map(f => <span key={"fmt-" + f} className="meta-tag meta-tag-format">{f}</span>)}
                    {selectedModel.render_engines?.map(r => <span key={"ren-" + r} className="meta-tag meta-tag-render">{r}</span>)}
                    {selectedModel.archive_types?.map(a => <span key={"arc-" + a} className="meta-tag meta-tag-archive">{a}</span>)}
                  </div>
                )}
                <div className="form-group">
                  <label className="form-label">Перенести в категорію:</label>
                  <select className="form-select" value={selectedModel.category_id} onChange={(e) => handleUpdateModelCategory(selectedModel.id, Number(e.target.value))}>
                    {categories.map(cat => <option key={cat.id} value={cat.id}>{cat.name}</option>)}
                  </select>
                </div>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Опис з Telegram:</label>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', background: 'rgba(0,0,0,0.3)', padding: 12, borderRadius: 'var(--radius-md)', whiteSpace: 'pre-wrap' }}>
                {selectedModel.description || 'Опис відсутній'}
              </p>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20, alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-danger btn-sm" onClick={() => handleDeleteModel(selectedModel.id)}><Trash2 size={14} /><span>Видалити</span></button>
                <button className="btn btn-secondary btn-sm" onClick={() => handleRefreshPreview(selectedModel.id)}><RefreshCw size={14} /><span>Оновити прев'ю</span></button>
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <button className="btn btn-primary btn-sm" onClick={() => { handleAddToCart(selectedModel.id); setSelectedModel(null); }}><ShoppingCart size={14} /><span>Додати в кошик</span></button>
                <a href={selectedModel.telegram_post_url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary"><ExternalLink size={16} /><span>В Telegram</span></a>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}