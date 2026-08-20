import React, { useState, useEffect } from 'react'
import { 
  Box, Search, RefreshCw, ExternalLink, Plus, Settings, 
  Trash2, Edit2, Eye, EyeOff, ArrowUp, ArrowDown, Radio, CheckCircle, 
  AlertCircle, ShieldCheck, Layers, RadioTower, Check, X, ShoppingCart,
  FolderOpen, BarChart3, Clock, Zap
} from 'lucide-react'

import Catalog from './components/Catalog'
import Cart from './components/Cart'
import Projects from './components/Projects'
import CategoryManager from './components/CategoryManager'
import SourcesPanel from './components/SourcesPanel'
import AdminDashboard from './components/AdminDashboard'

export default function App() {
  const [activeTab, setActiveTab] = useState('catalog')
  
  // Catalog State
  const [models, setModels] = useState([])
  const [categories, setCategories] = useState([])
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [totalModels, setTotalModels] = useState(0)
  const [loadingModels, setLoadingModels] = useState(false)
  const [selectedModel, setSelectedModel] = useState(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  // Sources State
  const [accounts, setAccounts] = useState([])
  const [channels, setChannels] = useState([])
  const [syncingChannelId, setSyncingChannelId] = useState(null)
  const [globalSyncMsg, setGlobalSyncMsg] = useState('')

  // Cart State
  const [cartItems, setCartItems] = useState([])
  const [cartCount, setCartCount] = useState(0)

  // Projects State
  const [projects, setProjects] = useState([])
  const [selectedProject, setSelectedProject] = useState(null)
  const [projectModels, setProjectModels] = useState([])

  // Admin State
  const [adminStats, setAdminStats] = useState(null)

  // Modals
  const [showCatManagerModal, setShowCatManagerModal] = useState(false)
  const [showAddAccountModal, setShowAddAccountModal] = useState(false)
  const [showAddChannelModal, setShowAddChannelModal] = useState(false)
  const [showCartModal, setShowCartModal] = useState(false)
  const [showSaveToProjectModal, setShowSaveToProjectModal] = useState(false)
  const [showNewProjectModal, setShowNewProjectModal] = useState(false)

  // Forms State
  const [newCatName, setNewCatName] = useState('')
  const [catStatuses, setCatStatuses] = useState({})

  // Account Form
  const [accForm, setAccForm] = useState({ name: 'Основний акаунт', api_id: '', api_hash: '', phone_number: '' })
  const [accStep, setAccStep] = useState('config')
  const [accCreatedId, setAccCreatedId] = useState(null)
  const [accCode, setAccCode] = useState('')
  const [accMsg, setAccMsg] = useState('')

  // Channel Form
  const [chForm, setChForm] = useState({ telegram_id: '', title: '', account_id: '' })

  // Project Form
  const [newProjectName, setNewProjectName] = useState('')
  const [selectedModelsForProject, setSelectedModelsForProject] = useState([])

  // Collapsible sidebar sections
  const [catsExpanded, setCatsExpanded] = useState(true)
  const [projectsExpanded, setProjectsExpanded] = useState(true)

  useEffect(() => {
    fetchUserCategories()
    fetchAccounts()
    fetchChannels()
    fetchCart()
    fetchProjects()
  }, [])

  useEffect(() => {
    if (activeTab === 'catalog') {
      fetchModels()
    } else if (activeTab === 'admin') {
      fetchAdminStats()
    }
  }, [activeTab, selectedCategory, searchQuery, currentPage])

  // --- API CALLS ---

  const fetchModels = async () => {
    setLoadingModels(true)
    try {
      const params = new URLSearchParams()
      if (searchQuery) params.append('search', searchQuery)
      if (selectedCategory) params.append('category_id', selectedCategory)
      params.append('page', currentPage)
      params.append('limit', '24')

      const res = await fetch(`/api/models?${params.toString()}`)
      const data = await res.json()
      setModels(data.items || [])
      setTotalModels(data.total || 0)
      setTotalPages(data.pages || 1)
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
      const statuses = {}
      data.forEach(c => { 
        statuses[c.id] = { 
          active: c.is_active !== false, 
          visible: c.is_visible !== false,
          markedForDeletion: c.is_marked_for_deletion || false
        } 
      })
      setCatStatuses(statuses)
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

  const fetchCart = async () => {
    try {
      const res = await fetch('/api/cart')
      const data = await res.json()
      setCartItems(data.items || [])
      setCartCount(data.count || 0)
    } catch (err) {
      console.error('Error fetching cart:', err)
    }
  }

  const fetchProjects = async () => {
    try {
      const res = await fetch('/api/projects')
      const data = await res.json()
      setProjects(data)
    } catch (err) {
      console.error('Error fetching projects:', err)
    }
  }

  const fetchProjectDetail = async (projectId) => {
    try {
      const res = await fetch(`/api/projects/${projectId}`)
      const data = await res.json()
      setProjectModels(data.models || [])
      setSelectedProject(data)
    } catch (err) {
      console.error('Error fetching project:', err)
    }
  }

  const fetchAdminStats = async () => {
    try {
      const res = await fetch('/api/admin/stats')
      const data = await res.json()
      setAdminStats(data)
    } catch (err) {
      console.error('Error fetching admin stats:', err)
    }
  }

  // --- HANDLERS ---

  const handleAddToCart = async (modelId) => {
    try {
      const res = await fetch('/api/cart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId })
      })
      const data = await res.json()
      if (data.success) {
        fetchCart()
        setGlobalSyncMsg(data.message)
        setTimeout(() => setGlobalSyncMsg(''), 2000)
      }
    } catch (err) {
      console.error('Error adding to cart:', err)
    }
  }

  const handleRemoveFromCart = async (cartItemId) => {
    try {
      await fetch(`/api/cart/${cartItemId}`, { method: 'DELETE' })
      fetchCart()
    } catch (err) {
      console.error('Error removing from cart:', err)
    }
  }

  const handleClearCart = async () => {
    if (!window.confirm('Очистити кошик?')) return
    try {
      await fetch('/api/cart', { method: 'DELETE' })
      fetchCart()
    } catch (err) {
      console.error('Error clearing cart:', err)
    }
  }

  const handleSaveToProject = async () => {
    if (selectedModelsForProject.length === 0) return
    try {
      const res = await fetch('/api/cart/save-to-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: selectedProject?.id || null,
          project_name: newProjectName || null,
          model_ids: selectedModelsForProject
        })
      })
      const data = await res.json()
      if (data.success) {
        fetchCart()
        fetchProjects()
        setShowSaveToProjectModal(false)
        setSelectedModelsForProject([])
        setNewProjectName('')
        setGlobalSyncMsg(data.message)
        setTimeout(() => setGlobalSyncMsg(''), 3000)
      }
    } catch (err) {
      console.error('Error saving to project:', err)
    }
  }

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return
    try {
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newProjectName })
      })
      const data = await res.json()
      if (data.id) {
        fetchProjects()
        setShowNewProjectModal(false)
        setNewProjectName('')
      }
    } catch (err) {
      console.error('Error creating project:', err)
    }
  }

  const handleDeleteProject = async (projectId) => {
    if (!window.confirm('Видалити цей проект?')) return
    try {
      await fetch(`/api/projects/${projectId}`, { method: 'DELETE' })
      fetchProjects()
      setSelectedProject(null)
      setProjectModels([])
    } catch (err) {
      console.error('Error deleting project:', err)
    }
  }

  const handleRemoveFromProject = async (projectId, modelId) => {
    try {
      await fetch(`/api/projects/${projectId}/models/${modelId}`, { method: 'DELETE' })
      fetchProjectDetail(projectId)
    } catch (err) {
      console.error('Error removing from project:', err)
    }
  }

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

  const handleToggleCategoryStatus = async (catId) => {
    const current = catStatuses[catId] || { active: true, visible: true, markedForDeletion: false }
    
    let nextActive, nextMarkedForDeletion
    if (current.active && !current.markedForDeletion) {
      nextActive = false
      nextMarkedForDeletion = false
    } else if (!current.active && !current.markedForDeletion) {
      nextActive = false
      nextMarkedForDeletion = true
    } else {
      nextActive = true
      nextMarkedForDeletion = false
    }
    
    try {
      await fetch(`/api/categories/${catId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: nextActive, is_marked_for_deletion: nextMarkedForDeletion })
      })
      setCatStatuses(prev => ({
        ...prev,
        [catId]: { ...prev[catId], active: nextActive, markedForDeletion: nextMarkedForDeletion }
      }))
    } catch (err) {
      console.error('Error updating category status:', err)
    }
  }

  const handleApplyCategoryChanges = async () => {
    try {
      const res = await fetch('/api/categories/apply', { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        fetchUserCategories(true)
        setGlobalSyncMsg(data.message)
      } else {
        setGlobalSyncMsg(data.message)
        if (data.blocked_categories) {
          console.log('Blocked:', data.blocked_categories)
        }
      }
      setTimeout(() => setGlobalSyncMsg(''), 4000)
    } catch (err) {
      console.error('Error applying changes:', err)
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

  const handleDeleteModel = async (modelId) => {
    if (!window.confirm('Видалити цю модель?')) return
    try {
      await fetch(`/api/models/${modelId}`, { method: 'DELETE' })
      fetchModels()
      setSelectedModel(null)
    } catch (err) {
      console.error('Error deleting model:', err)
    }
  }

  const handleRefreshPreview = async (modelId) => {
    try {
      const res = await fetch(`/api/models/${modelId}/refresh-preview`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        setSelectedModel(prev => prev ? { ...prev, preview_path: data.preview_path } : null)
        fetchModels()
        setGlobalSyncMsg('Прев\'ю оновлено')
        setTimeout(() => setGlobalSyncMsg(''), 2000)
      } else {
        setGlobalSyncMsg(data.message)
        setTimeout(() => setGlobalSyncMsg(''), 3000)
      }
    } catch (err) {
      console.error('Error refreshing preview:', err)
    }
  }

  const getStatusLabel = (status) => {
    switch (status) {
      case 'queued': return '🟡 У черзі'
      case 'backlog': return '🔵 Backlog'
      case 'monitoring': return '🟢 Monitoring'
      case 'up_to_date': return '🟢 Актуальний'
      case 'error': return '🔴 Помилка'
      case 'disabled': return '⚪ Вимкнено'
      default: return '⚪ Idle'
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
            onClick={() => { setActiveTab('catalog'); setCurrentPage(1); fetchUserCategories(); }}
          >
            <Box size={18} />
            <span>Каталог</span>
          </button>
          <button 
            className={`tab-btn ${activeTab === 'sources' ? 'active' : ''}`}
            onClick={() => { setActiveTab('sources'); fetchAccounts(); fetchChannels(); }}
          >
            <RadioTower size={18} />
            <span>Джерела</span>
          </button>
          <button 
            className={`tab-btn ${activeTab === 'admin' ? 'active' : ''}`}
            onClick={() => { setActiveTab('admin'); fetchAdminStats(); }}
          >
            <BarChart3 size={18} />
            <span>Статистика</span>
          </button>
        </div>

        {/* CART & SEARCH */}
        <div className="header-right">
          <button 
            className="cart-btn"
            onClick={() => setShowCartModal(true)}
          >
            <ShoppingCart size={20} />
            {cartCount > 0 && <span className="cart-badge">{cartCount}</span>}
          </button>
        </div>
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

      {/* COMPONENTS */}
      <Catalog
        activeTab={activeTab}
        models={models}
        categories={categories}
        selectedCategory={selectedCategory}
        searchQuery={searchQuery}
        totalModels={totalModels}
        loadingModels={loadingModels}
        selectedModel={selectedModel}
        currentPage={currentPage}
        totalPages={totalPages}
        catsExpanded={catsExpanded}
        setCatsExpanded={setCatsExpanded}
        setShowCatManagerModal={setShowCatManagerModal}
        fetchUserCategories={fetchUserCategories}
        setSelectedCategory={setSelectedCategory}
        setSearchQuery={setSearchQuery}
        setCurrentPage={setCurrentPage}
        setSelectedModel={setSelectedModel}
        handleAddToCart={handleAddToCart}
        handleUpdateModelCategory={handleUpdateModelCategory}
        handleDeleteModel={handleDeleteModel}
        handleRefreshPreview={handleRefreshPreview}
      />

      <Projects
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        projects={projects}
        selectedProject={selectedProject}
        setSelectedProject={setSelectedProject}
        projectModels={projectModels}
        fetchProjects={fetchProjects}
        fetchProjectDetail={fetchProjectDetail}
        handleCreateProject={handleCreateProject}
        handleDeleteProject={handleDeleteProject}
        handleRemoveFromProject={handleRemoveFromProject}
        setShowNewProjectModal={setShowNewProjectModal}
        newProjectName={newProjectName}
        setNewProjectName={setNewProjectName}
      />

      <SourcesPanel
        activeTab={activeTab}
        accounts={accounts}
        channels={channels}
        syncingChannelId={syncingChannelId}
        showAddAccountModal={showAddAccountModal}
        setShowAddAccountModal={setShowAddAccountModal}
        showAddChannelModal={showAddChannelModal}
        setShowAddChannelModal={setShowAddChannelModal}
        accForm={accForm}
        setAccForm={setAccForm}
        accStep={accStep}
        setAccStep={setAccStep}
        accCode={accCode}
        setAccCode={setAccCode}
        accMsg={accMsg}
        setAccMsg={setAccMsg}
        chForm={chForm}
        setChForm={setChForm}
        handleAddAccountSubmit={handleAddAccountSubmit}
        handleVerifyAccCode={handleVerifyAccCode}
        handleRequestAccCode={handleRequestAccCode}
        handleDeleteAccount={handleDeleteAccount}
        handleAddChannelSubmit={handleAddChannelSubmit}
        handleToggleChannelEnabled={handleToggleChannelEnabled}
        handleChangeChannelAccount={handleChangeChannelAccount}
        handleDeleteChannel={handleDeleteChannel}
        handleSyncChannel={handleSyncChannel}
        getStatusLabel={getStatusLabel}
      />

      {activeTab === 'admin' && (
        <AdminDashboard
          adminStats={adminStats}
          fetchAdminStats={fetchAdminStats}
          getStatusLabel={getStatusLabel}
        />
      )}

      {/* MODALS */}
      <Cart
        activeTab={activeTab}
        cartItems={cartItems}
        cartCount={cartCount}
        projects={projects}
        showCartModal={showCartModal}
        setShowCartModal={setShowCartModal}
        showSaveToProjectModal={showSaveToProjectModal}
        setShowSaveToProjectModal={setShowSaveToProjectModal}
        showNewProjectModal={showNewProjectModal}
        setShowNewProjectModal={setShowNewProjectModal}
        selectedProject={selectedProject}
        setSelectedProject={setSelectedProject}
        newProjectName={newProjectName}
        setNewProjectName={setNewProjectName}
        selectedModelsForProject={selectedModelsForProject}
        setSelectedModelsForProject={setSelectedModelsForProject}
        handleRemoveFromCart={handleRemoveFromCart}
        handleClearCart={handleClearCart}
        handleSaveToProject={handleSaveToProject}
        handleCreateProject={handleCreateProject}
        fetchProjects={fetchProjects}
      />

      <CategoryManager
        showCatManagerModal={showCatManagerModal}
        setShowCatManagerModal={setShowCatManagerModal}
        categories={categories}
        newCatName={newCatName}
        setNewCatName={setNewCatName}
        catStatuses={catStatuses}
        handleCreateNewCategory={handleCreateNewCategory}
        handleToggleCategoryStatus={handleToggleCategoryStatus}
        handleMoveCategoryOrder={handleMoveCategoryOrder}
        handleDeleteCategory={handleDeleteCategory}
        handleApplyCategoryChanges={handleApplyCategoryChanges}
        fetchUserCategories={fetchUserCategories}
      />


    </div>
  )
}
