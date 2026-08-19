import React from 'react'
import { ShoppingCart, X, Trash2, FolderOpen, Plus, Check, CheckSquare, Square } from 'lucide-react'

export default function Cart({
  activeTab,
  cartItems = [],
  cartCount = 0,
  projects = [],
  showCartModal,
  setShowCartModal,
  showSaveToProjectModal,
  setShowSaveToProjectModal,
  showNewProjectModal,
  setShowNewProjectModal,
  selectedProject,
  setSelectedProject,
  newProjectName,
  setNewProjectName,
  selectedModelsForProject = [],
  setSelectedModelsForProject,
  handleRemoveFromCart,
  handleClearCart,
  handleSaveToProject,
  handleCreateProject,
  fetchProjects
}) {
  const allSelected = cartItems.length > 0 && cartItems.every(item => selectedModelsForProject.includes(item.model_id))

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedModelsForProject([])
    } else {
      setSelectedModelsForProject(cartItems.map(item => item.model_id))
    }
  }

  const toggleSelectModel = (modelId) => {
    if (selectedModelsForProject.includes(modelId)) {
      setSelectedModelsForProject(selectedModelsForProject.filter(id => id !== modelId))
    } else {
      setSelectedModelsForProject([...selectedModelsForProject, modelId])
    }
  }

  return (
    <>
      {/* MODAL: CART */}
      {showCartModal && (
        <div className="modal-overlay" onClick={() => setShowCartModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 700 }}>
            <div className="modal-header">
              <h2 className="modal-title">
                <ShoppingCart size={20} style={{ marginRight: 8 }} />
                Кошик ({cartCount})
              </h2>
              <button className="btn-close" onClick={() => setShowCartModal(false)}>
                <X size={20} />
              </button>
            </div>

            {cartItems.length === 0 ? (
              <div className="empty-state" style={{ padding: 40 }}>
                <ShoppingCart size={48} />
                <p>Кошик порожній</p>
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, paddingBottom: 8, borderBottom: '1px solid var(--border-color)' }}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={toggleSelectAll}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                  >
                    {allSelected ? <CheckSquare size={16} /> : <Square size={16} />}
                    <span>{allSelected ? 'Зняти всі' : 'Вибрати всі'}</span>
                  </button>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Вибрано: {selectedModelsForProject.length} з {cartItems.length}
                  </span>
                </div>

                <div className="cart-grid">
                  {cartItems.map(item => {
                    const isChecked = selectedModelsForProject.includes(item.model_id)
                    return (
                      <div
                        key={item.id}
                        className={`cart-item ${isChecked ? 'selected' : ''}`}
                        onClick={() => toggleSelectModel(item.model_id)}
                        style={{ cursor: 'pointer', position: 'relative' }}
                      >
                        <div
                          style={{ position: 'absolute', top: 8, left: 8, zIndex: 2 }}
                          onClick={e => e.stopPropagation()}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleSelectModel(item.model_id)}
                            style={{ width: 18, height: 18, cursor: 'pointer' }}
                          />
                        </div>


                        <img
                          src={item.preview_path || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=200&q=80'}
                          alt={item.title}
                          className="cart-item-img"
                        />
                        <div className="cart-item-info">
                          <span className="cart-item-title">{item.title}</span>
                          <span className="cart-item-cat">{item.category_name}</span>
                        </div>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleRemoveFromCart(item.id)
                          }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    )
                  })}
                </div>

                <div className="cart-actions" style={{ marginTop: 16 }}>
                  <button className="btn btn-danger" onClick={handleClearCart}>
                    <Trash2 size={16} />
                    <span>Очистити кошик</span>
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      if (selectedModelsForProject.length === 0) {
                        setSelectedModelsForProject(cartItems.map(i => i.model_id))
                      }
                      setShowSaveToProjectModal(true)
                      fetchProjects()
                    }}
                  >
                    <FolderOpen size={16} />
                    <span>Зберегти у проект</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* MODAL: SAVE TO PROJECT */}
      {showSaveToProjectModal && (
        <div className="modal-overlay" onClick={() => setShowSaveToProjectModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Зберегти у проект</h2>
              <button className="btn-close" onClick={() => setShowSaveToProjectModal(false)}>
                <X size={20} />
              </button>
            </div>

            <div className="form-group">
              <label className="form-label">Оберіть проект або створіть новий:</label>

              <div className="project-select-list">
                {projects.map(proj => (
                  <div
                    key={proj.id}
                    className={`project-select-item ${selectedProject?.id === proj.id ? 'selected' : ''}`}
                    onClick={() => setSelectedProject(proj)}
                  >
                    <FolderOpen size={16} />
                    <span>{proj.name}</span>
                    {selectedProject?.id === proj.id && <Check size={16} className="text-primary" />}
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 16 }}>
                <label className="form-label">Або створити новий проект:</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Назва нового проекту..."
                  value={newProjectName}
                  onChange={e => setNewProjectName(e.target.value)}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
              <button className="btn btn-secondary" onClick={() => setShowSaveToProjectModal(false)}>
                Скасувати
              </button>
              <button
                className="btn btn-primary"
                onClick={handleSaveToProject}
                disabled={!selectedProject && !newProjectName.trim()}
              >
                Зберегти ({selectedModelsForProject.length || cartCount} моделей)
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: NEW PROJECT */}
      {showNewProjectModal && (
        <div className="modal-overlay" onClick={() => setShowNewProjectModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Новий проект</h2>
              <button className="btn-close" onClick={() => setShowNewProjectModal(false)}>
                <X size={20} />
              </button>
            </div>

            <div className="form-group">
              <label className="form-label">Назва проекту:</label>
              <input
                type="text"
                className="form-input"
                placeholder="Введіть назву..."
                value={newProjectName}
                onChange={e => setNewProjectName(e.target.value)}
                autoFocus
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
              <button className="btn btn-secondary" onClick={() => setShowNewProjectModal(false)}>
                Скасувати
              </button>
              <button className="btn btn-primary" onClick={handleCreateProject}>
                Створити
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
