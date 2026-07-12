import { useCallback, useMemo, useRef, useState, type DragEvent } from "react";
import {
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  GripVertical,
  MessageSquare,
  Plus,
  Trash2,
} from "lucide-react";
import {
  SHOT_STATUS_OPTIONS,
  type DirectorCameraShot,
  type ShotDialogue,
  type ShotStatus,
} from "../schema/directorProject";
import { useDirectorStore } from "../store/directorStore";

function formatDuration(sec: number): string {
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m${s > 0 ? `${s}s` : ""}`;
}

function statusIcon(status: ShotStatus): string {
  return SHOT_STATUS_OPTIONS.find((o) => o.value === status)?.icon ?? "○";
}

function statusLabel(status: ShotStatus): string {
  return SHOT_STATUS_OPTIONS.find((o) => o.value === status)?.label ?? "待拍摄";
}

interface ShotCardProps {
  camera: DirectorCameraShot;
  index: number;
  isActive: boolean;
  onSelect: () => void;
  onDragStart: (e: DragEvent) => void;
  onDragOver: (e: DragEvent) => void;
  onDrop: (e: DragEvent) => void;
  onDragEnd: () => void;
  isDragTarget: boolean;
}

function ShotCard({
  camera,
  index,
  isActive,
  onSelect,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
  isDragTarget,
}: ShotCardProps) {
  const seq = camera.sequence;
  const updateShotSequence = useDirectorStore((s) => s.updateShotSequence);
  const setShotStatus = useDirectorStore((s) => s.setShotStatus);
  const addShotDialogue = useDirectorStore((s) => s.addShotDialogue);
  const updateShotDialogue = useDirectorStore((s) => s.updateShotDialogue);
  const removeShotDialogue = useDirectorStore((s) => s.removeShotDialogue);
  const reorderShots = useDirectorStore((s) => s.reorderShots);
  const objects = useDirectorStore((s) => s.project.objects);
  const [expanded, setExpanded] = useState(false);

  const characterObjects = useMemo(
    () => objects.filter((o) => o.kind === "character"),
    [objects]
  );

  const thumbnail = camera.lastCaptureUrl ?? camera.captures?.[camera.captures.length - 1]?.dataUrl;

  const handleAddDialogue = useCallback(() => {
    const firstChar = characterObjects[0];
    addShotDialogue(camera.id, {
      characterId: firstChar?.id ?? null,
      characterName: firstChar?.name ?? "角色",
      text: "",
    });
  }, [camera.id, characterObjects, addShotDialogue]);

  const handleMoveLeft = useCallback(() => {
    if (index > 0) reorderShots(index, index - 1);
  }, [index, reorderShots]);

  const handleMoveRight = useCallback(() => {
    reorderShots(index, index + 1);
  }, [index, reorderShots]);

  if (!seq) return null;

  return (
    <div
      className={`shot-card${isActive ? " is-active" : ""}${isDragTarget ? " is-drag-target" : ""}`}
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onDragEnd={onDragEnd}
    >
      {/* Card header */}
      <div className="shot-card-header" onClick={onSelect}>
        <span className="shot-card-drag-handle" aria-hidden="true">
          <GripVertical size={12} strokeWidth={1.8} />
        </span>
        <span className="shot-card-index">{String(index + 1).padStart(2, "0")}</span>
        {thumbnail ? (
          <img className="shot-card-thumb" src={thumbnail} alt={camera.name} />
        ) : (
          <div className="shot-card-thumb shot-card-thumb-placeholder">
            <span className="shot-card-thumb-text">{statusIcon(seq.status)}</span>
          </div>
        )}
        <div className="shot-card-info">
          <span className="shot-card-name">{camera.name}</span>
          <span className="shot-card-scene-group">{seq.sceneGroup}</span>
        </div>
        <div className="shot-card-meta">
          <span className="shot-card-duration" title="预估时长">
            <Clock size={11} strokeWidth={1.8} />
            {formatDuration(seq.durationSec)}
          </span>
          <span className="shot-card-status-badge" data-status={seq.status} title={statusLabel(seq.status)}>
            {statusIcon(seq.status)}
          </span>
        </div>
        <button
          type="button"
          className="shot-card-expand-btn"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(!expanded);
          }}
          aria-label={expanded ? "收起" : "展开"}
        >
          {expanded ? <ChevronDown size={14} strokeWidth={1.8} /> : <ChevronUp size={14} strokeWidth={1.8} />}
        </button>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="shot-card-body" onClick={(e) => e.stopPropagation()}>
          {/* Scene group & duration */}
          <div className="shot-card-row">
            <label className="shot-card-field">
              <span className="shot-card-field-label">场景</span>
              <input
                className="ui-field shot-card-input"
                type="text"
                value={seq.sceneGroup}
                onChange={(e) => updateShotSequence(camera.id, { sceneGroup: e.target.value })}
              />
            </label>
            <label className="shot-card-field shot-card-field-duration">
              <span className="shot-card-field-label">时长(s)</span>
              <input
                className="ui-field shot-card-input"
                type="number"
                min="1"
                max="600"
                value={seq.durationSec}
                onChange={(e) => updateShotSequence(camera.id, { durationSec: Math.max(1, Number(e.target.value) || 1) })}
              />
            </label>
          </div>

          {/* Status selector */}
          <div className="shot-card-row">
            <label className="shot-card-field shot-card-field-full">
              <span className="shot-card-field-label">状态</span>
              <div className="shot-card-status-options">
                {SHOT_STATUS_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={`shot-card-status-opt${seq.status === opt.value ? " is-active" : ""}`}
                    onClick={() => setShotStatus(camera.id, opt.value)}
                    title={opt.label}
                  >
                    <span className="shot-card-status-opt-icon">{opt.icon}</span>
                    <span className="shot-card-status-opt-label">{opt.label}</span>
                  </button>
                ))}
              </div>
            </label>
          </div>

          {/* Action description */}
          <label className="shot-card-field shot-card-field-full">
            <span className="shot-card-field-label">动作描述</span>
            <textarea
              className="ui-field shot-card-textarea"
              rows={2}
              placeholder="如：男主走向窗边，女主回头"
              value={seq.actionDescription}
              onChange={(e) => updateShotSequence(camera.id, { actionDescription: e.target.value })}
            />
          </label>

          {/* Dialogues */}
          <div className="shot-card-dialogues">
            <div className="shot-card-dialogues-header">
              <span className="shot-card-field-label">
                <MessageSquare size={12} strokeWidth={1.8} /> 台词
              </span>
              <button type="button" className="shot-card-add-btn" onClick={handleAddDialogue}>
                <Plus size={12} strokeWidth={1.8} /> 添加
              </button>
            </div>
            {seq.dialogues.length === 0 && (
              <p className="shot-card-dialogues-empty">暂无台词</p>
            )}
            {seq.dialogues.map((dlg: ShotDialogue) => (
              <div key={dlg.id} className="shot-card-dialogue-row">
                <select
                  className="ui-field shot-card-dialogue-char"
                  value={dlg.characterId ?? ""}
                  onChange={(e) => {
                    const charObj = characterObjects.find((c) => c.id === e.target.value);
                    updateShotDialogue(camera.id, dlg.id, {
                      characterId: e.target.value || null,
                      characterName: charObj?.name ?? "角色",
                    });
                  }}
                >
                  <option value="">旁白</option>
                  {characterObjects.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <input
                  className="ui-field shot-card-dialogue-text"
                  type="text"
                  placeholder="台词内容"
                  value={dlg.text}
                  onChange={(e) => updateShotDialogue(camera.id, dlg.id, { text: e.target.value })}
                />
                <button
                  type="button"
                  className="shot-card-dialogue-remove"
                  onClick={() => removeShotDialogue(camera.id, dlg.id)}
                  aria-label="删除台词"
                >
                  <Trash2 size={12} strokeWidth={1.8} />
                </button>
              </div>
            ))}
          </div>

          {/* Director notes */}
          <label className="shot-card-field shot-card-field-full">
            <span className="shot-card-field-label">导演笔记</span>
            <textarea
              className="ui-field shot-card-textarea"
              rows={1}
              placeholder="不影响AI生成，仅用于备忘"
              value={seq.directorNotes}
              onChange={(e) => updateShotSequence(camera.id, { directorNotes: e.target.value })}
            />
          </label>

          {/* Move buttons */}
          <div className="shot-card-move-actions">
            <button type="button" className="shot-card-move-btn" onClick={handleMoveLeft} disabled={index === 0}>
              ← 前移
            </button>
            <button type="button" className="shot-card-move-btn" onClick={handleMoveRight}>
              后移 →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function StoryboardPanel() {
  const cameras = useDirectorStore((s) => s.project.cameras);
  const activeCameraId = useDirectorStore((s) => s.project.activeCameraId);
  const setActiveCamera = useDirectorStore((s) => s.setActiveCamera);
  const reorderShots = useDirectorStore((s) => s.reorderShots);
  const storyboardPanelOpen = useDirectorStore((s) => s.storyboardPanelOpen);
  const toggleStoryboardPanel = useDirectorStore((s) => s.toggleStoryboardPanel);
  const setStoryboardPanelOpen = useDirectorStore((s) => s.setStoryboardPanelOpen);

  const dragIndexRef = useRef<number | null>(null);
  const [dragTargetIndex, setDragTargetIndex] = useState<number | null>(null);

  const sortedCameras = useMemo(() => {
    return [...cameras].sort((a, b) => {
      const oa = a.sequence?.order ?? 0;
      const ob = b.sequence?.order ?? 0;
      return oa - ob;
    });
  }, [cameras]);

  const totalDuration = useMemo(
    () => sortedCameras.reduce((sum, cam) => sum + (cam.sequence?.durationSec ?? 0), 0),
    [sortedCameras]
  );

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const cam of sortedCameras) {
      const status = cam.sequence?.status ?? "pending";
      counts[status] = (counts[status] ?? 0) + 1;
    }
    return counts;
  }, [sortedCameras]);

  const handleSelectCamera = useCallback(
    (cameraId: string) => {
      setActiveCamera(cameraId);
    },
    [setActiveCamera]
  );

  const handleDragStart = useCallback((index: number) => (e: DragEvent) => {
    dragIndexRef.current = index;
    e.dataTransfer.effectAllowed = "move";
  }, []);

  const handleDragOver = useCallback((index: number) => (e: DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragTargetIndex(index);
  }, []);

  const handleDrop = useCallback((index: number) => (e: DragEvent) => {
    e.preventDefault();
    const fromIndex = dragIndexRef.current;
    if (fromIndex !== null && fromIndex !== index) {
      reorderShots(fromIndex, index);
    }
    dragIndexRef.current = null;
    setDragTargetIndex(null);
  }, [reorderShots]);

  const handleDragEnd = useCallback(() => {
    dragIndexRef.current = null;
    setDragTargetIndex(null);
  }, []);

  if (!storyboardPanelOpen) {
    return (
      <div className="storyboard-bar storyboard-bar-collapsed">
        <button
          type="button"
          className="storyboard-toggle-btn"
          onClick={() => setStoryboardPanelOpen(true)}
        >
          <ChevronUp size={16} strokeWidth={1.8} />
          <span>分镜板</span>
          <span className="storyboard-bar-summary">
            {sortedCameras.length} 镜 · {formatDuration(totalDuration)}
          </span>
        </button>
      </div>
    );
  }

  return (
    <div className="storyboard-bar">
      <div className="storyboard-bar-header">
        <div className="storyboard-bar-title-group">
          <span className="storyboard-bar-title">分镜板</span>
          <span className="storyboard-bar-stats">
            {sortedCameras.length} 镜 · {formatDuration(totalDuration)}
          </span>
          <span className="storyboard-bar-status-summary">
            {SHOT_STATUS_OPTIONS.map((opt) => {
              const count = statusCounts[opt.value] ?? 0;
              if (count === 0) return null;
              return (
                <span key={opt.value} className="storyboard-bar-status-chip" data-status={opt.value}>
                  {opt.icon} {count}
                </span>
              );
            })}
          </span>
        </div>
        <button
          type="button"
          className="storyboard-toggle-btn"
          onClick={toggleStoryboardPanel}
          aria-label="收起分镜板"
        >
          <ChevronDown size={16} strokeWidth={1.8} />
        </button>
      </div>
      <div className="storyboard-bar-content">
        {sortedCameras.length === 0 ? (
          <div className="storyboard-bar-empty">暂无机位，请先添加摄像机</div>
        ) : (
          sortedCameras.map((camera, index) => (
            <ShotCard
              key={camera.id}
              camera={camera}
              index={index}
              isActive={camera.id === activeCameraId}
              onSelect={() => handleSelectCamera(camera.id)}
              onDragStart={handleDragStart(index)}
              onDragOver={handleDragOver(index)}
              onDrop={handleDrop(index)}
              onDragEnd={handleDragEnd}
              isDragTarget={dragTargetIndex === index}
            />
          ))
        )}
      </div>
    </div>
  );
}
