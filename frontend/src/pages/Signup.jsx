import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL || 'http://localhost:5000'

export default function Signup() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const navigate = useNavigate()

  const handleSignup = async () => {
    try {
      const response = await fetch(`${API}/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      const data = await response.json()
      if (data.error) {
        setMessage(data.error)
      } else {
        setMessage(data.message)
        navigate('/login')
      }
    } catch (err) {
      setMessage('Could not reach the server')
    }
  }

  return (
    <div className="auth-page">
      <h1>Sign up</h1>
      <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <button className="btn-solid" onClick={handleSignup}>Sign up</button>
      <p>{message}</p>
      <p>Already have an account? <a href="/login">Log in</a></p>
    </div>
  )
}
