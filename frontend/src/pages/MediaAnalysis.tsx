import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { RecordingList } from '@/components/analysis/RecordingList'
import { VideoWorkspace } from '@/components/analysis/VideoWorkspace'
import { AnalysisTimeline } from '@/components/analysis/AnalysisTimeline'
import { DetectionPanel } from '@/components/analysis/DetectionPanel'
import { AIConfidence } from '@/components/analysis/AIConfidence'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/Badge'
import { getRecordings } from '@/services/mockApi'
import type { DetectionEvent, Recording } from '@/services/types'

export function MediaAnalysis() {
  const [searchParams] = useSearchParams()
  const [recordings, setRecordings] = useState<Recording[] | null>(null)
  const [selectedId, setSelectedId] = useState<string | undefined>()
  const [search, setSearch] = useState('')
  const [currentTime, setCurrentTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    getRecordings().then((all) => {
      const videos = all.filter((r) => r.durationSeconds > 0)
      setRecordings(videos)
      const requested = searchParams.get('recording')
      const preselect = requested && videos.some((v) => v.id === requested) ? requested : videos[0]?.id
      setSelectedId(preselect)
    })
  }, [searchParams])

  const filteredRecordings = useMemo(() => {
    if (!recordings) return []
    if (!search.trim()) return recordings
    return recordings.filter((r) => r.id.toLowerCase().includes(search.toLowerCase()))
  }, [recordings, search])

  const selected = recordings?.find((r) => r.id === selectedId) ?? null

  useEffect(() => {
    setCurrentTime(0)
    setPlaying(false)
  }, [selectedId])

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    if (playing && selected) {
      intervalRef.current = setInterval(() => {
        setCurrentTime((t) => {
          const next = t + 0.5 * speed
          if (next >= selected.durationSeconds) {
            setPlaying(false)
            return selected.durationSeconds
          }
          return next
        })
      }, 500)
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [playing, speed, selected])

  const activeEvent: DetectionEvent | null = useMemo(() => {
    if (!selected) return null
    const withinWindow = selected.detectionEvents.filter(
      (e) => currentTime >= e.timestampSeconds && currentTime < e.timestampSeconds + 4,
    )
    return withinWindow[withinWindow.length - 1] ?? null
  }, [selected, currentTime])

  if (!recordings) {
    return (
      <>
        <PageHeader title="Media Analysis" description="Loading recording index..." />
        <LoadingState label="Loading recordings..." />
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Media Analysis"
        description="AI-assisted review of CCTV and DVR recordings."
        actions={<Badge tone="accent">Demo Analysis</Badge>}
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[240px_minmax(0,1fr)_300px]">
        <div className="h-[560px]">
          <RecordingList
            recordings={filteredRecordings}
            selectedId={selectedId}
            onSelect={(r) => setSelectedId(r.id)}
            search={search}
            onSearchChange={setSearch}
          />
        </div>

        <div className="space-y-4">
          {selected ? (
            <>
              <VideoWorkspace
                recording={selected}
                currentTime={currentTime}
                playing={playing}
                speed={speed}
                onSeek={setCurrentTime}
                onTogglePlay={() => setPlaying((p) => !p)}
                onSpeedChange={setSpeed}
                activeEvent={activeEvent}
              />
              <Card>
                <CardHeader>
                  <CardTitle>Forensic Timeline</CardTitle>
                </CardHeader>
                <CardContent>
                  <AnalysisTimeline
                    recording={selected}
                    activeEvent={activeEvent}
                    onJump={(seconds) => setCurrentTime(seconds)}
                  />
                </CardContent>
              </Card>
            </>
          ) : (
            <p className="text-sm text-fg-muted">Select a recording to begin analysis.</p>
          )}
        </div>

        <div className="space-y-4">
          {selected && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Detection Summary</CardTitle>
                </CardHeader>
                <CardContent>
                  <DetectionPanel recording={selected} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>AI Confidence</CardTitle>
                </CardHeader>
                <CardContent>
                  <AIConfidence recording={selected} />
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </>
  )
}
