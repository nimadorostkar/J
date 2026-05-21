import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Coins } from 'lucide-react'
import StarField from '../components/StarField.jsx'
import Field from '../components/Field.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useToast } from '../context/ToastContext.jsx'

export default function Register() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const { showToast } = useToast()
  const [form, setForm] = useState({
    firstName: '',
    lastName: '',
    countryCode: '+1',
    mobile: '',
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
    if (!form.mobile) e.mobile = 'Mobile is required'
    else if (!/^[0-9 ]{6,15}$/.test(form.mobile)) e.mobile = 'Enter digits only'
    if (!form.email) e.email = 'Email is required'
    else if (!/^\S+@\S+\.\S+$/.test(form.email)) e.email = 'Enter a valid email'
    if (!form.password) e.password = 'Required'
    else if (form.password.length < 6) e.password = 'Min 6 characters'
    if (form.confirm !== form.password) e.confirm = 'Passwords do not match'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const onSubmit = (e) => {
    e.preventDefault()
    if (!validate()) return
    setSubmitting(true)
    try {
      register({
        firstName: form.firstName,
        lastName: form.lastName,
        email: form.email,
        mobile: `${form.countryCode} ${form.mobile}`,
      })
      showToast('Account created!', 'success')
      navigate('/home', { replace: true })
    } catch (err) {
      showToast(err.message || 'Registration failed', 'error')
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
          <div className="flex items-center gap-2">
            <Coins className="text-teal-400" size={24} />
            <span className="text-xl font-bold tracking-wide">TokenVault</span>
          </div>
          <span className="text-sm text-gray-400">Create your account</span>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="First Name" value={form.firstName} onChange={onChange('firstName')} error={errors.firstName} placeholder="Alex" />
          <Field label="Last Name" value={form.lastName} onChange={onChange('lastName')} error={errors.lastName} placeholder="Morgan" />
        </div>

        <div className="mt-3 grid grid-cols-[80px_1fr] gap-3">
          <Field label="Code" value={form.countryCode} onChange={onChange('countryCode')} placeholder="+1" />
          <Field label="Mobile" inputMode="numeric" value={form.mobile} onChange={onChange('mobile')} error={errors.mobile} placeholder="555 0100" />
        </div>

        <div className="space-y-3 mt-3">
          <Field label="Email" type="email" value={form.email} onChange={onChange('email')} error={errors.email} placeholder="you@example.com" />
          <Field label="Password" type="password" value={form.password} onChange={onChange('password')} error={errors.password} placeholder="••••••••" />
          <Field label="Confirm Password" type="password" value={form.confirm} onChange={onChange('confirm')} error={errors.confirm} placeholder="••••••••" />
          <Field label="Invite Code (optional)" value={form.invite} onChange={onChange('invite')} placeholder="FRIEND2024" />
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
