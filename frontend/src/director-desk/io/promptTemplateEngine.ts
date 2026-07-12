/**
 * AI Prompt Template Engine
 * Resolves {variable} placeholders in user-defined templates
 * using camera cinematic params + scene + character context.
 */
import { getMovementPresetById, type MotionMagnitude } from "../presets/cameraMovementPresets";
import type {
  DirectorCameraShot,
  DirectorObject,
  DirectorProject,
  PromptTemplate,
  SceneSettings,
  ShotDialogue,
} from "../schema/directorProject";
import { focalLengthToFov, fovToFocalLength } from "./cinematicPromptExport";

// ── Template variable context ──

export interface PromptContext {
  shot_type: string;
  focal_length: string;
  aperture: string;
  depth_of_field: string;
  movement: string;
  color_grade: string;
  character_desc: string;
  scene_desc: string;
  dialogue: string;
  action_desc: string;
}

// ── Default template ──

export const DEFAULT_PROMPT_TEMPLATE_ID = "default-cinematic";

export const DEFAULT_PROMPT_TEMPLATE: PromptTemplate = {
  id: DEFAULT_PROMPT_TEMPLATE_ID,
  name: "影视级默认模板",
  isDefault: true,
  template: `{shot_type}, {focal_length} lens, {depth_of_field}, {movement}, {color_grade}, character: {character_desc}, scene: {scene_desc}, {dialogue}, {action_desc}, 35mm cinematic film grain, Kodak 5207`,
};

export const TEMPLATE_VARIABLE_DESCRIPTIONS: { key: string; label: string; description: string }[] = [
  { key: "shot_type", label: "景别", description: "extreme close-up / close-up / medium shot / full shot / wide shot" },
  { key: "focal_length", label: "焦距", description: "如 50mm cinematic lens" },
  { key: "aperture", label: "光圈", description: "如 f/2.8" },
  { key: "depth_of_field", label: "景深", description: "如 shallow depth of field, bokeh background" },
  { key: "movement", label: "运镜", description: "如 slow dolly in, camera moves forward smoothly" },
  { key: "color_grade", label: "滤镜", description: "如 teal and orange color grading" },
  { key: "character_desc", label: "角色描述", description: "角色外貌描述，来自角色卡片" },
  { key: "scene_desc", label: "场景描述", description: "场景环境描述，来自场景卡片" },
  { key: "dialogue", label: "台词", description: "当前镜头的对白文本" },
  { key: "action_desc", label: "动作描述", description: "当前镜头的动作描述" },
];

// ── FOV → shot type inference (mirrors cinematicPromptExport) ──

function inferShotType(fov: number): string {
  if (fov <= 20) return "extreme close-up";
  if (fov <= 35) return "close-up";
  if (fov <= 55) return "medium shot";
  if (fov <= 75) return "full shot";
  return "wide shot";
}

// ── Aperture → DOF description ──

const APERTURE_DOF_MAP: Record<string, string> = {
  "f/1.4": "very shallow depth of field, creamy bokeh",
  "f/1.8": "very shallow depth of field, smooth bokeh",
  "f/2.0": "shallow depth of field, bokeh background",
  "f/2.8": "shallow depth of field",
  "f/4.0": "moderate shallow depth of field",
  "f/5.6": "moderate depth of field",
  "f/8.0": "deep depth of field, most elements in focus",
  "f/11": "deep depth of field, everything in focus",
  "f/16": "very deep depth of field, fully sharp",
};

// ── Color grade descriptions ──

const COLOR_GRADE_MAP: Record<string, string> = {
  teal_orange: "teal and orange color grading, blockbuster look",
  noir: "high contrast black and white, film noir style",
  warm: "warm golden tones, nostalgic feel",
  cool: "cool blue tones, melancholic atmosphere",
  vintage: "vintage film look, faded colors, grainy texture",
  natural: "natural color grading, true to life",
};

// ── Build context from camera + project ──

