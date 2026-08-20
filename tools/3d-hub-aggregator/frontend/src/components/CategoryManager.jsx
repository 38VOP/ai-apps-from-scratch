import React from 'react'
import { Plus, X, AlertCircle, CheckCircle, Zap, ArrowUp, ArrowDown, Trash2 } from 'lucide-react'

export default function CategoryManager({
  showCatManagerModal,
  setShowCatManagerModal,
  categories,
  newCatName,
  setNewCatName,
  catStatuses,
  handleCreateNewCategory,
  handleToggleCategoryStatus,
  handleMoveCategoryOrder,
  handleDeleteCategory,
  handleApplyCategoryChanges,
  fetchUserCategories
}) {
  if (!showCatManagerModal) return null

  return (
    <div className="modal-overlay" onClick={() => setShowCatManagerModal(false)}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 600 }}>
        <div className="modal-header">
          <h2 className="modal-title">Налаштування категорій</h2>
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
          </button>
        </form>

        <div className="cat-legend">
          <span><span className="cat-dot green"></span> Активна для класифікатора</span>
          <span><span className="cat-dot red"></span> Позначена на видалення</span>
          <span><span className="cat-dot neutral"></span> Нейтральна</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 16 }}>
          {categories.map((cat, idx) => {
            const status = catStatuses[cat.id] || { active: true, visible: true, markedForDeletion: false }
            const statusClass = status.markedForDeletion ? 'red' : status.active ? 'green' : 'neutral'
            const statusIcon = status.markedForDeletion ? <AlertCircle size={18} /> : status.active ? <CheckCircle size={18} /> : <Zap size={18} />
            const statusTitle = status.markedForDeletion ? 'Позначена на видалення' : status.active ? 'Активна для класифікатора' : 'Нейтральна'
            
            return (
              <div key={cat.id} className="cat-manage-item">
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <button 
                    type="button"
                    className={`cat-status-btn ${statusClass}`}
                    onClick={() => handleToggleCategoryStatus(cat.id)}
                    title={statusTitle}
                  >
                    {statusIcon}
                  </button>
                  <span style={{ 
                    fontWeight: 600, 
                    opacity: status.visible !== false ? 1 : 0.4,
                    textDecoration: status.markedForDeletion ? 'line-through' : 'none'
                  }}>
                    {cat.name}
                  </span>
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
            )
          })}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24 }}>
          <button className="btn btn-secondary" onClick={handleApplyCategoryChanges}>
            Застосувати зміни
          </button>
          <button className="btn btn-primary" onClick={() => { fetchUserCategories(); setShowCatManagerModal(false); }}>
            Готово
          </button>
        </div>
      </div>
    </div>
  )
}
