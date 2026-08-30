import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const value = bytes / Math.pow(1024, i)
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

export function formatRelativeTime(iso: string): string {
  const date = new Date(iso)
  const now = new Date('2026-08-27T10:45:00')
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.round(diffMs / 60000)

  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? '' : 's'} ago`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `${diffHr} hour${diffHr === 1 ? '' : 's'} ago`
  const diffDay = Math.round(diffHr / 24)
  if (diffDay < 7) return `${diffDay} day${diffDay === 1 ? '' : 's'} ago`
  return formatDate(iso)
}

export function formatDate(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function formatTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
}

export function truncateHash(hash: string, chars = 12): string {
  if (hash.length <= chars * 2) return hash
  return `${hash.slice(0, chars)}...`
}
