import { forwardRef, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

const Field = forwardRef(function Field(
  { label, error, type = 'text', prefix, suffix, className = '', ...props },
  ref,
) {
  const [show, setShow] = useState(false)
  const isPassword = type === 'password'
  const effectiveType = isPassword ? (show ? 'text' : 'password') : type

  return (
    <label className={`block ${className}`}>
      {label && (
        <span className="block text-xs font-medium text-gray-400 mb-1.5 tracking-wide">
          {label}
        </span>
      )}
      <div
        className={`flex items-center gap-2 bg-space-600 border rounded-xl px-3.5 min-h-[48px] transition focus-within:border-teal-400 focus-within:ring-2 focus-within:ring-teal-400/30 ${
          error ? 'border-rose-400/60' : 'border-space-500'
        }`}
      >
        {prefix && <span className="text-sm text-gray-400">{prefix}</span>}
        <input
          ref={ref}
          type={effectiveType}
          {...props}
          className="flex-1 bg-transparent outline-none text-white placeholder:text-gray-500 text-[15px] min-w-0"
        />
        {suffix && <span className="text-xs text-gray-400">{suffix}</span>}
        {isPassword && (
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="text-gray-400 hover:text-teal-300 transition"
            aria-label={show ? 'Hide password' : 'Show password'}
          >
            {show ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        )}
      </div>
      {error && <span className="block text-xs text-rose-400 mt-1.5">{error}</span>}
    </label>
  )
})

export default Field
