import React, { useState } from 'react'
import { FolderOpen, Plus, Trash2, Edit2, Check, X, Layers, ExternalLink, ArrowLeft } from 'lucide-react'

export default function Projects({
  activeTab,
  setActiveTab,
  projects = [],
  selectedProject,
  setSelectedProject,
  projectModels = [],
  fetchProjects,
  fetchProjectDetail,
  handleCreateProject,
  handleDeleteProject,
  handleRemoveFromProject,
  setShowNewProjectModal,
  newProjectName,
  setNewProjectName
}) {
  const [editingProjectId, setEditingProjectId] = useState(null)
  const [editingProjectName, setEditingProjectName] = useState('')

  if (activeTab !== 'projects') return null

  const handleStartRename = (proj) => {
    setEditingProjectId(proj.id)
    setEditingProjectName(proj.name)
  }

  const handleSaveRename = async (projectId) => {
    if (!editingProjectName.trim()) return
    try {
      const res = await fetch(`/api/projects/${projectId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editingProjectName.trim() })
      })
      const data = await res.json()
      if (data.success) {
        setEditingProjectId(null)
        fetchProjects()
        if (selectedProject?.id === projectId) {
          setSelectedProject(prev => prev ? { ...prev, name: editingProjectName.trim() } : null)
        }
      }
    } catch (err) {
      console.error('Error renaming project:', err)
    }
  }

  return (
    <main className="content-area" style={{ maxWidth: 1100, margin: '0 auto', width: '100%' }}>
      <button className="back-btn" onClick={() => setActiveTab('catalog')} title="Назад до каталогу">
        <ArrowLeft size={16} />
      </button>
      <div className="sources-container">
        {!selectedProject && (
        <div className="sources-section">
          <div className="section-header">
            <div className="section-title">
              <FolderOpen className="text-primary" size={22} />
              <span>Мої проекти</span>
            </div>
            <button className="btn btn-primary" onClick={() => setShowNewProjectModal && setShowNewProjectModal(true)}>
              <Plus size={16} />
              <span>Новий проект</span>
            </button>
          </div>

          {projects.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Немає проектів. Створіть перший проект.</p>
          ) : (
            <div className="projects-grid">
              {projects.map(proj => {
                const isSelected = selectedProject?.id === proj.id
                const isEditing = editingProjectId === proj.id

                return (
                  <div
                    key={proj.id}
                    className={`project-card ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      if (!isEditing) fetchProjectDetail(proj.id)
                    }}
                  >
                    <div className="project-header">
                      {isEditing ? (
                        <input
                          className="form-input"
                          value={editingProjectName}
                          onChange={e => setEditingProjectName(e.target.value)}
                          onBlur={() => handleSaveRename(proj.id)}
                          onKeyDown={e => e.key === 'Enter' && handleSaveRename(proj.id)}
                          autoFocus
                          onClick={e => e.stopPropagation()}
                        />
                      ) : (
                        <span className="project-name">{proj.name}</span>
                      )}
                      <div style={{ display: 'flex', gap: 6 }}>
                        {!isEditing && (
                          <>
                            <button
                              className="btn-close"
                              onClick={(e) => { e.stopPropagation(); handleStartRename(proj); }}
                            >
                              <Edit2 size={14} />
                            </button>
                            <button
                              className="btn btn-danger btn-sm"
                              onClick={(e) => { e.stopPropagation(); handleDeleteProject(proj.id); }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="project-meta">
                      <span>{proj.item_count} моделей</span>
                      <span>{new Date(proj.created_at).toLocaleDateString('uk-UA')}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
        )}

        {selectedProject && (
          <div className="sources-section">
            <div className="section-header">
              <div className="section-title">
                <Layers className="text-cyan" size={22} />
                <span>{selectedProject.name}</span>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => { setSelectedProject(null); }}>
                <X size={14} /><span>Усі проекти</span>
              </button>
            </div>

            {projectModels.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Проект порожній. Додайте моделі з кошика.</p>
            ) : (
              <div className="models-grid">
                {projectModels.map(model => (
                  <div key={model.id} className="model-card">
                    <div className="card-media">
                      <img
                        src={model.preview_path || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&q=80'}
                        alt={model.title}
                        className="card-img"
                      />
                    </div>
                    <div className="card-body">
                      <h3 className="card-title">{model.title}</h3>
                      <div className="card-footer">
                        <a
                          href={model.telegram_post_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn-tg-link"
                        >
                          Завантажити ↗
                        </a>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleRemoveFromProject(selectedProject.id, model.id)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  )
}
