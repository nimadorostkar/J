import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Copy } from 'lucide-react'
import StarField from '../components/StarField.jsx'
import NodePopup from '../components/NodePopup.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../i18n/LanguageContext.jsx'
import { referralsApi, resolveMediaUrl } from '../api'

const RADIUS_L1 = 130
const RADIUS_L2 = 220

function initials(name = '') {
  return name.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()
}

function polar(cx, cy, r, angle) {
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)]
}

function toUiNode(row, level, t) {
  const u = row.invitedUser || row.invited_user || {}
  const name = `${u.firstName || ''} ${u.lastName || ''}`.trim() || u.email || t('network.member')
  const statusKey = STATUS_KEY[row.status] || STATUS_KEY.registered
  return {
    id: row.id,
    level,
    name,
    avatar: resolveMediaUrl(u.avatarUrl),
    joined: u.joinedAt ? new Date(u.joinedAt).toISOString().slice(0, 10) : '',
    // New status fields from backend
    isVerified: !!row.isVerified,
    hasDeposit: !!row.hasDeposit,
    isQualified: !!row.isQualified,
    statusCode: row.status || 'registered',
    statusLabel: t(statusKey),
    commission: row.totalCommissionEarnedHcoin ?? '0',
    parent: row.parent || null,
  }
}

// Map backend status codes → translation keys (resolved at render time).
const STATUS_KEY = {
  registered: 'network.statusRegistered',
  verified: 'network.statusVerified',
  first_deposit_completed: 'network.statusFirstDeposit',
  qualified: 'network.statusQualified',
}

