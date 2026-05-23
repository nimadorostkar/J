import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

// Map backend field names (camelCase from DRF serializers) to local form keys
function mapKey(k) {
  if (k === 'inviteCode') return 'invite'
  return k
}

import { motion } from 'framer-motion'
import StarField from '../components/StarField.jsx'
import Field from '../components/Field.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import houstonLogo from '/houston-logo.png'

export default function Register() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const { showToast } = useToast()
  const [form, setForm] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirm: '',
    invite: '',
  })
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  const onChange = (k) => (e) => {
    setForm((f) => ({ ...f, [k]: e.target.value }))
    setErrors((er) => ({ ...er, [k]: undefined }))
  }

  const validate = () => {
    const e = {}
    if (!form.firstName) e.firstName = 'Required'
    if (!form.lastName) e.lastName = 'Required'
    if (!form.email) e.email = 'Email is required'
    else if (!/^\S+@\S+\.\S+$/.test(form.email)) e.email = 'Enter a valid email'
    if (!form.password) e.password = 'Required'
    else if (form.password.length < 8) e.password = 'Min 8 characters'
    if (form.confirm !== form.password) e.confirm = 'Passwords do not match'
    if (!form.invite.trim()) e.invite = 'Invite code is required'
    else if (!/^[A-Za-z0-9]{8}$/.test(form.invite.trim())) e.invite = 'Code must be 8 alphanumeric chars'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSubmitting(true)
    try {
      await register({
        firstName: form.firstName,
        lastName: form.lastName,
        email: form.email,
        password: form.password,
        inviteCode: form.invite.trim().toUpperCase(),
      })
      showToast('Account created!', 'success')
      navigate('/home', { replace: true })
    } catch (err) {
      // Try to surface field-level errors from DRF
      const data = err?.data
      if (data && typeof data === 'object') {
        const fieldErrors = {}
        for (const [k, v] of Object.entries(data)) {
          if (Array.isArray(v)) fieldErrors[mapKey(k)] = String(v[0])
          else if (typeof v === 'string') fieldErrors[mapKey(k)] = v
          else if (v && typeof v === 'object' && v.message) fieldErrors[mapKey(k)] = v.message
        }
        if (Object.keys(fieldErrors).length) setErrors((er) => ({ ...er, ...fieldErrors }))
      }
      showToast(err?.message || 'Registration failed', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-space-800 flex items-center justify-center px-5 py-10">
      <StarField />
      <motion.form
        onSubmit={onSubmit}
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-[390px] bg-space-700/70 backdrop-blur-xl rounded-3xl p-7 border border-space-500 shadow-card"
      >
        <div className="flex flex-col items-center gap-2 mb-6">
          <img
            src={houstonLogo}
            alt="Houston"
            className="h-10 w-auto select-none drop-shadow-[0_0_18px_rgba(45,212,191,0.35)]"
            draggable="false"
          />
          <span className="text-sm text-gray-400">Create your account</span>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="First Name" value={form.firstName} onChange={onChange('firstName')} error={errors.firstName} placeholder="Alex" />
          <Field label="Last Name" value={form.lastName} onChange={onChange('lastName')} error={errors.lastName} placeholder="Morgan" />
        </div>

        <div className="space-y-3 mt-3">
          <Field label="Email" type="email" value={form.email} onChange={onChange('email')} error={errors.email} placeholder="you@example.com" />
          <Field label="Password" type="password" value={form.password} onChange={onChange('password')} error={errors.password} placeholder="••••••••" />
          <Field label="Confirm Password" type="password" value={form.confirm} onChange={onChange('confirm')} error={errors.confirm} placeholder="••••••••" />
          <Field label="Invite Code" value={form.invite} onChange={onChange('invite')} error={errors.invite} placeholder="FRIEND2024" />
        </div>

        <motion.button
          whileTap={{ scale: 0.96 }}
          disabled={submitting}
          type="submit"
          className="w-full mt-6 h-12 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 font-semibold shadow-teal-glow disabled:opacity-60 transition"
        >
          {submitting ? 'Creating…' : 'Create Account'}
        </motion.button>

        <p className="text-center text-sm text-gray-400 mt-5">
          Already have an account?{' '}
          <Link to="/login" className="text-teal-400 hover:text-teal-300 font-medium">
            Login
          </Link>
        </p>
      </motion.form>
    </div>
  )
}
