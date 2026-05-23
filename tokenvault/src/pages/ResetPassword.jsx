import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import StarField from '../components/StarField.jsx'
import Field from '../components/Field.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { authApi } from '../api'
import houstonLogo from '/houston-logo.png'

export default function ResetPassword() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const { showToast } = useToast()
  const [pw, setPw] = useState({ next: '', confirm: '' })
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState({})

  const onSubmit = async (e) => {
    e.preventDefault()
    const errs = {}
    if (!token) errs.token = 'Missing token'
    if (!pw.next || pw.next.length < 8) errs.next = 'Min 8 characters'
    if (pw.confirm !== pw.next) errs.confirm = 'Does not match'
    setErrors(errs)
    if (Object.keys(errs).length) return
    setSubmitting(true)
    try {
      await authApi.resetPassword({ token, newPassword: pw.next })
      showToast('Password reset — please sign in', 'success')
      navigate('/login', { replace: true })
    } catch (err) {
      showToast(err?.message || 'Reset failed', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-space-800 flex items-center justify-center px-5">
      <StarField />
      <motion.form
        onSubmit={onSubmit}
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-[390px] bg-space-700/70 backdrop-blur-xl rounded-3xl p-7 border border-space-500 shadow-card"
      >
        <div className="flex flex-col items-center gap-2 mb-7">
          <img src={houstonLogo} alt="Houston" className="h-12 w-auto" draggable="false" />
          <span className="text-sm text-gray-400 text-center">Set a new password</span>
        </div>

        <div className="space-y-4">
          <Field
            label="New Password"
            type="password"
            value={pw.next}
            onChange={(e) => setPw((p) => ({ ...p, next: e.target.value }))}
            error={errors.next}
          />
          <Field
            label="Confirm Password"
            type="password"
            value={pw.confirm}
            onChange={(e) => setPw((p) => ({ ...p, confirm: e.target.value }))}
            error={errors.confirm}
          />
        </div>

        <motion.button
          whileTap={{ scale: 0.96 }}
          disabled={submitting}
          type="submit"
          className="w-full mt-6 h-12 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 font-semibold shadow-teal-glow disabled:opacity-60 transition"
        >
          {submitting ? 'Saving…' : 'Reset password'}
        </motion.button>

        <p className="text-center text-sm text-gray-400 mt-5">
          <Link to="/login" className="text-teal-400 hover:text-teal-300 font-medium">
            Back to sign in
          </Link>
        </p>
      </motion.form>
    </div>
  )
}
