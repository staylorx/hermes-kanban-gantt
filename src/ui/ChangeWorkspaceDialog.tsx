import { useEffect, useState } from 'react'
import {
  Button,
  Codicon,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch
} from '@hermes/plugin-sdk'
import { WORKSPACE_KINDS } from './NewTaskDialog'

/** The i18n hook's return, without importing the hook itself. */
type GanttI18n = ReturnType<typeof import('../i18n').useGanttI18n>

type Props = {
  open: boolean
  taskId: string
  taskTitle: string
  currentKind: string
  currentPath?: string | null
  currentStatus: string
  i18n: GanttI18n
  onClose: () => void
  onChange: (kind: string, path: string | undefined, moveToReady: boolean) => Promise<unknown>
}

/**
 * Change a task's workspace kind (and optional path).
 *
 * Changing the workspace does NOT reset a card's status, so a blocked/todo
 * card would never re-run after the fix — default the requeue checkbox ON for
 * exactly those states (the 'un-stick it' path). Hidden when already ready;
 * inapplicable for running/done/archived.
 */
export function ChangeWorkspaceDialog({ open, taskId, taskTitle, currentKind,
  currentPath, currentStatus, i18n, onClose, onChange }: Props) {
  const [kind, setKind] = useState('scratch')
  const [path, setPath] = useState('')
  const [moveToReady, setMoveToReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canRequeue = currentStatus === 'blocked' || currentStatus === 'todo'

  // Reset per open — dialog is externally controlled. Re-seed from the task.
  useEffect(() => {
    if (open) {
      setKind(currentKind === 'scratch' ? 'scratch' : currentKind)
      setPath(currentKind === 'scratch' ? '' : (currentPath || ''))
      setMoveToReady(canRequeue)
      setBusy(false)
      setError(null)
    }
  }, [open, currentKind, currentPath, canRequeue])

  const submit = async () => {
    if (busy) return
    const trimmed = path.trim()
    if (kind !== 'scratch' && !trimmed) {
      setError(i18n.changeWorkspacePathRequired)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await onChange(kind, kind === 'scratch' ? undefined : trimmed, canRequeue && moveToReady)
      onClose()
    } catch (err) {
      setError(String((err as Error)?.message || err))
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={o => !o && !busy && onClose()}>
      <DialogContent className="w-[min(30rem,94vw)] max-w-none">
        <div className="flex flex-col gap-3">
          <DialogHeader>
            <DialogTitle>{i18n.changeWorkspace}</DialogTitle>
          </DialogHeader>

          <span className="truncate text-[0.75rem] text-(--ui-text-secondary)">{taskTitle}</span>

          <Select value={kind} onValueChange={setKind}>
            <SelectTrigger aria-label={i18n.changeWorkspaceKind}>
              <SelectValue placeholder={i18n.changeWorkspaceKind} />
            </SelectTrigger>
            <SelectContent>
              {WORKSPACE_KINDS.map(k => (
                <SelectItem key={k} value={k} className="font-mono">{k}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {kind !== 'scratch' && (
            <Input
              value={path}
              placeholder={i18n.changeWorkspacePathPlaceholder}
              aria-label={i18n.changeWorkspacePath}
              onChange={e => setPath(e.target.value)}
            />
          )}

          {canRequeue && (
            <label className="flex items-center gap-2 text-[11px] text-(--ui-text-secondary)">
              <Switch checked={moveToReady} onCheckedChange={v => setMoveToReady(Boolean(v))} />
              {i18n.changeWorkspaceMoveToReady}
            </label>
          )}

          {error ? <span className="text-[0.75rem] text-destructive">{error}</span> : null}

          <DialogFooter>
            <Button disabled={busy} onClick={onClose} size="sm" variant="ghost">{i18n.cancel}</Button>
            <Button disabled={busy} onClick={() => void submit()} size="sm">
              {busy ? <Codicon name="loading" size="0.75rem" spinning /> : i18n.changeWorkspaceConfirm}
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  )
}
