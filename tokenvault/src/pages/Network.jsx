import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Copy } from 'lucide-react'
import StarField from '../components/StarField.jsx'
import NodePopup from '../components/NodePopup.jsx'
import { L1_NODES, L2_NODES } from '../data/network.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useToast } from '../context/ToastContext.jsx'

const RADIUS_L1 = 130
const RADIUS_L2 = 220

function initials(name) {
  return name.split(' ').map((p) => p[0]).slice(0, 2).join('')
}

function polar(cx, cy, r, angle) {
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)]
}

export default function Network() {
  const { user } = useAuth()
  const { showToast } = useToast()
  const [selected, setSelected] = useState(null)

  const VIEWBOX = 520
  const CENTER = VIEWBOX / 2

  const l1Positions = useMemo(
    () =>
      L1_NODES.map((node, i) => {
        const angle = (i / L1_NODES.length) * Math.PI * 2 - Math.PI / 2
        const [x, y] = polar(CENTER, CENTER, RADIUS_L1, angle)
        return { ...node, x, y, angle }
      }),
    [],
  )

  const l2Positions = useMemo(() => {
    return L2_NODES.map((node, i) => {
      const parent = l1Positions.find((p) => p.id === node.parent)
      const angle = (i / L2_NODES.length) * Math.PI * 2 - Math.PI / 2
      const [x, y] = polar(CENTER, CENTER, RADIUS_L2, angle)
      return { ...node, x, y, parent }
    })
  }, [l1Positions])

  const empty = L1_NODES.length === 0

  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(user?.referralCode || 'TOKEN2024')
      showToast('Invite code copied', 'success')
    } catch {
      showToast('Copy failed', 'error')
    }
  }

  return (
    <div className="relative min-h-[100dvh] w-full overflow-hidden bg-space-900 pb-20">
      <StarField />

      {/* Counter pills */}
      <div className="relative z-20 flex items-center justify-center gap-2 pt-5 px-5">
        <span className="px-3 py-1 rounded-full bg-teal-500/15 border border-teal-400/40 text-teal-300 text-xs font-medium">
          Level 1 · {L1_NODES.length} members
        </span>
        <span className="px-3 py-1 rounded-full bg-purple-500/15 border border-purple-400/40 text-purple-300 text-xs font-medium">
          Level 2 · {L2_NODES.length} members
        </span>
      </div>

      {/* Galaxy */}
      <div className="relative z-10 mt-4 flex items-center justify-center">
        <svg viewBox={`0 0 ${VIEWBOX} ${VIEWBOX}`} className="w-full max-w-[480px] aspect-square">
          {/* Ghost orbit rings */}
          <circle
            cx={CENTER} cy={CENTER} r={RADIUS_L1}
            fill="none" stroke="rgba(45,212,191,0.25)" strokeDasharray="4 6" strokeWidth="1"
          />
          <circle
            cx={CENTER} cy={CENTER} r={RADIUS_L2}
            fill="none" stroke="rgba(168,85,247,0.2)" strokeDasharray="3 7" strokeWidth="1"
          />

          {/* L1 group with rotation */}
          <g style={{ transformOrigin: `${CENTER}px ${CENTER}px` }} className="animate-spin-slow">
            {!empty && l1Positions.map((n) => (
              <line
                key={`line-${n.id}`}
                x1={CENTER} y1={CENTER} x2={n.x} y2={n.y}
                stroke="rgba(45,212,191,0.45)" strokeWidth="1" strokeDasharray="4 4"
              >
                <animate attributeName="stroke-dashoffset" from="0" to="-32" dur="3s" repeatCount="indefinite" />
              </line>
            ))}
            {l1Positions.map((n) => (
              <g
                key={n.id}
                style={{ transformOrigin: `${n.x}px ${n.y}px` }}
                className="cursor-pointer"
                onClick={() => setSelected(n)}
              >
                {/* Counter-rotate so the labels stay upright */}
                <g style={{ transformOrigin: `${n.x}px ${n.y}px` }} className="animate-spin-slower">
                  <circle cx={n.x} cy={n.y} r="22" fill="rgba(45,212,191,0.2)" stroke="#2DD4BF" strokeWidth="1.5" />
                  <text x={n.x} y={n.y + 4} textAnchor="middle" fill="#5EEAD4" fontSize="11" fontWeight="700">
                    {initials(n.name)}
                  </text>
                </g>
              </g>
            ))}
          </g>

          {/* L2 group with rotation (opposite) */}
          <g style={{ transformOrigin: `${CENTER}px ${CENTER}px` }} className="animate-spin-slower">
            {l2Positions.map((n) => (
              <line
                key={`line2-${n.id}`}
                x1={n.parent?.x ?? CENTER} y1={n.parent?.y ?? CENTER} x2={n.x} y2={n.y}
                stroke="rgba(168,85,247,0.35)" strokeWidth="0.75" strokeDasharray="3 5"
              >
                <animate attributeName="stroke-dashoffset" from="0" to="-24" dur="4s" repeatCount="indefinite" />
              </line>
            ))}
            {l2Positions.map((n) => (
              <g key={n.id} className="cursor-pointer" onClick={() => setSelected(n)}>
                <circle cx={n.x} cy={n.y} r="15" fill="rgba(168,85,247,0.2)" stroke="#A78BFA" strokeWidth="1.25" />
                <text x={n.x} y={n.y + 3} textAnchor="middle" fill="#C4B5FD" fontSize="9" fontWeight="700">
                  {initials(n.name)}
                </text>
              </g>
            ))}
          </g>

          {/* Center user node */}
          <g>
            <circle
              cx={CENTER} cy={CENTER} r="34"
              fill="rgba(45,212,191,0.18)" stroke="#2DD4BF" strokeWidth="2"
            >
              <animate attributeName="r" values="34;36;34" dur="2.6s" repeatCount="indefinite" />
            </circle>
            <text x={CENTER} y={CENTER + 5} textAnchor="middle" fill="#FFFFFF" fontSize="14" fontWeight="700">
              {initials(`${user?.firstName || 'Y'} ${user?.lastName || 'OU'}`)}
            </text>
          </g>
        </svg>
      </div>

      {empty && (
        <div className="absolute inset-0 grid place-items-center px-6 z-30">
          <div className="bg-space-700/80 backdrop-blur-xl border border-space-500 rounded-2xl p-6 text-center max-w-xs">
            <h3 className="font-semibold text-white">Invite friends to grow your network</h3>
            <p className="text-xs text-gray-400 mt-1">Share your code to start earning rewards together.</p>
            <button
              type="button"
              onClick={copyInvite}
              className="mt-4 h-11 px-5 rounded-full bg-teal-500 text-space-900 font-semibold inline-flex items-center gap-2 shadow-teal-glow"
            >
              <Copy size={16} /> Copy Invite Code
            </button>
          </div>
        </div>
      )}

      {/* Invite shortcut */}
      {!empty && (
        <motion.button
          type="button"
          whileTap={{ scale: 0.96 }}
          onClick={copyInvite}
          className="absolute left-1/2 -translate-x-1/2 bottom-20 z-20 flex items-center gap-2 h-10 px-4 rounded-full bg-space-700/80 backdrop-blur-xl border border-space-500 text-sm text-teal-300"
        >
          <Copy size={14} /> Copy invite code
        </motion.button>
      )}

      <NodePopup node={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
