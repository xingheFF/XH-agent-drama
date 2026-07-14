import { useEffect, useRef, useState } from 'react';
import {
  X, Search, Image as ImageIcon, Film, Music, User, MapPin, Package, Link2, Check, Trash2,
  Globe, Users, Plus, LogIn, Shield, User as UserIcon, ChevronDown, Upload,
} from 'lucide-react';
import { useEditorStore } from '@/store/editor';
import { useAuthStore } from '@/store/auth';
import { api } from '@/utils/api';
import type { Asset, Team, TeamMember } from '@/types';

const TYPE_OPTIONS: { value: string; label: string; icon: React.ReactNode }[] = [
  { value: 'all', label: '全部', icon: <Package size={14} /> },
  { value: 'character', label: '角色', icon: <User size={14} /> },
  { value: 'scene', label: '场景', icon: <MapPin size={14} /> },
  { value: 'image', label: '图片', icon: <ImageIcon size={14} /> },
  { value: 'video', label: '视频', icon: <Film size={14} /> },
  { value: 'audio', label: '音频', icon: <Music size={14} /> },
];

const ROLE_LABELS: Record<string, string> = {
  owner: '所有者',
  admin: '管理员',
  member: '成员',
};

const ROLE_BADGE_CLASS: Record<string, string> = {
  owner: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  admin: 'bg-accent/20 text-accent border-accent/30',
  member: 'bg-theme-input text-theme-sub border-panel-border',
};

