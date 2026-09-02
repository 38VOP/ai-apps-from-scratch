import React from 'react'

export default function About() {
  return (
    <main className="content-area">
      <div style={{
        position: 'absolute',
        bottom: 12,
        left: 0,
        right: 0,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        fontSize: '0.78rem',
        color: 'var(--text-muted)'
      }}>
        <span>{`3D Hub Aggregator · ${__COMMIT_HASH__} · ${new Date(__BUILD_DATE__).toLocaleString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}`}</span>
      </div>
    </main>
  )
}
