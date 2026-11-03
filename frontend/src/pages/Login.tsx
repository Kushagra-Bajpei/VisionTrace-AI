/**
 * VisionTrace AI – Tactical Security Authentication Portal.
 * Supports Operator Login, Registration, and System Admin Bootstrap.
 */
import React, { useState } from 'react'
import { Shield, Lock, Mail, User, AlertCircle, ArrowRight, CheckCircle2, KeyRound } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

interface LoginProps {
  onSuccess?: () => void
}

type AuthMode = 'login' | 'register' | 'bootstrap'

export const Login: React.FC<LoginProps> = ({ onSuccess }) => {
  const { login, register, bootstrapAdmin } = useAuth()
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccessMsg(null)
    setIsSubmitting(true)

    try {
      if (mode === 'login') {
        await login(email, password)
      } else if (mode === 'register') {
        await register(email, password, fullName)
        setSuccessMsg('Account registered successfully. Welcome to VisionTrace AI.')
      } else if (mode === 'bootstrap') {
        await bootstrapAdmin(email, password, fullName)
        setSuccessMsg('Administrator account initialized. Welcome Chief Administrator.')
      }
      if (onSuccess) onSuccess()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Authentication operation failed'
      setError(msg)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#07090e] flex items-center justify-center p-4 relative overflow-hidden font-sans">
      {/* Background cyber grid overlay */}
      <div className="absolute inset-0 bg-[radial-gradient(#162235_1px,transparent_1px)] [background-size:24px_24px] opacity-40 pointer-events-none" />

      {/* Decorative tactical ambient glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-md bg-[#0d111a] border border-cyan-500/20 rounded-xl shadow-2xl p-8 backdrop-blur-md">
        {/* Header Branding */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-xl bg-cyan-950/60 border border-cyan-400/40 flex items-center justify-center mb-4 shadow-[0_0_20px_rgba(0,229,255,0.2)]">
            <Shield className="w-7 h-7 text-cyan-400 animate-pulse" />
          </div>
          <h1 className="text-xl font-bold tracking-wider text-slate-100 uppercase flex items-center gap-2">
            VisionTrace <span className="text-cyan-400 font-mono text-sm tracking-normal px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/30">AI</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 uppercase tracking-widest font-mono">
            Surveillance Intelligence & Forensic Core
          </p>
        </div>

        {/* Mode Selector Tabs */}
        <div className="flex bg-[#080b11] p-1 rounded-lg border border-slate-800 mb-6 font-mono text-xs">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(null); }}
            className={`flex-1 py-2 text-center rounded transition-all ${
              mode === 'login'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Operator Sign In
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(null); }}
            className={`flex-1 py-2 text-center rounded transition-all ${
              mode === 'register'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Register
          </button>
          <button
            type="button"
            onClick={() => { setMode('bootstrap'); setError(null); }}
            className={`flex-1 py-2 text-center rounded transition-all ${
              mode === 'bootstrap'
                ? 'bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Bootstrap
          </button>
        </div>

        {/* Banner Alerts */}
        {error && (
          <div className="mb-6 p-3 rounded-lg bg-red-950/40 border border-red-500/30 text-red-300 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-400 mt-0.5" />
            <span className="leading-relaxed">{error}</span>
          </div>
        )}

        {successMsg && (
          <div className="mb-6 p-3 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs flex items-start gap-2.5">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400 mt-0.5" />
            <span className="leading-relaxed">{successMsg}</span>
          </div>
        )}

        {/* Auth Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {(mode === 'register' || mode === 'bootstrap') && (
            <div>
              <label className="block text-xs font-mono uppercase text-slate-400 mb-1.5">
                Full Operator Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Special Investigator Vance"
                  className="w-full pl-9 pr-3 py-2 bg-[#080b11] border border-slate-800 rounded-lg text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/30 transition-colors"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-mono uppercase text-slate-400 mb-1.5">
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@visiontrace.ai"
                className="w-full pl-9 pr-3 py-2 bg-[#080b11] border border-slate-800 rounded-lg text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/30 transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono uppercase text-slate-400 mb-1.5">
              Secure Key / Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Minimum 8 characters"
                className="w-full pl-9 pr-3 py-2 bg-[#080b11] border border-slate-800 rounded-lg text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/30 transition-colors"
              />
            </div>
          </div>

          {mode === 'bootstrap' && (
            <div className="p-3 bg-amber-950/20 border border-amber-500/30 rounded-lg text-amber-300 text-xs flex items-start gap-2">
              <KeyRound className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
              <span>
                System Bootstrap initializes the first root administrator account. This operation is locked once initialized.
              </span>
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-2 py-2.5 px-4 bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold text-xs uppercase tracking-wider rounded-lg flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(0,229,255,0.3)] transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {isSubmitting ? (
              <span className="inline-block w-4 h-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <span>
                  {mode === 'login' ? 'Authenticate Operator' : mode === 'register' ? 'Create Account' : 'Initialize Root Admin'}
                </span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Footer Audit Notice */}
        <div className="mt-8 pt-4 border-t border-slate-800/80 text-center text-[10px] text-slate-500 font-mono uppercase tracking-wider">
          All authentication attempts and surveillance sessions are cryptographically logged for forensic audit.
        </div>
      </div>
    </div>
  )
}
