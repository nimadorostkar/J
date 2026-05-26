import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import StarField from '../components/StarField.jsx'
import Field from '../components/Field.jsx'
import LanguagePicker from '../components/LanguagePicker.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../i18n/LanguageContext.jsx'
import { authApi } from '../api'
import houstonLogo from '/houston-logo.png'

export default function ForgotPassword() {
  const { showToast } = useToast()
  const t = useT()
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [sent, setSent] = useState(false)

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!/^\S+@\S+\.\S+$/.test(email)) {
      showToast(t('auth.emailInvalid'), 'error')
      return
    }
    setSubmitting(true)
    try {
      await authApi.forgotPassword(email)
      setSent(true)
      showToast(t('auth.resetEmailSent'), 'success')
    } catch (err) {
      showToast(err?.message || t('auth.resetFailed'), 'error')
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
          <img src={houstonLogo} alt="Houston" className="h-12 w-auto" draggable="false" />
          <span className="text-sm text-gray-400 text-center">{t('auth.resetTitle')}</span>
        </div>

        {sent ? (
          <p className="text-sm text-gray-300 text-center">
            {t('auth.resetSentDesc')}
          </p>
        ) : (
          <>
            <Field
              label={t('auth.email')}
              type="email"
              placeholder={t('auth.emailPlaceholder')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <motion.button
              whileTap={{ scale: 0.96 }}
              disabled={submitting}
              type="submit"
              className="w-full mt-6 h-12 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 font-semibold shadow-teal-glow disabled:opacity-60 transition"
            >
              {submitting ? t('auth.sending') : t('auth.sendReset')}
            </motion.button>
          </>
        )}

        <p className="text-center text-sm text-gray-400 mt-5">
          <Link to="/login" className="text-teal-400 hover:text-teal-300 font-medium">
            {t('auth.backToSignIn')}
          </Link>
        </p>
      </motion.form>
    </div>
  )
}
