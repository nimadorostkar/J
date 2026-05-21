import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Check, ChevronDown, Copy, LogOut, ShieldCheck, UserPlus } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import Field from '../components/Field.jsx'
import MobileField from '../components/MobileField.jsx'
import { COUNTRIES, COUNTRY_CODES } from '../data/network.js'

function splitMobile(stored) {
  if (!stored) return { code: '+1', number: '' }
  const match = stored.match(/^\s*(\+\d{1,4})\s*(.*)$/)
  if (match) {
    const code = COUNTRY_CODES.find((c) => c.code === match[1])?.code || match[1]
    return { code, number: match[2].trim() }
  }
  return { code: '+1', number: stored.trim() }
}

function initials(first, last) {
  return `${first?.[0] || ''}${last?.[0] || ''}`.toUpperCase() || 'U'
}

export default function Profile() {
  const { user, updateUser, logout } = useAuth()
  const { showToast } = useToast()

  const initialMobile = splitMobile(user?.mobile)
  const [form, setForm] = useState({
    firstName: user?.firstName || '',
    lastName: user?.lastName || '',
    countryCode: initialMobile.code,
    mobile: initialMobile.number,
    email: user?.email || '',
    country: user?.country || 'United States',
  })
  const [saved, setSaved] = useState(false)
  const [pwOpen, setPwOpen] = useState(false)
  const [pw, setPw] = useState({ current: '', next: '', confirm: '' })
  const [pwErrors, setPwErrors] = useState({})

  const onChange = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const onSave = (e) => {
    e.preventDefault()
    const { countryCode, mobile, ...rest } = form
    updateUser({ ...rest, mobile: `${countryCode} ${mobile}`.trim() })
    setSaved(true)
    showToast('Profile saved', 'success')
    setTimeout(() => setSaved(false), 2200)
  }

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(user?.referralCode || 'TOKEN2024')
      showToast('Copied!', 'success')
    } catch {
      showToast('Copy failed', 'error')
    }
  }

  const onUpdatePassword = (e) => {
    e.preventDefault()
    const errs = {}
    if (!pw.current) errs.current = 'Required'
    if (!pw.next || pw.next.length < 6) errs.next = 'Min 6 characters'
    if (pw.confirm !== pw.next) errs.confirm = 'Does not match'
    setPwErrors(errs)
    if (Object.keys(errs).length) return
    setPw({ current: '', next: '', confirm: '' })
    showToast('Password updated', 'success')
    setPwOpen(false)
  }

  return (
    <div className="relative w-full max-w-[480px] mx-auto px-5 pt-6 pb-28 bg-space-900 min-h-[100dvh]">
      {/* Avatar section */}
      <div className="flex flex-col items-center gap-2 mt-2">
        <div className="h-20 w-20 rounded-full border-2 border-teal-400 bg-gradient-to-br from-teal-500/30 to-space-700 grid place-items-center text-white text-xl font-bold shadow-teal-glow">
          {initials(form.firstName, form.lastName)}
        </div>
        <button type="button" className="text-xs text-teal-300 hover:text-teal-200">
          Edit Photo
        </button>
        <div className="font-semibold text-white text-base">
          {form.firstName} {form.lastName}
        </div>
      </div>

      {/* Status chips */}
      <div className="mt-5 flex gap-2 justify-center">
        <StatusChip active={user?.hasDeposit} label="Initial Deposit" />
        <StatusChip active={user?.hasReferral} label="1+ Referral" icon={<UserPlus size={12} />} />
      </div>

      {/* Editable form */}
      <form onSubmit={onSave} className="mt-6 bg-space-700 border border-space-500 rounded-2xl p-5 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="First Name" value={form.firstName} onChange={onChange('firstName')} />
          <Field label="Last Name" value={form.lastName} onChange={onChange('lastName')} />
        </div>
        <MobileField
          label="Mobile"
          code={form.countryCode}
          number={form.mobile}
          onCodeChange={(code) => setForm((f) => ({ ...f, countryCode: code }))}
          onNumberChange={(n) => setForm((f) => ({ ...f, mobile: n }))}
        />
        <Field label="Email" type="email" value={form.email} onChange={onChange('email')} />

        <label className="block">
          <span className="block text-xs font-medium text-gray-400 mb-1.5 tracking-wide">Country</span>
          <div className="relative">
            <select
              value={form.country}
              onChange={onChange('country')}
              className="w-full appearance-none bg-space-600 border border-space-500 rounded-xl px-3.5 min-h-[48px] text-white text-[15px] outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-400/30 transition"
            >
              {COUNTRIES.map((c) => (
                <option key={c} value={c} className="bg-space-700">{c}</option>
              ))}
            </select>
            <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
          </div>
        </label>

        <motion.button
          whileTap={{ scale: 0.97 }}
          type="submit"
          className="w-full h-12 mt-2 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 font-semibold shadow-teal-glow transition relative overflow-hidden"
        >
          <AnimatePresence mode="wait">
            {saved ? (
              <motion.span
                key="saved"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                className="inline-flex items-center gap-1.5"
              >
                <Check size={16} /> Saved
              </motion.span>
            ) : (
              <motion.span
                key="save"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
              >
                Save Changes
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>
      </form>

      {/* Invite code */}
      <div className="mt-5 bg-space-700 border border-space-500 rounded-2xl p-5">
        <div className="text-xs text-gray-400 uppercase tracking-wider">Your Referral Code</div>
        <div className="mt-2 flex items-center justify-between gap-3">
          <span className="font-mono font-bold text-2xl text-white tracking-wider">
            {user?.referralCode}
          </span>
          <button
            type="button"
            onClick={onCopy}
            className="h-10 w-10 rounded-full bg-space-600 border border-space-500 hover:border-teal-400 grid place-items-center text-teal-300 transition"
            aria-label="Copy referral code"
          >
            <Copy size={16} />
          </button>
        </div>
      </div>

      {/* Change password */}
      <div className="mt-5 bg-space-700 border border-space-500 rounded-2xl overflow-hidden">
        <button
          type="button"
          onClick={() => setPwOpen((o) => !o)}
          className="w-full flex items-center justify-between px-5 py-4 hover:bg-space-600/40 transition"
        >
          <span className="flex items-center gap-2 text-sm font-medium text-white">
            <ShieldCheck size={16} className="text-teal-300" />
            Change Password
          </span>
          <motion.span animate={{ rotate: pwOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
            <ChevronDown size={18} className="text-gray-400" />
          </motion.span>
        </button>
        <AnimatePresence initial={false}>
          {pwOpen && (
            <motion.form
              key="pw"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25 }}
              onSubmit={onUpdatePassword}
              className="px-5 pb-5 pt-1 space-y-3"
            >
              <Field
                label="Current Password"
                type="password"
                value={pw.current}
                onChange={(e) => setPw((p) => ({ ...p, current: e.target.value }))}
                error={pwErrors.current}
              />
              <Field
                label="New Password"
                type="password"
                value={pw.next}
                onChange={(e) => setPw((p) => ({ ...p, next: e.target.value }))}
                error={pwErrors.next}
              />
              <Field
                label="Confirm New Password"
                type="password"
                value={pw.confirm}
                onChange={(e) => setPw((p) => ({ ...p, confirm: e.target.value }))}
                error={pwErrors.confirm}
              />
              <button
                type="submit"
                className="w-full h-11 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 font-semibold shadow-teal-glow transition active:scale-[0.98]"
              >
                Update Password
              </button>
            </motion.form>
          )}
        </AnimatePresence>
      </div>

      {/* Logout */}
      <button
        type="button"
        onClick={() => {
          logout()
          showToast('Signed out', 'info')
        }}
        className="w-full mt-5 h-11 rounded-full bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 font-semibold border border-rose-400/30 transition flex items-center justify-center gap-2"
      >
        <LogOut size={16} /> Sign Out
      </button>
    </div>
  )
}

function StatusChip({ active, label, icon }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border ${
        active
          ? 'bg-emerald-500/15 border-emerald-400/40 text-emerald-300'
          : 'bg-space-700 border-space-500 text-gray-400'
      }`}
    >
      {icon ?? (active ? <Check size={12} /> : <span>○</span>)}
      {label}
    </span>
  )
}
