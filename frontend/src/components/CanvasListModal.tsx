import { useState, useEffect } from 'react';
import { X, Plus, Folder, Trash2, Users } from 'lucide-react';
import { useEditorStore } from '@/store/editor';
import { api } from '@/utils/api';
import type { Team } from '@/types';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export function CanvasListModal({ isOpen, onClose }: Props) {
  const { canvasList, loadCanvasList, loadCanvas, createNewCanvas, deleteCanvas } = useEditorStore();
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [createTeamId, setCreateTeamId] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadCanvasList();
      setNewName('');
      setDeletingId(null);
      setCreateTeamId(null);
      api.listTeams()
        .then((res) => setTeams(res.teams || []))
        .catch(() => setTeams([]));
    }
  }, [isOpen, loadCanvasList]);

  if (!isOpen) return null;

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await createNewCanvas(newName.trim(), createTeamId || undefined);
      onClose();
    } finally {
      setCreating(false);
    }
  };

  const handleSelect = async (id: string) => {
    await loadCanvas(id);
    onClose();
  };

  const handleDelete = async (id: string, name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteError(null);
    if (!window.confirm(`确定删除项目「${name}」吗？删除后无法恢复。`)) return;
    setDeletingId(id);
    try {
      await deleteCanvas(id);
    } catch (err: any) {
      setDeleteError(err.message || '删除失败，请重试');
    } finally {
      setDeletingId(null);
    }
  };

  const getTeamName = (teamId?: string) => {
    if (!teamId) return null;
    return teams.find((t) => t.id === teamId)?.name || '团队项目';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="glass rounded-3xl border border-panel-border shadow-soft-lg w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-panel-border bg-panel-bg">
          <h2 className="text-lg font-semibold text-theme-main">全部项目</h2>
          <button className="btn-ghost p-1.5 rounded-xl" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="p-4 space-y-3 max-h-[70vh] overflow-y-auto">
          <div className="space-y-2">
            <div className="flex gap-2">
              <input
                className="input-field flex-1"
                placeholder="新建画布名称..."
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              />
              <button className="btn-primary rounded-xl" onClick={handleCreate} disabled={!newName.trim() || creating}>
                <Plus size={16} />
                <span>新建</span>
              </button>
            </div>
            {teams.length > 0 && (
              <div className="flex items-center gap-2">
                <Users size={12} className="text-theme-hint" />
                <select
                  value={createTeamId || ''}
                  onChange={(e) => setCreateTeamId(e.target.value || null)}
                  className="input-field flex-1 text-xs appearance-none"
                >
                  <option value="">个人项目</option>
                  {teams.map((t) => (
                    <option key={t.id} value={t.id}>团队：{t.name}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="h-px bg-panel-border" />

          {deleteError && (
            <div className="text-sm text-error bg-error/10 px-3 py-2 rounded-lg">
              {deleteError}
            </div>
          )}

          {canvasList.length === 0 ? (
            <div className="text-center text-theme-sub py-8 text-sm">
              <Folder size={32} className="mx-auto mb-2 opacity-30" />
              还没有项目，创建一个开始吧
            </div>
          ) : (
            <div className="space-y-1.5">
              {canvasList.map((c) => {
                const teamName = getTeamName(c.team_id);
                return (
                  <div
                    key={c.id}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-panel-hover transition-colors text-left group cursor-pointer"
                    onClick={() => handleSelect(c.id)}
                  >
                    <div className="w-9 h-9 rounded-xl bg-accent/10 flex items-center justify-center text-accent">
                      <Folder size={16} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-theme-main truncate">{c.name}</div>
                      <div className="text-[10px] text-theme-sub flex items-center gap-1 flex-wrap">
                        <span>{c.id.slice(0, 8)}</span>
                        {teamName && (
                          <span className="text-[9px] px-1 py-0.5 rounded bg-accent/10 text-accent border border-accent/20">
                            {teamName}
                          </span>
                        )}
                      </div>
                    </div>
                    <button
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-theme-sub hover:text-error hover:bg-error/10 transition-all"
                      title="删除项目"
                      disabled={deletingId === c.id}
                      onClick={(e) => handleDelete(c.id, c.name, e)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
