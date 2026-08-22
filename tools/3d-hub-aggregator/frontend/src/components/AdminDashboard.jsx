import React from 'react'
import { BarChart3, Layers, RadioTower, FolderOpen, ShoppingCart, Clock, RefreshCw, ArrowLeft } from 'lucide-react'

export default function AdminDashboard({
  adminStats,
  fetchAdminStats,
  getStatusLabel,
  setActiveTab
}) {
  if (!adminStats) return null

  return (
    <main className="content-area" style={{ maxWidth: 1100, margin: '0 auto', width: '100%' }}>
      <button className="back-btn" onClick={() => setActiveTab('catalog')}>
        <ArrowLeft size={16} /><span>Назад</span>
      </button>
      <div className="sources-container">
        <div className="section-header">
          <div className="section-title">
            <BarChart3 className="text-primary" size={22} />
            <span>Статистика системи</span>
          </div>
          <button className="btn btn-secondary" onClick={fetchAdminStats}>
            <RefreshCw size={16} />
            <span>Оновити</span>
          </button>
        </div>

        <>
          <div className="stats-grid">
            <div className="stat-card">
              <Layers size={24} className="text-primary" />
              <div className="stat-value">{adminStats.total_models}</div>
              <div className="stat-label">Моделей</div>
            </div>
            <div className="stat-card">
              <RadioTower size={24} className="text-cyan" />
              <div className="stat-value">{adminStats.active_channels} / {adminStats.total_channels}</div>
              <div className="stat-label">Активних каналів</div>
            </div>
            <div className="stat-card">
              <FolderOpen size={24} className="text-emerald" />
              <div className="stat-value">{adminStats.total_projects}</div>
              <div className="stat-label">Проектів</div>
            </div>
            <div className="stat-card">
              <ShoppingCart size={24} className="text-amber" />
              <div className="stat-value">{adminStats.cart_count}</div>
              <div className="stat-label">У кошику</div>
            </div>
          </div>

          <div className="sources-section">
            <div className="section-title" style={{ marginBottom: 16 }}>
              <Clock size={18} />
              <span>Статус каналів</span>
            </div>

            <table className="channels-table">
              <thead>
                <tr>
                  <th>Канал</th>
                  <th>Статус</th>
                  <th>Режим</th>
                  <th>Прогрес</th>
                </tr>
              </thead>
              <tbody>
                {adminStats.channel_stats.map(ch => (
                  <tr key={ch.id}>
                    <td style={{ fontWeight: 600 }}>{ch.title}</td>
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
                    <td style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      {ch.scan_mode || 'idle'}
                    </td>
                    <td>
                      {ch.total_posts > 0 ? (
                        <div className="progress-bar">
                          <div
                            className="progress-fill"
                            style={{ width: `${Math.round((ch.processed_count / ch.total_posts) * 100)}%` }}
                          />
                          <span className="progress-text">
                            {ch.processed_count} / {ch.total_posts}
                          </span>
                        </div>
                      ) : (
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                          {ch.processed_count} моделей
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      </div>
    </main>
  )
}
