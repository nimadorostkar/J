import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import StarField from '../components/StarField.jsx'
import Field from '../components/Field.jsx'
import LanguagePicker from '../components/LanguagePicker.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../i18n/LanguageContext.jsx'
import houstonLogo from '/houston-logo.png'

export default function Login() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const { showToast } = useToast()
  const t = useT()
  const [form, setForm] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  const onChange = (k) => (e) => {
    setForm((f) => ({ ...f, [k]: e.target.value }))
    setErrors((e) => ({ ...e, [k]: undefined }))
  }

  const validate = () => {
    const e = {}
    if (!form.email) e.email = t('auth.emailRequired')
    else if (!/^\S+@\S+\.\S+$/.test(form.email)) e.email = t('auth.emailInvalid')
    if (!form.password) e.password = t('auth.passwordRequired')
    else if (form.password.length < 6) e.password = t('auth.pwMin6')
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSubmitting(true)
    try {
      await login(form)
      showToast(t('auth.welcomeBack'), 'success')
      navigate('/home', { replace: true })
    } catch (err) {
      showToast(err?.message || t('auth.signInFailed'), 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-space-800 flex items-center justify-center px-5">
      <StarField />
      <LanguagePicker />
      <motion.form
        onSubmit={onSubmit}
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-[390px] bg-space-700/70 backdrop-blur-xl rounded-3xl p-7 border border-space-500 shadow-card"
      >
        <div className="flex flex-col items-center gap-2 mb-7">
          <img
            src={houstonLogo}
            alt="Houston"
            className="h-12 w-auto select-none drop-shadow-[0_0_18px_rgba(45,212,191,0.35)]"
            draggable="false"
          />
          <span className="text-sm text-gray-400 text-center">
            {t('auth.gateway')}
          </span>
        </div>

        <div className="space-y-4">
          <Field
            label={t('auth.email')}
            type="email"
            autoComplete="email"
            placeholder={t('auth.emailPlaceholder')}
            value={form.email}
            onChange={onChange('email')}
            error={errors.email}
          />
          <Field
            label={t('auth.password')}
            type="password"
            autoComplete="current-password"
            placeholder={t('auth.passwordPlaceholder')}
            value={form.password}
            onChange={onChange('password')}
            error={errors.password}
          />
        </div>

        <motion.button
          whileTap={{ scale: 0.96 }}
          disabled={submitting}
          type="submit"
          className="w-full mt-6 h-12 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 font-semibold shadow-teal-glow disabled:opacity-60 transition"
        >
          {submitting ? t('auth.signingIn') : t('auth.signIn')}
        </motion.button>

        <p className="text-center text-sm text-gray-400 mt-3">
          <Link to="/forgot-password" className="text-teal-400 hover:text-teal-300 font-medium">
            {t('auth.forgotPassword')}
          </Link>
        </p>
        <p className="text-center text-sm text-gray-400 mt-2">
          {t('auth.noAccount')}{' '}
          <Link to="/register" className="text-teal-400 hover:text-teal-300 font-medium">
            {t('auth.register')}
          </Link>
        </p>
      </motion.form>
    </div>
  )
}
