import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import StarField from '../components/StarField.jsx'
import { useT } from '../i18n/LanguageContext.jsx'
import { authApi } from '../api'
import houstonLogo from '/houston-logo.png'

export default function VerifyEmail() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const t = useT()
  const [state, setState] = useState({ status: 'loading', message: '' })

  useEffect(() => {
    if (!token) {
      setState({ status: 'error', message: t('auth.missingVerifyToken') })
      return
    }
    let cancelled = false
    authApi
      .verifyEmail(token)
      .then(() => {
        if (!cancelled) setState({ status: 'ok', message: t('auth.verified') })
      })
      .catch((err) => {
        if (!cancelled) setState({ status: 'error', message: err?.message || t('auth.cannotVerify') })
      })
    return () => { cancelled = true }
  }, [token, t])

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-space-800 flex items-center justify-center px-5">
      <StarField />
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-[390px] bg-space-700/70 backdrop-blur-xl rounded-3xl p-7 border border-space-500 shadow-card text-center"
      >
        <img src={houstonLogo} alt="Houston" className="h-12 w-auto mx-auto" draggable="false" />
        <h1 className="mt-4 text-lg font-semibold text-white">
          {state.status === 'loading' && t('auth.verifying')}
          {state.status === 'ok' && t('auth.verified')}
          {state.status === 'error' && t('auth.cannotVerify')}
        </h1>
        {state.status !== 'loading' && (
          <p className="text-sm text-gray-400 mt-2">{state.message}</p>
        )}
        <Link
          to="/login"
          className="inline-block mt-5 h-11 px-5 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 font-semibold shadow-teal-glow leading-[44px]"
        >
          {t('auth.continueSignIn')}
        </Link>
      </motion.div>
    </div>
  )
}
