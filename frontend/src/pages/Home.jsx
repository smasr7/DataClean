import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Footer from './Footer'

const API = import.meta.env.VITE_API_URL || 'http://localhost:5000'

function BarList({ title, entries }) {
  const max = Math.max(...Object.values(entries), 1)
  return (
    <div className="card">
      <h3>{title}</h3>
      {Object.entries(entries).map(([label, value]) => (
        <div className="bar-row" key={label}>
          <span className="bar-label">{label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(value / max) * 100}%` }} />
          </div>
          <span className="bar-value">${Math.round(value).toLocaleString()}</span>
        </div>
      ))}
    </div>
  )
}

export default function Home() {
  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  const aboutRef = useRef(null)
  const uploadRef = useRef(null)
  const resultsRef = useRef(null)
  const downloadRef = useRef(null)

  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [result, setResult] = useState(null)
  const [downloadMsg, setDownloadMsg] = useState('')

  const scrollTo = (ref) => {
    ref.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleUploadClick = () => {
    if (!token) {
      navigate('/login')
      return
    }
    scrollTo(uploadRef)
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/')
  }

  const handleFileChange = (e) => {
    setFile(e.target.files[0])
  }

  const handleSubmit = async () => {
    if (!file) {
      setMessage('Please choose a file first')
      return
    }
    setLoading(true)
    setMessage('')

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${API}/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })

      if (response.status === 401 || response.status === 422) {
        localStorage.removeItem('token')
        navigate('/login')
        return
      }

      const data = await response.json()

      if (!response.ok) {
        setMessage(data.error || data.msg || `Error ${response.status}`)
        return
      }

      setResult(data)
      setTimeout(() => scrollTo(resultsRef), 100)
    } catch (err) {
      console.error(err)
      setMessage('Could not reach the server')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async () => {
    setDownloadMsg('')
    try {
      const response = await fetch(`${API}/download/${result.download_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })

      if (response.status === 401 || response.status === 422) {
        localStorage.removeItem('token')
        navigate('/login')
        return
      }
      if (!response.ok) {
        setDownloadMsg('Download failed. Please try again.')
        return
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = result.download_filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error(err)
      setDownloadMsg('Could not reach the server')
    }
  }

  const columns = result?.data?.length > 0 ? Object.keys(result.data[0]) : []

  return (
    <div>
      {/* NAVBAR */}
      <nav className="navbar">
        <div className="brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
          DataClean
        </div>
        <div className="nav-links">
          <button className="link-btn" onClick={() => scrollTo(aboutRef)}>About Us</button>
          <button className="link-btn" onClick={handleUploadClick}>Upload your work</button>
        </div>
        <div className="nav-auth">
          {token ? (
            <button className="btn-outline" onClick={handleLogout}>Log out</button>
          ) : (
            <>
              <button className="btn-outline" onClick={() => navigate('/login')}>Login</button>
              <button className="btn-solid" onClick={() => navigate('/signup')}>Sign up</button>
            </>
          )}
        </div>
      </nav>

      {/* HERO */}
      <section className="hero">
        <div className="hero-inner">
          <h1>Turn messy spreadsheets into clean, dashboard-ready data</h1>
          <p>Upload an Excel or CSV file. We clean it, flag what needs review, and build you a dashboard — with an AI summary on top.</p>
          <button className="btn-solid large" onClick={handleUploadClick}>Upload your work</button>
        </div>
      </section>

      {/* ABOUT */}
      <section className="section" ref={aboutRef}>
        <h2>About Us</h2>
        <p>
          DataClean extracts data from messy exports, standardizes inconsistent
          formatting, flags rows that need a second look, and turns the result
          into a dashboard — all in one upload.
        </p>
        <ul className="pitch-list">
          <li>Automatic duplicate removal</li>
          <li>Missing data flagged, never silently dropped</li>
          <li>Category &amp; region normalization</li>
          <li>Instant KPI dashboard with an AI-written summary</li>
        </ul>
      </section>

      {/* UPLOAD */}
      <section className="section upload-section" ref={uploadRef}>
        <h2>Upload your file</h2>
        {!token ? (
          <p>Please <a href="/login">log in</a> to upload a file.</p>
        ) : (
          <>
            <p>Accepts .xlsx and .csv files.</p>
            <input type="file" accept=".xlsx,.csv" onChange={handleFileChange} />
            <div className="upload-actions">
              <button className="btn-solid" onClick={handleSubmit} disabled={loading}>
                {loading ? 'Processing…' : 'Submit'}
              </button>
              {result && (
                <button className="btn-ghost" onClick={() => scrollTo(downloadRef)}>
                  Download ↓
                </button>
              )}
            </div>
            {loading && <p className="status">Extracting data… cleaning inconsistencies…</p>}
            <p>{message}</p>
          </>
        )}
      </section>

      {/* RESULTS + AI + DASHBOARD — only after a successful upload */}
      {result && (
        <div ref={resultsRef}>
          <section className="section">
            <h2>Cleaned Data</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
                </thead>
                <tbody>
                  {result.data.map((row, i) => (
                    <tr key={i} className={row.flag ? 'flagged-row' : ''}>
                      {columns.map((c) => <td key={c}>{String(row[c] ?? '')}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="section">
            <div className="ai-panel">
              <h2>AI Summary</h2>
              <p>{result.ai_summary}</p>
            </div>
          </section>

          <section className="section">
            <h2>Dashboard</h2>
            <div className="kpis">
              <div className="kpi">
                <div className="kpi-label">Records</div>
                <div className="kpi-value mono">{result.data.length}</div>
              </div>
              <div className="kpi">
                <div className="kpi-label">Flagged Rows</div>
                <div className="kpi-value mono">{result.data.filter(r => r.flag).length}</div>
              </div>
            </div>
            <div className="grid">
              {result.summary?.by_category && (
                <BarList title="Revenue by Category" entries={result.summary.by_category} />
              )}
              {result.summary?.by_region && (
                <BarList title="Revenue by Region" entries={result.summary.by_region} />
              )}
            </div>
          </section>

          <section className="section" ref={downloadRef}>
            <h2>Download cleaned file</h2>
            <p>Duplicates removed, text normalized, and flagged rows marked in a "flag" column.</p>
            <button className="btn-solid" onClick={handleDownload}>
              Download {result.download_filename}
            </button>
            {downloadMsg && <p className="status">{downloadMsg}</p>}
          </section>
        </div>
      )}
      <Footer />
    </div>
  )
}