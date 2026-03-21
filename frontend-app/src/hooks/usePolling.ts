import { useEffect, useRef } from 'react'

interface PollingOptions<T> {
  fetcher: () => Promise<T>
  interval: number
  enabled: boolean
  onData: (data: T) => void
  shouldStop: (data: T) => boolean
  onError?: (err: unknown) => void
}

export function usePolling<T>({
  fetcher, interval, enabled, onData, shouldStop, onError,
}: PollingOptions<T>) {
  const stopRef = useRef(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!enabled) return
    stopRef.current = false

    const poll = async () => {
      if (stopRef.current) return
      try {
        const data = await fetcher()
        onData(data)
        if (shouldStop(data)) {
          stopRef.current = true
          return
        }
      } catch (err) {
        onError?.(err)
      }
      if (!stopRef.current) {
        timerRef.current = setTimeout(poll, interval)
      }
    }

    timerRef.current = setTimeout(poll, 0) // first poll immediately

    return () => {
      stopRef.current = true
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [enabled]) // eslint-disable-line react-hooks/exhaustive-deps
}