export function AssetPanel() {
  const showAssetPanel = useEditorStore((s) => s.showAssetPanel);
  const toggleAssetPanel = useEditorStore((s) => s.toggleAssetPanel);
  const canvas = useEditorStore((s) => s.canvas);
  const applyAssetToSelectedNode = useEditorStore((s) => s.applyAssetToSelectedNode);
  const currentUser = useAuthStore((s) => s.user);

  const [assets, setAssets] = useState<Asset[]>([]);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [appliedAssetId, setAppliedAssetId] = useState<string | null>(null);

  // 资产范围：project=当前项目, team=指定团队, all=全部项目+团队
  const [scope, setScope] = useState<'project' | 'team' | 'all'>('project');
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);

  // 团队管理弹窗
  const [teamModalOpen, setTeamModalOpen] = useState(false);
  const [teamTab, setTeamTab] = useState<'list' | 'create' | 'join' | 'detail'>('list');
  const [newTeamName, setNewTeamName] = useState('');
  const [joinCode, setJoinCode] = useState('');
  const [teamActionLoading, setTeamActionLoading] = useState(false);
  const [detailTeamId, setDetailTeamId] = useState<string | null>(null);
  const [detailTeam, setDetailTeam] = useState<Team | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // 二次确认删除：记录正在确认删除的资产 ID
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadTargetTeamId, setUploadTargetTeamId] = useState<string | null>(null);

  // 加载团队列表
  useEffect(() => {
    if (!showAssetPanel) return;
    let cancelled = false;
    api.listTeams()
      .then((res) => {
        if (!cancelled) setTeams(res.teams || []);
      })
      .catch(() => {
        if (!cancelled) setTeams([]);
      });
    return () => { cancelled = true; };
  }, [showAssetPanel, teamModalOpen]);

  // 默认选中第一个团队（当切换到团队范围且未选择时）
  useEffect(() => {
    if (scope === 'team' && !selectedTeamId && teams.length > 0) {
      setSelectedTeamId(teams[0].id);
    }
  }, [scope, teams, selectedTeamId]);

  // 加载资产列表
  useEffect(() => {
    if (!showAssetPanel) return;
    let cancelled = false;
    setLoading(true);
    const canvasId = scope === 'project' ? canvas?.id : undefined;
    const teamId = scope === 'team' ? selectedTeamId || undefined : undefined;
    api.listAssets(filter === 'all' ? undefined : filter, query || undefined, canvasId, teamId)
      .then((data) => {
        if (!cancelled) setAssets(data || []);
      })
      .catch(() => {
        if (!cancelled) setAssets([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [showAssetPanel, filter, query, canvas?.id, scope, selectedTeamId]);

  // 加载团队详情（含成员）
  useEffect(() => {
    if (!teamModalOpen || !detailTeamId) {
      setDetailTeam(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    api.getTeam(detailTeamId)
      .then((team) => {
        if (!cancelled) setDetailTeam(team);
      })
      .catch(() => {
        if (!cancelled) setDetailTeam(null);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => { cancelled = true; };
  }, [teamModalOpen, detailTeamId]);

  if (!showAssetPanel) return null;

  const currentTeam = teams.find((t) => t.id === selectedTeamId);

  const handleCopyPrompt = (prompt: string) => {
    navigator.clipboard.writeText(prompt).catch(() => {});
  };

  const handleDeleteAsset = async (assetId: string) => {
    setDeleting(true);
    try {
      await api.deleteAsset(assetId);
      setAssets((prev) => prev.filter((a) => a.id !== assetId));
      if (selectedId === assetId) setSelectedId(null);
      setConfirmDeleteId(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : '删除失败');
    } finally {
      setDeleting(false);
    }
  };

  const renderDeleteButton = (assetId: string) => {
    const isConfirming = confirmDeleteId === assetId;
    return (
      <button
        className={`flex items-center justify-center gap-1 py-1 text-[10px] rounded-lg transition-colors ${
          isConfirming
            ? 'bg-error/20 text-error border border-error/30 hover:bg-error/30'
            : 'bg-theme-input text-theme-sub border border-panel-border hover:text-error hover:border-error/30'
        }`}
        onClick={(e) => {
          e.stopPropagation();
          if (isConfirming) {
            handleDeleteAsset(assetId);
          } else {
            setConfirmDeleteId(assetId);
            setTimeout(() => {
              setConfirmDeleteId((prev) => (prev === assetId ? null : prev));
            }, 3000);
          }
        }}
        disabled={deleting && isConfirming}
        title={isConfirming ? '再次点击确认删除' : '删除资产'}
      >
        {deleting && isConfirming ? (
          <><Check size={10} className="animate-pulse" /> 删除中...</>
        ) : isConfirming ? (
          <><Trash2 size={10} /> 确认删除？</>
        ) : (
          <><Trash2 size={10} /> 删除</>
        )}
      </button>
    );
  };

  const handleAssetDragStart = (e: React.DragEvent, asset: Asset) => {
    e.dataTransfer.setData('application/asset', JSON.stringify(asset));
    e.dataTransfer.effectAllowed = 'copy';
  };

  const refreshAssets = () => {
    const canvasId = scope === 'project' ? canvas?.id : undefined;
    const teamId = scope === 'team' ? selectedTeamId || undefined : undefined;
    setLoading(true);
    api.listAssets(filter === 'all' ? undefined : filter, query || undefined, canvasId, teamId)
      .then((data) => setAssets(data || []))
      .catch(() => setAssets([]))
      .finally(() => setLoading(false));
  };

  const handleUploadClick = () => {
    if (scope === 'team' && selectedTeamId) {
      setUploadTargetTeamId(selectedTeamId);
    } else {
      setUploadTargetTeamId(null);
    }
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await api.uploadAsset(file, {
        name: file.name,
        assetType: 'image',
        canvasId: scope === 'project' ? canvas?.id : undefined,
        teamId: uploadTargetTeamId || undefined,
      });
      refreshAssets();
    } catch (err) {
      alert(err instanceof Error ? err.message : '上传失败');
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // 团队管理操作
  const handleCreateTeam = async () => {
    if (!newTeamName.trim()) return;
    setTeamActionLoading(true);
    try {
      const team = await api.createTeam(newTeamName.trim());
      setTeams((prev) => [team, ...prev]);
      setSelectedTeamId(team.id);
      setScope('team');
      setNewTeamName('');
      setTeamTab('list');
    } catch (err) {
      alert(err instanceof Error ? err.message : '创建失败');
    } finally {
      setTeamActionLoading(false);
    }
  };

  const handleJoinTeam = async () => {
    if (!joinCode.trim()) return;
    setTeamActionLoading(true);
    try {
      const res = await api.joinTeam(joinCode.trim().toUpperCase());
      setJoinCode('');
      setTeamTab('list');
      api.listTeams().then((r) => setTeams(r.teams || [])).catch(() => {});
      alert(`成功加入团队「${res.team_name}」`);
    } catch (err) {
      alert(err instanceof Error ? err.message : '加入失败');
    } finally {
      setTeamActionLoading(false);
    }
  };

  const handleDeleteTeam = async (teamId: string) => {
    if (!confirm('确定要解散该团队吗？团队内所有共享画布和资产将不再可用。')) return;
    try {
      await api.deleteTeam(teamId);
      setTeams((prev) => prev.filter((t) => t.id !== teamId));
      if (selectedTeamId === teamId) setSelectedTeamId(null);
      if (detailTeamId === teamId) setDetailTeamId(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : '解散失败');
    }
  };

  const handleLeaveTeam = async (teamId: string) => {
    if (!confirm('确定要退出该团队吗？')) return;
    try {
      await api.removeTeamMember(teamId, currentUser?.id || '');
      setTeams((prev) => prev.filter((t) => t.id !== teamId));
      if (selectedTeamId === teamId) setSelectedTeamId(null);
      if (detailTeamId === teamId) setDetailTeamId(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : '退出失败');
    }
  };

  const handleUpdateMemberRole = async (teamId: string, userId: string, role: string) => {
    try {
      await api.updateTeamMemberRole(teamId, userId, role);
      if (detailTeamId === teamId) {
        api.getTeam(teamId).then((t) => setDetailTeam(t)).catch(() => {});
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '修改失败');
    }
  };

  const handleRemoveMember = async (teamId: string, userId: string) => {
    if (!confirm('确定要移除该成员吗？')) return;
    try {
      await api.removeTeamMember(teamId, userId);
      if (detailTeamId === teamId) {
        api.getTeam(teamId).then((t) => setDetailTeam(t)).catch(() => {});
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : '移除失败');
    }
  };

  const isTeamAdminOrOwner = (team?: Team | null) => {
    if (!team || !currentUser) return false;
    if (team.owner_id === currentUser.id) return true;
    return team.members?.some((m) => m.user_id === currentUser.id && (m.role === 'admin' || m.role === 'owner')) || false;
  };

  const renderScopeLabel = () => {
    if (scope === 'project') return canvas ? `当前项目：${canvas.name}` : '当前项目';
    if (scope === 'team') return currentTeam ? `团队：${currentTeam.name}` : '团队资产';
    return '全部项目+团队';
  };

  const renderAssetSourceBadge = (asset: Asset) => {
    if (asset.team_id) {
      const teamName = teams.find((t) => t.id === asset.team_id)?.name || '团队';
      return (
        <span className="text-[9px] px-1.5 py-0.5 rounded bg-accent/10 text-accent border border-accent/20 shrink-0" title={`来自团队 ${teamName}`}>
          团队
        </span>
      );
    }
    if (asset.canvas_id && asset.canvas_id !== canvas?.id) {
      return (
        <span className="text-[9px] px-1.5 py-0.5 rounded bg-theme-input text-theme-sub border border-panel-border shrink-0" title="来自其他项目">
          跨项目
        </span>
      );
    }
    return null;
  };

  return (
    <div className="fixed right-4 top-20 bottom-6 w-80 glass rounded-2xl border border-panel-border shadow-soft-lg z-40 flex flex-col">
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={handleFileChange}
      />

      <div className="h-12 border-b border-panel-border flex items-center justify-between px-4 shrink-0 bg-panel-bg">
        <h2 className="text-sm font-bold text-theme-main flex items-center gap-2">
          <Package size={16} className="text-accent" />
          资产库
        </h2>
        <div className="flex items-center gap-1">
          <button
            className="btn-ghost p-1.5 rounded-xl"
            onClick={() => { setTeamModalOpen(true); setTeamTab('list'); setDetailTeamId(null); }}
            title="团队管理"
          >
            <Users size={16} />
          </button>
          <button className="btn-ghost p-1.5 rounded-xl" onClick={toggleAssetPanel} title="关闭">
            <X size={16} />
          </button>
        </div>
      </div>

      <div className="p-3 border-b border-panel-border space-y-2 shrink-0">
        {/* 范围切换 */}
        <div className="flex flex-wrap gap-1">
          <button
            onClick={() => setScope('project')}
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] border transition-colors ${
              scope === 'project'
                ? 'bg-accent/20 border-accent text-accent'
                : 'bg-canvas-bg border-panel-border text-theme-sub hover:border-panel-border/80'
            }`}
          >
            <Package size={11} /> 本项目
          </button>
          <button
            onClick={() => setScope('team')}
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] border transition-colors ${
              scope === 'team'
                ? 'bg-accent/20 border-accent text-accent'
                : 'bg-canvas-bg border-panel-border text-theme-sub hover:border-panel-border/80'
            }`}
          >
            <Users size={11} /> 团队
          </button>
          <button
            onClick={() => setScope('all')}
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] border transition-colors ${
              scope === 'all'
                ? 'bg-accent/20 border-accent text-accent'
                : 'bg-canvas-bg border-panel-border text-theme-sub hover:border-panel-border/80'
            }`}
          >
            <Globe size={11} /> 全部
          </button>
        </div>

        {/* 团队选择器 + 上传 */}
        {scope === 'team' && (
          <div className="flex items-center gap-2">
            <div className="relative flex-1 min-w-0">
              <select
                value={selectedTeamId || ''}
                onChange={(e) => setSelectedTeamId(e.target.value || null)}
                className="input-field w-full appearance-none pr-7 text-xs truncate"
              >
                {teams.length === 0 && <option value="">暂无团队</option>}
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-theme-hint pointer-events-none" />
            </div>
            <button
              onClick={handleUploadClick}
              disabled={!selectedTeamId}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-[10px] btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              title="上传团队资产"
            >
              <Upload size={11} /> 上传
            </button>
          </div>
        )}

        {scope === 'project' && (
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-theme-sub truncate">{canvas ? canvas.name : '未选择项目'}</span>
            <button
              onClick={handleUploadClick}
              disabled={!canvas}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-[10px] btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              title="上传项目资产"
            >
              <Upload size={11} /> 上传
            </button>
          </div>
        )}

        {scope === 'all' && (
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-theme-sub">全部项目与团队资产</span>
            <button
              onClick={handleUploadClick}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-[10px] btn-primary"
              title="上传到当前项目"
            >
              <Upload size={11} /> 上传
            </button>
          </div>
        )}

        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-theme-hint" />
          <input
            className="input-field pl-8"
            placeholder="搜索资产..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-1">
          {TYPE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setFilter(opt.value)}
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] border transition-colors ${
                filter === opt.value
                  ? 'bg-accent/20 border-accent text-accent'
                  : 'bg-canvas-bg border-panel-border text-theme-sub hover:border-panel-border/80'
              }`}
            >
              {opt.icon}
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {loading ? (
          <div className="text-center text-theme-hint text-sm py-8">加载中...</div>
        ) : assets.length === 0 ? (
          <div className="text-center text-theme-hint text-sm py-8">
            <Package size={32} className="mx-auto mb-2 opacity-30" />
            暂无资产
          </div>
        ) : filter === 'character' ? (
          assets.map((asset) => {
            const meta = asset.meta || {};
            const features = (meta.immutable_features as string[]) || [];
            const charId = meta.char_id as string | undefined;
            const basePrompt = meta.base_prompt as string | undefined;
            return (
              <div
                key={asset.id}
                draggable
                onDragStart={(e) => handleAssetDragStart(e, asset)}
                onClick={() => setSelectedId(asset.id === selectedId ? null : asset.id)}
                className={`p-3 rounded-xl cursor-pointer transition-all shadow-soft ${
                  selectedId === asset.id
                    ? 'border-2 border-accent bg-accent/10'
                    : 'border border-panel-border bg-panel-bg hover:border-accent/30'
                }`}
              >
                <div className="flex gap-3">
                  <div className="w-24 h-32 rounded-lg bg-canvas-bg flex items-center justify-center shrink-0 overflow-hidden">
                    {asset.thumbnail_url || asset.file_url ? (
                      <img
                        src={asset.thumbnail_url || asset.file_url}
                        alt={asset.name}
                        draggable={false}
                        className="w-full h-full object-cover"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                      />
                    ) : (
                      <User size={20} className="text-theme-hint" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-bold text-theme-main truncate">{asset.name}</div>
                    {charId && (
                      <div className="text-[10px] text-accent font-mono mt-0.5">ID: {charId}</div>
                    )}
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {renderAssetSourceBadge(asset)}
                    </div>
                    {features.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {features.map((f, i) => (
                          <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-accent/10 text-accent border border-accent/20">
                            {f}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                {selectedId === asset.id && (
                  <div className="mt-2 pt-2 border-t border-panel-border/50 space-y-2">
                    {basePrompt && (
                      <div className="text-[10px] text-theme-hint font-mono bg-canvas-bg rounded p-1.5 line-clamp-4">
                        {basePrompt}
                      </div>
                    )}
                    <button
                      className={`w-full text-center py-1.5 text-[10px] rounded-lg flex items-center justify-center gap-1.5 transition-colors ${
                        appliedAssetId === asset.id
                          ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                          : 'btn-primary'
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        applyAssetToSelectedNode({
                          id: asset.id,
                          file_url: asset.file_url,
                          asset_type: asset.asset_type,
                          meta: asset.meta,
                          name: asset.name,
                        });
                        setAppliedAssetId(asset.id);
                        setTimeout(() => setAppliedAssetId(null), 2000);
                      }}
                    >
                      {appliedAssetId === asset.id ? (
                        <><Check size={12} /> 已应用</>
                      ) : (
                        <><Link2 size={12} /> 应用到选中分镜</>
                      )}
                    </button>
                    <div className="flex gap-2">
                      <a
                        href={asset.file_url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex-1 text-center btn-secondary py-1 text-[10px]"
                        onClick={(e) => e.stopPropagation()}
                      >
                        查看原文件
                      </a>
                      {renderDeleteButton(asset.id)}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        ) : (
          assets.map((asset) => (
            <div
              key={asset.id}
              draggable
              onDragStart={(e) => handleAssetDragStart(e, asset)}
              onClick={() => setSelectedId(asset.id === selectedId ? null : asset.id)}
              className={`p-2.5 rounded-xl cursor-pointer transition-all shadow-soft ${
                selectedId === asset.id
                  ? 'border-2 border-accent bg-accent/10'
                  : 'border border-panel-border bg-panel-bg hover:border-accent/30 hover:-translate-y-0.5'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <div className="w-12 h-12 rounded-lg bg-canvas-bg flex items-center justify-center shrink-0 overflow-hidden">
                  {asset.file_url?.match(/\.(jpg|jpeg|png|webp|gif|svg)(\?|$)/i) ? (
                    <img
                      src={asset.thumbnail_url || asset.file_url}
                      alt=""
                      draggable={false}
                      className="w-full h-full object-cover"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                  ) : (
                    TYPE_OPTIONS.find((t) => t.value === asset.asset_type)?.icon || <Package size={16} />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-theme-main truncate">{asset.name}</div>
                  <div className="text-[10px] text-theme-hint flex items-center gap-1 flex-wrap">
                    <span className="px-1 rounded bg-canvas-bg">{asset.asset_type}</span>
                    <span className="truncate">{asset.id.slice(0, 8)}</span>
                    {renderAssetSourceBadge(asset)}
                  </div>
                </div>
              </div>

              {selectedId === asset.id && (
                <div className="mt-2 pt-2 border-t border-panel-border/50 space-y-2">
                  {asset.description && (
                    <div className="text-[10px] text-theme-sub line-clamp-3">{asset.description}</div>
                  )}
                  {asset.meta?.prompt && (
                    <div className="text-[10px] text-theme-hint font-mono bg-canvas-bg rounded p-1.5 line-clamp-4">
                      {asset.meta.prompt as string}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <a
                      href={asset.file_url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex-1 text-center btn-secondary py-1 text-[10px]"
                      onClick={(e) => e.stopPropagation()}
                    >
                      查看原文件
                    </a>
                    {asset.meta?.prompt && (
                      <button
                        className="flex-1 btn-secondary py-1 text-[10px]"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCopyPrompt(asset.meta?.prompt as string);
                        }}
                      >
                        复制Prompt
                      </button>
                    )}
                    {renderDeleteButton(asset.id)}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <div className="p-3 border-t border-panel-border text-[10px] text-theme-hint shrink-0">
        共 {assets.length} 个资产 · {renderScopeLabel()}
      </div>

      {/* 团队管理弹窗 */}
      {teamModalOpen && (
        <div className="absolute inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-md glass rounded-2xl border border-panel-border shadow-soft-lg flex flex-col max-h-[80vh]">
            <div className="h-12 border-b border-panel-border flex items-center justify-between px-4 shrink-0">
              <h3 className="text-sm font-bold text-theme-main flex items-center gap-2">
                <Users size={16} className="text-accent" />
                团队管理
              </h3>
              <button className="btn-ghost p-1.5 rounded-xl" onClick={() => setTeamModalOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <div className="flex border-b border-panel-border shrink-0">
              {[
                { key: 'list', label: '我的团队', icon: <Users size={11} /> },
                { key: 'create', label: '创建团队', icon: <Plus size={11} /> },
                { key: 'join', label: '加入团队', icon: <LogIn size={11} /> },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => { setTeamTab(tab.key as 'list' | 'create' | 'join'); setDetailTeamId(null); }}
                  className={`flex-1 flex items-center justify-center gap-1 py-2 text-[11px] font-semibold transition-colors ${
                    teamTab === tab.key
                      ? 'text-accent border-b-2 border-accent'
                      : 'text-theme-sub hover:text-theme-main'
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="p-4 overflow-y-auto flex-1 min-h-0">
              {teamTab === 'list' && (
                <div className="space-y-2">
                  {teams.length === 0 ? (
                    <div className="text-center text-theme-hint text-sm py-8">
                      <Users size={32} className="mx-auto mb-2 opacity-30" />
                      你还没有加入任何团队
                    </div>
                  ) : (
                    teams.map((team) => {
                      const isOwner = team.owner_id === currentUser?.id;
                      return (
                        <div
                          key={team.id}
                          className="p-3 rounded-xl border border-panel-border bg-panel-bg/50 hover:border-accent/30 transition-colors"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="min-w-0">
                              <div className="text-sm font-bold text-theme-main truncate">{team.name}</div>
                              <div className="text-[10px] text-theme-hint font-mono mt-0.5">团号：{team.team_code}</div>
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              <button
                                onClick={() => { setDetailTeamId(team.id); setTeamTab('detail'); }}
                                className="px-2 py-1 rounded-lg text-[10px] btn-secondary"
                              >
                                详情
                              </button>
                              {isOwner ? (
                                <button
                                  onClick={() => handleDeleteTeam(team.id)}
                                  className="px-2 py-1 rounded-lg text-[10px] bg-error/10 text-error border border-error/20 hover:bg-error/20"
                                >
                                  解散
                                </button>
                              ) : (
                                <button
                                  onClick={() => handleLeaveTeam(team.id)}
                                  className="px-2 py-1 rounded-lg text-[10px] bg-theme-input text-theme-sub border border-panel-border hover:text-error hover:border-error/30"
                                >
                                  退出
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {teamTab === 'create' && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-[10px] text-theme-sub mb-1">团队名称</label>
                    <input
                      className="input-field w-full"
                      placeholder="输入团队名称"
                      value={newTeamName}
                      onChange={(e) => setNewTeamName(e.target.value)}
                      maxLength={50}
                    />
                  </div>
                  <button
                    onClick={handleCreateTeam}
                    disabled={teamActionLoading || !newTeamName.trim()}
                    className="w-full btn-primary py-2 text-xs disabled:opacity-50"
                  >
                    {teamActionLoading ? '创建中...' : '创建团队'}
                  </button>
                  <p className="text-[10px] text-theme-hint leading-relaxed">
                    创建后会自动生成 6 位团号，其他用户输入团号即可加入。
                  </p>
                </div>
              )}

              {teamTab === 'join' && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-[10px] text-theme-sub mb-1">团号</label>
                    <input
                      className="input-field w-full uppercase"
                      placeholder="输入 6 位团号"
                      value={joinCode}
                      onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                      maxLength={16}
                    />
                  </div>
                  <button
                    onClick={handleJoinTeam}
                    disabled={teamActionLoading || !joinCode.trim()}
                    className="w-full btn-primary py-2 text-xs disabled:opacity-50"
                  >
                    {teamActionLoading ? '加入中...' : '加入团队'}
                  </button>
                  <p className="text-[10px] text-theme-hint leading-relaxed">
                    输入其他团队提供的团号，即可加入并共享该团队的画布与资产。
                  </p>
                </div>
              )}

              {teamTab === 'detail' && detailTeamId && (
                <div className="space-y-3">
                  <button
                    onClick={() => setTeamTab('list')}
                    className="text-[10px] text-theme-sub hover:text-accent flex items-center gap-1"
                  >
                    ← 返回团队列表
                  </button>
                  {detailLoading ? (
                    <div className="text-center text-theme-hint text-sm py-8">加载中...</div>
                  ) : detailTeam ? (
                    <>
                      <div className="p-3 rounded-xl border border-panel-border bg-panel-bg/50">
                        <div className="text-sm font-bold text-theme-main">{detailTeam.name}</div>
                        <div className="text-[10px] text-theme-hint font-mono mt-0.5">团号：{detailTeam.team_code}</div>
                      </div>
                      <div className="space-y-2">
                        <div className="text-[11px] font-semibold text-theme-sub">成员列表</div>
                        {(detailTeam.members || []).map((member: TeamMember) => {
                          const isMe = member.user_id === currentUser?.id;
                          const canManage = isTeamAdminOrOwner(detailTeam) && !isMe && member.role !== 'owner';
                          return (
                            <div
                              key={member.id}
                              className="flex items-center justify-between p-2 rounded-lg border border-panel-border bg-panel-bg/30"
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                <UserIcon size={14} className="text-theme-hint shrink-0" />
                                <span className="text-xs text-theme-main truncate">
                                  {member.username || member.user_id.slice(0, 8)}
                                  {isMe ? '（我）' : ''}
                                </span>
                              </div>
                              <div className="flex items-center gap-1 shrink-0">
                                <span className={`text-[9px] px-1.5 py-0.5 rounded border ${ROLE_BADGE_CLASS[member.role]}`}>
                                  {ROLE_LABELS[member.role]}
                                </span>
                                {canManage && (
                                  <>
                                    {member.role === 'member' ? (
                                      <button
                                        onClick={() => handleUpdateMemberRole(detailTeam.id, member.user_id, 'admin')}
                                        className="p-1 rounded hover:bg-accent/10 text-theme-sub hover:text-accent"
                                        title="设为管理员"
                                      >
                                        <Shield size={12} />
                                      </button>
                                    ) : (
                                      <button
                                        onClick={() => handleUpdateMemberRole(detailTeam.id, member.user_id, 'member')}
                                        className="p-1 rounded hover:bg-accent/10 text-theme-sub hover:text-accent"
                                        title="降为成员"
                                      >
                                        <UserIcon size={12} />
                                      </button>
                                    )}
                                    <button
                                      onClick={() => handleRemoveMember(detailTeam.id, member.user_id)}
                                      className="p-1 rounded hover:bg-error/10 text-theme-sub hover:text-error"
                                      title="移除成员"
                                    >
                                      <Trash2 size={12} />
                                    </button>
                                  </>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  ) : (
                    <div className="text-center text-theme-hint text-sm py-8">加载失败</div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
