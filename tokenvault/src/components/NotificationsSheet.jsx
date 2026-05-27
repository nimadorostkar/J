import { useCallback, useEffect, useState } from 'react'
import {
  Bell,
  ArrowDownCircle,
  ArrowUpCircle,
  Gift,
  Users,
  Star,
  CheckCheck,
} from 'lucide-react'
import BottomSheet from './BottomSheet.jsx'
import { notificationsApi } from '../api'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../i18n/LanguageContext.jsx'

function typeIcon(type) {
  if (type === 'deposit') return <ArrowDownCircle size={18} className="text-emerald-400" />
  if (type === 'withdraw') return <ArrowUpCircle size={18} className="text-rose-400" />
  if (type === 'reward') return <Gift size={18} className="text-gold-400" />
  if (type === 'commission') return <Users size={18} className="text-teal-300" />
  return <Bell size={18} className="text-gray-300" />
}

function timeAgo(iso, t) {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  const diff = Math.max(0, Date.now() - then)
  const s = Math.floor(diff / 1000)
  if (s < 60) return t?.('common.justNow') || 'just now'
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h`
  const d = Math.floor(h / 24)
  if (d < 30) return `${d}d`
  return new Date(iso).toLocaleDateString()
}

export default function NotificationsSheet({ open, onClose, onUnreadChange }) {
  const t = useT()
  const { showToast } = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [nextCursor, setNextCursor] = useState(null)
  const [loadingMore, setLoadingMore] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await notificationsApi.list()
      // CursorPagination yields { results, next, previous } — `next` is a
      // full URL; we just need the `cursor` query param when paging.
      setItems(Array.isArray(r?.results) ? r.results : (Array.isArray(r) ? r : []))
      setNextCursor(r?.next || null)
    } catch (e) {
      showToast(e?.message || 'Failed to load notifications', 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    if (!open) return
    load()
  }, [open, load])

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return
    setLoadingMore(true)
    try {
      // Extract the `cursor` query param from `next` for the next request.
      let cursor = null
      try {
        const url = new URL(nextCursor, window.location.origin)
        cursor = url.searchParams.get('cursor')
      } catch {}
      const r = await notificationsApi.list({ cursor })
      setItems((prev) => [...prev, ...(r?.results || [])])
      setNextCursor(r?.next || null)
    } catch (e) {
      showToast(e?.message || 'Failed to load more', 'error')
    } finally {
      setLoadingMore(false)
    }
  }

  const onClickItem = async (n) => {
    if (n.isRead) return
    // Optimistic UI — flip read flag locally, then sync to backend.
    setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, isRead: true } : x)))
    onUnreadChange?.((v) => Math.max(0, (v || 1) - 1))
    try {
      await notificationsApi.markRead(n.id)
    } catch (e) {
      // Revert on failure
      setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, isRead: false } : x)))
      onUnreadChange?.((v) => (v || 0) + 1)
      showToast(e?.message || 'Could not mark as read', 'error')
    }
  }

  const onMarkAll = async () => {
    const prev = items
    setItems((arr) => arr.map((x) => ({ ...x, isRead: true })))
    onUnreadChange?.(0)
    try {
      await notificationsApi.markAllRead()
      showToast(t('wallet.markedAllRead'), 'success')
    } catch (e) {
      setItems(prev)
      showToast(e?.message || t('wallet.couldNotUpdate'), 'error')
    }
  }

  const hasUnread = items.some((x) => !x.isRead)

  return (
    <BottomSheet open={open} onClose={onClose} title={t('wallet.notifications')}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-gray-400">
          {loading ? '…' : items.length > 0 ? `${items.length}` : ''}
        </span>
        <button
          type="button"
          disabled={!hasUnread || loading}
          onClick={onMarkAll}
          className="text-xs inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-space-500 bg-space-800 text-gray-200 hover:border-teal-400 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          <CheckCheck size={14} />
          {t('wallet.markedAllRead')}
        </button>
      </div>

      <div className="max-h-[60vh] overflow-y-auto -mx-2 px-2">
        {loading && items.length === 0 ? (
          <div className="py-10 text-center text-sm text-gray-400">…</div>
        ) : items.length === 0 ? (
          <div className="py-10 text-center text-sm text-gray-400">
            {t('wallet.noNotifications') || 'No notifications yet.'}
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((n) => (
              <li
                key={n.id}
                onClick={() => onClickItem(n)}
                className={
                  'rounded-2xl border px-3 py-3 cursor-pointer transition ' +
                  (n.isRead
                    ? 'border-space-500 bg-space-800/60 hover:bg-space-800'
                    : 'border-teal-400/40 bg-teal-500/5 hover:bg-teal-500/10')
                }
              >
                <div className="flex items-start gap-3">
                  <div className="h-9 w-9 rounded-full bg-space-700 grid place-items-center shrink-0">
                    {typeIcon(n.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-semibold text-sm text-white truncate">{n.title}</div>
                      <div className="text-[11px] text-gray-400 shrink-0">{timeAgo(n.createdAt, t)}</div>
                    </div>
                    {n.body && (
                      <div className="text-[13px] text-gray-300 mt-0.5 break-words">{n.body}</div>
                    )}
                  </div>
                  {!n.isRead && (
                    <span className="mt-1 h-2 w-2 rounded-full bg-teal-400 shrink-0" />
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}

        {nextCursor && (
          <div className="pt-3 pb-1 text-center">
            <button
              type="button"
              disabled={loadingMore}
              onClick={loadMore}
              className="text-xs px-3 py-1.5 rounded-full border border-space-500 hover:border-teal-400 transition disabled:opacity-50"
            >
              {loadingMore ? '…' : (t('common.loadMore') || 'Load more')}
            </button>
          </div>
        )}
      </div>
    </BottomSheet>
  )
}