export default function Network() {
  const { user } = useAuth()
  const { showToast } = useToast()
  const t = useT()
  const [selected, setSelected] = useState(null)
  const [l1, setL1] = useState([])
  const [l2, setL2] = useState([])
  const [shareUrl, setShareUrl] = useState('')
  const [code, setCode] = useState(user?.referralCode || '')
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.allSettled([
      referralsApi.network(),
      referralsApi.code(),
      referralsApi.stats(),
    ])
      .then(([net, codeRes, statsRes]) => {
        if (cancelled) return
        if (net.status === 'fulfilled' && net.value) {
          setL1((net.value.level1 || []).map((r) => toUiNode(r, 1, t)))
          setL2((net.value.level2 || []).map((r) => toUiNode(r, 2, t)))
        }
        if (codeRes.status === 'fulfilled' && codeRes.value) {
          setCode(codeRes.value.code)
          setShareUrl(codeRes.value.shareUrl || '')
        }
        if (statsRes.status === 'fulfilled' && statsRes.value) {
          setStats(statsRes.value)
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  // Milestone progress (optional — backend may not include yet)
  const milestone = stats?.milestone || null

  const VIEWBOX = 520
  const CENTER = VIEWBOX / 2

  // Avatar URL for the center node. Falls back to initials if missing or 404.
  const avatarHref = user?.avatarUrl ? resolveMediaUrl(user.avatarUrl) : null

  const l1Positions = useMemo(
    () =>
      l1.map((node, i) => {
        const angle = (i / Math.max(1, l1.length)) * Math.PI * 2 - Math.PI / 2
        const [x, y] = polar(CENTER, CENTER, RADIUS_L1, angle)
        return { ...node, x, y, angle }
      }),
    [l1, CENTER],
  )

  const l2Positions = useMemo(() => {
    return l2.map((node, i) => {
      const parent = l1Positions[i % Math.max(1, l1Positions.length)] || null
      const angle = (i / Math.max(1, l2.length)) * Math.PI * 2 - Math.PI / 2
      const [x, y] = polar(CENTER, CENTER, RADIUS_L2, angle)
      return { ...node, x, y, parent }
    })
  }, [l2, l1Positions, CENTER])

  const empty = !loading && l1.length === 0

  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl || code || '')
      showToast(t('network.inviteCopied'), 'success')
    } catch {
      showToast(t('common.copyFailed'), 'error')
    }
  }

  return (
    <div className="relative min-h-[100dvh] w-full overflow-hidden bg-space-900 pb-20">
      <StarField />

      {/* Counter pills — qualified vs registered */}
      <div className="relative z-20 flex flex-wrap items-center justify-center gap-2 pt-5 px-5">
        <span className="px-3 py-1 rounded-full bg-teal-500/15 border border-teal-400/40 text-teal-300 text-xs font-medium">
          {t('network.l1SignedUp', { count: l1.length })}
        </span>
        <span className="px-3 py-1 rounded-full bg-emerald-500/15 border border-emerald-400/40 text-emerald-300 text-xs font-medium">
          {t('network.qualified', { count: stats?.qualifiedCount ?? 0 })}
        </span>
        {(stats?.pendingDepositCount ?? 0) > 0 && (
          <span className="px-3 py-1 rounded-full bg-amber-500/15 border border-amber-400/40 text-amber-300 text-xs font-medium">
            {t('network.awaitingDeposit', { count: stats.pendingDepositCount })}
          </span>
        )}
        <span className="px-3 py-1 rounded-full bg-purple-500/15 border border-purple-400/40 text-purple-300 text-xs font-medium">
          {t('network.l2Count', { count: l2.length })}
        </span>
      </div>

      {/* Milestone progress card — based on QUALIFIED referrals only */}
      {milestone && (
        <div className="relative z-20 mx-5 mt-3 rounded-2xl border border-gold-400/40 bg-gradient-to-br from-gold-500/10 to-space-700 p-3.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-semibold text-gold-300 uppercase tracking-wider">
              {t('network.milestones')}
            </span>
            <span className="font-mono text-[12px] font-bold text-gold-300">
              {t('network.milestonePer', { reward: milestone.rewardHcoin, size: milestone.size })}
            </span>
          </div>
          <p className="text-[11px] text-gray-400 leading-snug">
            {milestone.qualifiedUntilNext > 0
              ? t('network.moreToNext', {
                  count: milestone.qualifiedUntilNext,
                  label: milestone.qualifiedUntilNext === 1
                    ? t('network.qualifiedReferral')
                    : t('network.qualifiedReferrals'),
                  next: milestone.nextMilestoneAt,
                })
              : t('network.unlocked')}
          </p>
          <div className="mt-2 h-1 rounded-full bg-space-600 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-gold-400 to-gold-500 transition-all"
              style={{ width: `${Math.min(100, milestone.progressPercent || 0)}%` }}
            />
          </div>
          <p className="mt-2 text-[10px] text-amber-200/80 leading-snug italic">
            {t('network.qualifyingNote')}
          </p>
          {milestone.milestonesPaid > 0 && (
            <p className="mt-1.5 text-[10.5px] text-gray-500">
              {milestone.milestonesPaid === 1
                ? t('network.milestonesPaidOne', { count: milestone.milestonesPaid, total: milestone.totalRewardEarnedHcoin })
                : t('network.milestonesPaidMany', { count: milestone.milestonesPaid, total: milestone.totalRewardEarnedHcoin })}
            </p>
          )}
        </div>
      )}

      {/* Galaxy */}
      <div className="relative z-10 mt-4 flex items-center justify-center">
        <svg viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`} className="w-full max-w-[480px] aspect-square">
          <circle cx={CENTER} cy={CENTER} r={RADIUS_L1} fill="none" stroke="rgba(45,212,191,0.25)" strokeDasharray="4 6" strokeWidth="1" />
          <circle cx={CENTER} cy={CENTER} r={RADIUS_L2} fill="none" stroke="rgba(168,85,247,0.2)" strokeDasharray="3 7" strokeWidth="1" />

          <g style={{ transformOrigin: `${CENTER}px ${CENTER}px` }} className="animate-spin-slow">
            {!empty && l1Positions.map((n) => (
              <line key={`line-${n.id}`} x1={CENTER} y1={CENTER} x2={n.x} y2={n.y}
                stroke="rgba(45,212,191,0.45)" strokeWidth="1" strokeDasharray="4 4">
                <animate attributeName="stroke-dashoffset" from="0" to="-32" dur="3s" repeatCount="indefinite" />
              </line>
            ))}
            {l1Positions.map((n) => {
              const clipId = `l1Clip-${n.id}`
              // Color the ring by qualification status:
              //   qualified  → teal (#2DD4BF)
              //   not yet    → amber (#F59E0B) so the user can see who they're waiting on
              const ringColor = n.isQualified ? '#2DD4BF' : '#F59E0B'
              return (
                <g
                  key={n.id}
                  style={{ transformOrigin: `${n.x}px ${n.y}px` }}
                  className="cursor-pointer"
                  onClick={() => setSelected(n)}
                >
                  <g style={{ transformOrigin: `${n.x}px ${n.y}px` }} className="animate-spin-slower">
                    <defs>
                      <clipPath id={clipId}>
                        <circle cx={n.x} cy={n.y} r="20" />
                      </clipPath>
                    </defs>
                    {/* Background glow */}
                    <circle
                      cx={n.x} cy={n.y} r="22"
                      fill={n.isQualified ? 'rgba(45,212,191,0.2)' : 'rgba(245,158,11,0.18)'}
                    />
                    {n.avatar ? (
                      <image
                        href={n.avatar}
                        xlinkHref={n.avatar}
                        x={n.x - 20}
                        y={n.y - 20}
                        width="40"
                        height="40"
                        preserveAspectRatio="xMidYMid slice"
                        clipPath={`url(#${clipId})`}
                      />
                    ) : (
                      <text x={n.x} y={n.y + 4} textAnchor="middle"
                        fill={n.isQualified ? '#5EEAD4' : '#FCD34D'}
                        fontSize="11" fontWeight="700">
                        {initials(n.name)}
                      </text>
                    )}
                    {/* Status ring */}
                    <circle cx={n.x} cy={n.y} r="22" fill="none"
                      stroke={ringColor} strokeWidth="1.5" pointerEvents="none" />
                    {/* Small dot ↘ marks "awaiting deposit" so it stands out at a glance */}
                    {!n.isQualified && (
                      <circle cx={n.x + 16} cy={n.y - 16} r="4"
                        fill="#F59E0B" stroke="#1F2937" strokeWidth="1.5"
                        pointerEvents="none" />
                    )}
                  </g>
                </g>
              )
            })}
          </g>

          <g style={{ transformOrigin: `${CENTER}px ${CENTER}px` }} className="animate-spin-slower">
            {l2Positions.map((n) => (
              <line key={`line2-${n.id}`} x1={n.parent?.x ?? CENTER} y1={n.parent?.y ?? CENTER} x2={n.x} y2={n.y}
                stroke="rgba(168,85,247,0.35)" strokeWidth="0.75" strokeDasharray="3 5">
                <animate attributeName="stroke-dashoffset" from="0" to="-24" dur="4s" repeatCount="indefinite" />
              </line>
            ))}
            {l2Positions.map((n) => {
              const clipId = `l2Clip-${n.id}`
              return (
                <g key={n.id} className="cursor-pointer" onClick={() => setSelected(n)}>
                  <defs>
                    <clipPath id={clipId}>
                      <circle cx={n.x} cy={n.y} r="13.5" />
                    </clipPath>
                  </defs>
                  {/* Background glow */}
                  <circle cx={n.x} cy={n.y} r="15" fill="rgba(168,85,247,0.2)" />
                  {n.avatar ? (
                    <image
                      href={n.avatar}
                      xlinkHref={n.avatar}
                      x={n.x - 13.5}
                      y={n.y - 13.5}
                      width="27"
                      height="27"
                      preserveAspectRatio="xMidYMid slice"
                      clipPath={`url(#${clipId})`}
                    />
                  ) : (
                    <text x={n.x} y={n.y + 3} textAnchor="middle" fill="#C4B5FD" fontSize="9" fontWeight="700">
                      {initials(n.name)}
                    </text>
                  )}
                  {/* Border on top */}
                  <circle cx={n.x} cy={n.y} r="15" fill="none" stroke="#A78BFA" strokeWidth="1.25" pointerEvents="none" />
                </g>
              )
            })}
          </g>

          {/* Center user node — avatar (clipped to circle) + pulsing ring */}
          <g>
            <defs>
              <clipPath id="centerAvatarClip">
                <circle cx={CENTER} cy={CENTER} r="32" />
              </clipPath>
            </defs>
            {/* glow background */}
            <circle cx={CENTER} cy={CENTER} r="34" fill="rgba(45,212,191,0.18)" stroke="#2DD4BF" strokeWidth="2">
              <animate attributeName="r" values="34;36;34" dur="2.6s" repeatCount="indefinite" />
            </circle>
            {avatarHref ? (
              <image
                href={avatarHref}
                xlinkHref={avatarHref}
                x={CENTER - 32}
                y={CENTER - 32}
                width="64"
                height="64"
                preserveAspectRatio="xMidYMid slice"
                clipPath="url(#centerAvatarClip)"
              />
            ) : (
              <text x={CENTER} y={CENTER + 5} textAnchor="middle" fill="#FFFFFF" fontSize="14" fontWeight="700">
                {initials(`${user?.firstName || 'Y'} ${user?.lastName || 'OU'}`)}
              </text>
            )}
            {/* outline on top of the image so the border stays visible */}
            <circle cx={CENTER} cy={CENTER} r="32" fill="none" stroke="#2DD4BF" strokeWidth="2" pointerEvents="none" />
          </g>
        </svg>
      </div>

      {empty && (
        <div className="absolute inset-0 grid place-items-center px-6 z-30">
          <div className="bg-space-700/80 backdrop-blur-xl border border-space-500 rounded-2xl p-6 text-center max-w-xs">
            <h3 className="font-semibold text-white">{t('network.inviteFriends')}</h3>
            <p className="text-xs text-gray-400 mt-1">{t('network.shareDesc')}</p>
            <p className="mt-2 font-mono text-teal-300">{code}</p>
            <button
              type="button"
              onClick={copyInvite}
              className="mt-4 h-11 px-5 rounded-full bg-teal-500 text-space-900 font-semibold inline-flex items-center gap-2 shadow-teal-glow"
            >
              <Copy size={16} /> {t('network.copyInvite')}
            </button>
          </div>
        </div>
      )}

      {!empty && (
        <div className="absolute left-1/2 -translate-x-1/2 bottom-20 z-20">
          <motion.button
            type="button"
            whileTap={{ scale: 0.96 }}
            onClick={copyInvite}
            className="flex items-center gap-2 h-10 px-4 rounded-full bg-space-700/80 backdrop-blur-xl border border-space-500 text-sm text-teal-300"
          >
            <Copy size={14} /> {t('network.copyInviteWith', { code })}
          </motion.button>
        </div>
      )}

      <NodePopup node={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