export function buildPromptContext(
  camera: DirectorCameraShot,
  project: DirectorProject
): PromptContext {
  const shotType = inferShotType(camera.fov);
  const focalLength = camera.cinematic?.focalLength ?? Math.round(fovToFocalLength(camera.fov));
  const aperture = camera.cinematic?.aperture ?? "f/2.8";
  const dof = APERTURE_DOF_MAP[aperture] ?? "shallow depth of field";

  const movementPreset = camera.cinematic?.movementPresetId
    ? getMovementPresetById(camera.cinematic.movementPresetId)
    : undefined;
  const movement = movementPreset?.promptFragment ?? "locked-off static camera with subtle micro-movement";

  const colorGrade = camera.cinematic?.colorGrade ?? "natural";
  const colorGradeDesc = COLOR_GRADE_MAP[colorGrade] ?? COLOR_GRADE_MAP.natural;

  // Character descriptions — collect from visible characters in the scene
  const characters = project.objects.filter((obj) => obj.kind === "character" && obj.visible);
  const characterDesc = characters
    .map((c) => c.promptDescription?.trim())
    .filter(Boolean)
    .join("; ");

  // Scene description
  const sceneDesc = project.scene.promptDescription?.trim() || "unspecified environment";

  // Dialogue from sequence metadata
  const dialogues = camera.sequence?.dialogues ?? [];
  const dialogueText = dialogues
    .filter((d) => d.text.trim())
    .map((d) => `${d.characterName}: "${d.text.trim()}"`)
    .join(" ");

  // Action description
  const actionDesc = camera.sequence?.actionDescription?.trim() || "";

  return {
    shot_type: shotType,
    focal_length: `${focalLength}mm cinematic`,
    aperture,
    depth_of_field: dof,
    movement,
    color_grade: colorGradeDesc,
    character_desc: characterDesc || "unspecified character",
    scene_desc: sceneDesc,
    dialogue: dialogueText,
    action_desc: actionDesc,
  };
}

// ── Resolve template ──

export function resolveTemplate(template: string, ctx: PromptContext): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => {
    const value = ctx[key as keyof PromptContext];
    if (value === undefined || value === "") {
      // Remove the placeholder entirely if the value is empty
      return "";
    }
    return value;
  })
  // Clean up: remove empty segments (caused by empty variables), collapse commas
  .replace(/\s*,\s*,+/g, ", ")
  .replace(/^\s*,\s*/, "")
  .replace(/\s*,\s*$/, "")
  .replace(/\s{2,}/g, " ")
  .trim();
}

// ── Get active template from project ──

export function getActivePromptTemplate(project: DirectorProject): PromptTemplate {
  const templates = project.promptTemplates ?? [];
  const activeId = project.activePromptTemplateId;

  if (activeId) {
    const found = templates.find((t) => t.id === activeId);
    if (found) return found;
  }

  const defaultTpl = templates.find((t) => t.isDefault);
  if (defaultTpl) return defaultTpl;

  return DEFAULT_PROMPT_TEMPLATE;
}

// ── Generate prompt using template engine ──

export function generatePromptWithTemplate(
  camera: DirectorCameraShot,
  project: DirectorProject
): string {
  const template = getActivePromptTemplate(project);
  const ctx = buildPromptContext(camera, project);
  return resolveTemplate(template.template, ctx);
}

// ── Get motion magnitude (re-exported helper) ──

export function getMotionMagnitudeForCamera(camera: DirectorCameraShot): MotionMagnitude {
  if (camera.cinematic?.movementPresetId) {
    const preset = getMovementPresetById(camera.cinematic.movementPresetId);
    if (preset) return preset.motionMagnitude;
  }
  return "low";
}

// ── Format dialogue for prompt ──

export function formatDialogueForPrompt(dialogues: ShotDialogue[]): string {
  return dialogues
    .filter((d) => d.text.trim())
    .map((d) => `${d.characterName}: "${d.text.trim()}"`)
    .join(" ");
}

// ── Collect character descriptions ──

export function collectCharacterDescriptions(objects: DirectorObject[]): string {
  return objects
    .filter((o) => o.kind === "character" && o.visible && o.promptDescription?.trim())
    .map((o) => `${o.name}: ${o.promptDescription!.trim()}`)
    .join("; ");
}

// ── Get scene description ──

export function getSceneDescription(scene: SceneSettings): string {
  return scene.promptDescription?.trim() || "";
}
