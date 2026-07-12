export type NodeType = 'character' | 'scene' | 'script' | 'storyboard' | 'image' | 'video' | 'audio' | 'group';
export type NodeStatus = 'pending' | 'processing' | 'success' | 'failed';
export type EdgeType = 'default' | 'sequence' | 'reference' | 'association';

export interface NodeConfig {
  model?: string;
  aspect_ratio?: string;
  resolution?: string;
  duration?: number;
  style?: string;
  reference_asset_ids?: string[];
  reference_images?: string[];
  reference_video?: string;
  reference_audio?: string;
  negative_prompt?: string;
  seed?: number;
  sound?: boolean;
  watermark?: boolean;
  /** 局部重绘蒙版（PNG data URL，白色区域=重绘区） */
  mask_data_url?: string;
  /** 局部重绘前的原图 URL（用于撤销） */
  previous_result_url?: string;
}

export interface CanvasNode {
  id: string;
  canvas_id: string;
  node_type: NodeType;
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
  status: NodeStatus;
  progress: number;
  prompt?: string;
  style?: string;
  result_url?: string;
  thumbnail_url?: string;
  error_msg?: string;
  config?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface CanvasEdge {
  id: string;
  canvas_id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: EdgeType;
  label?: string;
  config?: Record<string, unknown>;
}

export interface Canvas {
  id: string;
  name: string;
  description?: string;
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  created_at: string;
  updated_at: string;
}

export interface CanvasListItem {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface TaskInfo {
  id: string;
  node_id: string;
  canvas_id: string;
  task_type: string;
  status: string;
  progress: number;
  result?: Record<string, unknown>;
  error?: string;
  retry_count: number;
}

export interface WSMessage {
  type: 'connected' | 'task_update' | 'node_status' | 'ping';
  task_id?: string;
  node_id?: string;
  canvas_id?: string;
  status?: string;
  progress?: number;
  result?: Record<string, unknown>;
  error?: string;
  message?: string;
}

// Agent workflow types
export interface AgentMessage {
  role: 'user' | 'agent' | 'system';
  agent?: string;
  step?: string;
  content: string;
  payload?: Record<string, unknown>;
  ts: number;
}

export interface ShortDramaScript {
  project_title: string;
  genre: string;
  source_prompt: string;
  style_bible?: string;
  color_palette?: string[];
  is_user_script?: boolean;
  raw_script_text?: string;
  episodes: {
    episode_num: number;
    logline: string;
    scenes: {
      scene_id: string;
      location: string;
      time: string;
      characters_involved: string[];
      action_description: string;
      dialogues: { character: string; line: string; emotion: string }[];
    }[];
  }[];
}

export interface ShortDramaCharacter {
  char_id: string;
  name: string;
  role: string;
  visual_anchor: string;
  base_prompt: string;
  negative_prompt?: string;
  style_preset?: string;
}

export interface ShortDramaScene {
  scene_id: string;
  name: string;
  base_prompt: string;
  atmosphere_tags?: string[];
  reference_shots?: string[];
  negative_prompt?: string;
}

export interface ShortDramaAssets {
  characters: ShortDramaCharacter[];
  scenes: ShortDramaScene[];
  character_relations?: { from: string; to: string; relation: string }[];
  props?: { prop_id: string; name: string; base_prompt: string; negative_prompt?: string }[];
}

export interface ShortDramaScreenwriter {
  screenplay: {
    project_title: string;
    total_episodes: number;
    episodes: {
      episode_num: number;
      logline: string;
      scenes: {
        scene_id: string;
        location: string;
        time: string;
        characters_involved: string[];
        action_description: string;
        emotion_intensity?: number;
        dialogues: { character: string; line: string; emotion: string }[];
      }[];
    }[];
  };
}

export interface ShortDramaCharacterData {
  characters: ShortDramaCharacter[];
  character_relations?: { from: string; to: string; relation: string }[];
}

export interface ShortDramaSceneData {
  scenes: ShortDramaScene[];
  props?: { prop_id: string; name: string; base_prompt: string; negative_prompt?: string }[];
}

export interface ShortDramaStoryboardItem {
  storyboard_id: string;
  linked_scene_id: string;
  shot_type: string;
  camera_movement: string;
  composition?: string;
  visual_description: string;
  final_video_prompt: string;
  final_image_prompt?: string;
  linked_char_id: string;
  linked_char_ids?: string[];
  continuity_marker?: string;
  duration_seconds: number;
}

export interface ShortDramaStoryboard {
  storyboards: ShortDramaStoryboardItem[];
}

export interface ShortDramaVideoItem {
  storyboard_id: string;
  status: string;
  video_url?: string;
  thumbnail_url?: string;
  error_reason?: string;
  fix_suggestion?: string;
}

export interface ShortDramaVideos {
  videos: ShortDramaVideoItem[];
  summary: string;
}

export interface LockedAsset extends ShortDramaCharacter, ShortDramaScene {
  type: 'character' | 'scene';
  asset_id?: string;
  asset_file_url?: string;
  asset_prompt?: string;
}

export interface Asset {
  id: string;
  name: string;
  asset_type: 'image' | 'video' | 'audio' | 'character' | 'scene' | 'other';
  canvas_id?: string;
  file_url: string;
  thumbnail_url?: string;
  description?: string;
  tags: string[];
  meta?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface WorkflowOption {
  id: string;
  label: string;
  icon?: string;
  description?: string;
  value: string;
  choices?: string[];
}

export interface AgentSession {
  id: string;
  status: string;
  prompt: string;
  parameter_pending?: boolean;
  global_params?: Record<string, string>;
  // 三阶段大脑状态
  current_stage?: 'planning' | 'asset' | 'production' | 'finished';
  script_outline?: ShortDramaScript;
  full_script?: ShortDramaScreenwriter;
  character_assets?: ShortDramaCharacterData;
  scene_assets?: ShortDramaSceneData;
  storyboard_data?: ShortDramaStoryboard;
  video_plan?: ShortDramaVideos;
  feedback_message?: string;
  user_feedback?: string;
  user_feedback_stage?: string;
  pending_user_feedback?: string;
  retry_count?: number;
  review_target?: string;
  last_error?: string;
  // 兼容旧字段
  script?: ShortDramaScript;
  screenwriter?: ShortDramaScreenwriter;
  character?: ShortDramaCharacterData;
  storyboard?: ShortDramaStoryboard;
  scene?: ShortDramaSceneData;
  videos?: ShortDramaVideos;
  assets?: ShortDramaAssets;
  locked_assets?: LockedAsset[];
  asset_ids?: string[];
  /** #13: 画布关联 ID（用于增量同步） */
  finalized_canvas_id?: string;
  one_click_canvas_id?: string;
  messages: AgentMessage[];
  options?: Record<string, string>;
}

export interface CreditLedgerEntry {
  id: string;
  amount: number;
  balance_after: number;
  reason: string;
  ref_id?: string;
  description?: string;
  created_at: string;
}

export interface CreditEstimate {
  task_type: string;
  cost: number;
  model?: string;
  duration?: number;
  resolution?: string;
}

export interface WorkflowMessage {
  role: string;
  agent: string;
  step: string;
  content: string;
  payload?: Record<string, unknown>;
}

export interface BrainStreamMessage {
  type: string;
  content: string;
  agent?: string;
  agent_meta?: {
    agent_id: string;
    display_name: string;
    icon: string;
    color: string;
    stage: string;
    description?: string;
  };
  decision?: string;
  reasoning?: string;
  skill_id?: string;
  skill_name?: string;
  step?: number;
  total?: number;
  params?: Record<string, string>;
  data?: any;
  error?: string;
  results?: any[];
  short_drama_params?: any;
  // #1 tool-calling 相关字段
  tool_name?: string;
  tool_call?: string;
  skill_plan?: any[];
}
