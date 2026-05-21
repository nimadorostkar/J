import { AnimatePresence, motion } from 'framer-motion'

function initials(name) {
  return name.split(' ').map((p) => p[0]).slice(0, 2).join('')
}

export default function NodePopup({ node, onClose }) {
  return (
    <AnimatePresence>
      {node && (
        <motion.div
          className="fixed inset-0 z-40 flex items-center justify-center p-6"
          initial={{ backgroundColor: 'rgba(0,0,0,0)' }}
          animate={{ backgroundColor: 'rgba(0,0,0,0.55)' }}
          exit={{ backgroundColor: 'rgba(0,0,0,0)' }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ type: 'spring', stiffness: 360, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[320px] rounded-2xl bg-space-700 border border-space-500 p-5 shadow-card"
          >
            <div className="flex items-center gap-3">
              <div
                className={`h-14 w-14 rounded-full grid place-items-center font-bold text-white ${
                  node.parent ? 'bg-gradient-to-br from-purple-400 to-purple-600' : 'bg-gradient-to-br from-teal-400 to-teal-600'
                }`}
              >
                {initials(node.name)}
              </div>
              <div className="min-w-0">
                <div className="font-semibold text-white truncate">{node.name}</div>
                <div className="text-xs text-gray-400">Joined {node.joined}</div>
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between">
              <span className="text-xs text-gray-400 uppercase tracking-wider">Status</span>
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                  node.status === 'Active'
                    ? 'bg-emerald-500/20 text-emerald-300'
                    : 'bg-gold-500/20 text-gold-300'
                }`}
              >
                {node.status === 'Active' ? '● Active' : '○ Pending'}
              </span>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="w-full mt-5 h-10 rounded-full bg-space-600 hover:bg-space-500 text-sm text-white transition"
            >
              Close
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
