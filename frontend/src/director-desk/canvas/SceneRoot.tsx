import { Html, Line, TransformControls, type TransformControlsProps } from "@react-three/drei";
import { useLoader, type ThreeEvent } from "@react-three/fiber";
import { Suspense, useCallback, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Box3, Matrix4, Quaternion, Vector3, type Group, type Object3D } from "three";
import type { TransformControls as TransformControlsImpl } from "three-stdlib";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import type {
  DirectorAssetRef,
  DirectorCameraShot,
  DirectorObject,
  GeometryPrimitiveType,
} from "../schema/directorProject";
import {
  VIEWPORT_CAMERA_ASPECT,
  VIEWPORT_CAMERA_FRUSTUM_DEPTH,
  VIEWPORT_CAMERA_FRUSTUM_FRAME_WIDTH,
  VIEWPORT_CAMERA_VISUAL_SCALE,
} from "../schema/cameraGeometry";
import { VIEWPORT_OBJECT_LABEL_VERTICAL_GAP } from "../schema/viewportLabels";
import type { TransformMode } from "../store/directorStore";
import { useDirectorStore } from "../store/directorStore";
import { CharacterModel } from "../runtime/CharacterModel";
import { getGroundedLabelY } from "../runtime/mannequin/bodyTypes";
import { getUE4GroundedLabelY } from "../runtime/ue4Mannequin/ue4MannequinRig";
import { getEffectiveGroundOpacity } from "./panoramaMath";
import { getCrowdAnchorTransform } from "../store/directorStore";

export { getEffectiveGroundOpacity, getPanoramaRotationRadians } from "./panoramaMath";

const VIEWPORT_CAMERA_LINE = "#A9D8FF";
const VIEWPORT_CAMERA_LINE_OPACITY = 0.92;
const VIEWPORT_CAMERA_HIT_PADDING = 0.06;
const VIEWPORT_CAMERA_FORWARD = new Vector3(0, 0, 1);
const VIEWPORT_CAMERA_WORLD_UP = new Vector3(0, 1, 0);
const HIDE_FROM_VIEWPORT_CAPTURE_KEY = "hideFromViewportCapture";
const VIEWPORT_CAMERA_BODY_CENTER: CameraWirePoint = [0, 0, -0.52 * VIEWPORT_CAMERA_VISUAL_SCALE];
const VIEWPORT_CAMERA_BODY_SIZE: CameraWirePoint = [
  0.4 * VIEWPORT_CAMERA_VISUAL_SCALE,
  0.4 * VIEWPORT_CAMERA_VISUAL_SCALE,
  1 * VIEWPORT_CAMERA_VISUAL_SCALE,
];
const VIEWPORT_CAMERA_BODY_FRONT_Z = VIEWPORT_CAMERA_BODY_CENTER[2] + VIEWPORT_CAMERA_BODY_SIZE[2] / 2;
const VIEWPORT_CAMERA_LENS_TIP: CameraWirePoint = [0, 0, 0.2 * VIEWPORT_CAMERA_VISUAL_SCALE];
const ROLE_LABEL_DISTANCE_FACTOR = 3;
const IMPORTED_MODEL_TARGET_MAX_SIZE = 2;
type CameraWirePoint = [number, number, number];
type CameraWirePointLine = CameraWirePoint[];
type CameraWirePart = "body" | "lens" | "reel";
type CameraWireLine = {
  part: CameraWirePart;
  points: CameraWirePointLine;
};
type CameraHitArea = {
  args: CameraWirePoint;
  position: CameraWirePoint;
};

function ViewportObjectLabel({
  children,
  position,
}: {
  children: ReactNode;
  position: [number, number, number];
}) {
  return (
    <Html
      center
      distanceFactor={ROLE_LABEL_DISTANCE_FACTOR}
      pointerEvents="none"
      position={position}
      sprite
      transform
      zIndexRange={[0, 1]}
    >
      <div className="role-label">{children}</div>
    </Html>
  );
}

function ViewportTransformControls({
  mode,
  object,
  onObjectChange,
  translationSnap,
}: {
  mode: TransformMode;
  object: TransformControlsProps["object"];
  onObjectChange: TransformControlsProps["onObjectChange"];
  translationSnap?: number | null;
}) {
  const controlsRef = useRef<TransformControlsImpl | null>(null);
  const setControlsRef = useCallback((controls: TransformControlsImpl | null) => {
    controlsRef.current = controls;
    if (controls) {
      controls.userData[HIDE_FROM_VIEWPORT_CAPTURE_KEY] = true;
    }
  }, []);
  const beginUndoBatch = useDirectorStore((state) => state.beginUndoBatch);
  const endUndoBatch = useDirectorStore((state) => state.endUndoBatch);

  return (
    <TransformControls
      ref={setControlsRef}
      mode={mode}
      object={object}
      onMouseDown={beginUndoBatch}
      onMouseUp={endUndoBatch}
      onObjectChange={onObjectChange}
      translationSnap={translationSnap ?? undefined}
      userData={{ [HIDE_FROM_VIEWPORT_CAPTURE_KEY]: true }}
    />
  );
}

export function getViewportCameraQuaternion(
  position: [number, number, number],
  target: [number, number, number]
) {
  const origin = new Vector3(...position);
  const direction = new Vector3(...target).sub(origin);
  if (direction.lengthSq() === 0) return new Quaternion();

  const forward = direction.normalize();
  const up =
    Math.abs(forward.dot(VIEWPORT_CAMERA_WORLD_UP)) > 0.999
      ? new Vector3(0, 0, 1)
      : VIEWPORT_CAMERA_WORLD_UP;
  const matrix = new Matrix4().lookAt(origin, origin.clone().sub(forward), up);

  return new Quaternion().setFromRotationMatrix(matrix);
}

export function getViewportCameraOpaqueDepthRange() {
  const zValues = getViewportCameraBodyWireframeLines()
    .filter((line) => line.part !== "lens")
    .flatMap((line) => line.points)
    .map((point) => point[2]);

  return {
    minZ: Math.min(...zValues),
    maxZ: Math.max(...zValues),
  };
}

export function getViewportCameraLabelY() {
  const points = getViewportCameraBodyWireframeLines().flatMap((line) => line.points);
  const modelTopY = Math.max(...points.map((point) => point[1]));

  return modelTopY + VIEWPORT_OBJECT_LABEL_VERTICAL_GAP;
}

export function getImportedModelNormalization(bounds: Box3, targetMaxSize = IMPORTED_MODEL_TARGET_MAX_SIZE) {
  if (bounds.isEmpty()) {
    return {
      position: [0, 0, 0] as [number, number, number],
      scale: 1,
    };
  }

  const size = new Vector3();
  const center = new Vector3();
  bounds.getSize(size);
  bounds.getCenter(center);

  const maxSize = Math.max(size.x, size.y, size.z);
  const scale = Number.isFinite(maxSize) && maxSize > 0 ? targetMaxSize / maxSize : 1;

  return {
    position: [-center.x * scale, -bounds.min.y * scale, -center.z * scale] as [number, number, number],
    scale,
  };
}

function createBoxWireframeLines({
  center,
  size,
}: {
  center: CameraWirePoint;
  size: CameraWirePoint;
}): CameraWirePointLine[] {
  const [cx, cy, cz] = center;
  const [width, height, depth] = size;
  const x0 = cx - width / 2;
  const x1 = cx + width / 2;
  const y0 = cy - height / 2;
  const y1 = cy + height / 2;
  const z0 = cz - depth / 2;
  const z1 = cz + depth / 2;
  const corners: Record<string, CameraWirePoint> = {
    bbl: [x0, y0, z0],
    bbr: [x1, y0, z0],
    btl: [x0, y1, z0],
    btr: [x1, y1, z0],
    fbl: [x0, y0, z1],
    fbr: [x1, y0, z1],
    ftl: [x0, y1, z1],
    ftr: [x1, y1, z1],
  };

  return [
    [corners.bbl, corners.bbr],
    [corners.bbr, corners.btr],
    [corners.btr, corners.btl],
    [corners.btl, corners.bbl],
    [corners.fbl, corners.fbr],
    [corners.fbr, corners.ftr],
    [corners.ftr, corners.ftl],
    [corners.ftl, corners.fbl],
    [corners.bbl, corners.fbl],
    [corners.bbr, corners.fbr],
    [corners.btr, corners.ftr],
    [corners.btl, corners.ftl],
  ];
}

function createCircleWireframeLine({
  center,
  radius,
  segments = 32,
  plane = "xy",
}: {
  center: CameraWirePoint;
  radius: number;
  segments?: number;
  plane?: "xy" | "xz" | "yz";
}): CameraWirePointLine {
  const [cx, cy, cz] = center;
  return Array.from({ length: segments + 1 }, (_, index) => {
    const angle = (Math.PI * 2 * index) / segments;
    const a = Math.cos(angle) * radius;
    const b = Math.sin(angle) * radius;

    if (plane === "xz") return [cx + a, cy, cz + b];
    if (plane === "yz") return [cx, cy + a, cz + b];

    return [cx + a, cy + b, cz];
  });
}

function createInvertedTetrahedronLensWireframeLines(): CameraWirePointLine[] {
  const backTopLeft: CameraWirePoint = [
    -0.10 * VIEWPORT_CAMERA_VISUAL_SCALE,
    0.10 * VIEWPORT_CAMERA_VISUAL_SCALE,
    VIEWPORT_CAMERA_BODY_FRONT_Z,
  ];
  const backTopRight: CameraWirePoint = [
    0.10 * VIEWPORT_CAMERA_VISUAL_SCALE,
    0.10 * VIEWPORT_CAMERA_VISUAL_SCALE,
    VIEWPORT_CAMERA_BODY_FRONT_Z,
  ];
  const backBottomRight: CameraWirePoint = [
    0.10 * VIEWPORT_CAMERA_VISUAL_SCALE,
    -0.10 * VIEWPORT_CAMERA_VISUAL_SCALE,
    VIEWPORT_CAMERA_BODY_FRONT_Z,
  ];
  const backBottomLeft: CameraWirePoint = [
    -0.10 * VIEWPORT_CAMERA_VISUAL_SCALE,
    -0.10 * VIEWPORT_CAMERA_VISUAL_SCALE,
    VIEWPORT_CAMERA_BODY_FRONT_Z,
  ];

  const frontTopLeft: CameraWirePoint = [
    -0.25 * VIEWPORT_CAMERA_VISUAL_SCALE,
    0.2 * VIEWPORT_CAMERA_VISUAL_SCALE,
    VIEWPORT_CAMERA_LENS_TIP[2],
  ];
  const frontTopRight: CameraWirePoint = [
    0.25 * VIEWPORT_CAMERA_VISUAL_SCALE,
    0.2 * VIEWPORT_CAMERA_VISUAL_SCALE,
    VIEWPORT_CAMERA_LENS_TIP[2],
  ];
  const frontBottomRight: CameraWirePoint = [
    0.25 * VIEWPORT_CAMERA_VISUAL_SCALE,
    -0.2 * VIEWPORT_CAMERA_VISUAL_SCALE,
    VIEWPORT_CAMERA_LENS_TIP[2],
  ];
  const frontBottomLeft: CameraWirePoint = [
    -0.25 * VIEWPORT_CAMERA_VISUAL_SCALE,
    -0.2 * VIEWPORT_CAMERA_VISUAL_SCALE,
    VIEWPORT_CAMERA_LENS_TIP[2],
  ];

  return [
    [backTopLeft, backTopRight, backBottomRight, backBottomLeft, backTopLeft],
    [frontTopLeft, frontTopRight, frontBottomRight, frontBottomLeft, frontTopLeft],

    [backTopLeft, frontTopLeft],
    [backTopRight, frontTopRight],
    [backBottomRight, frontBottomRight],
    [backBottomLeft, frontBottomLeft],

  ];
}
function withCameraPart(part: CameraWirePart, lines: CameraWirePointLine[]): CameraWireLine[] {
  return lines.map((points) => ({ part, points }));
}

export function getViewportCameraBodyWireframeLines(): CameraWireLine[] {
  return [
    ...withCameraPart("body", [
      ...createBoxWireframeLines({ center: VIEWPORT_CAMERA_BODY_CENTER, size: VIEWPORT_CAMERA_BODY_SIZE }),
    ]),
    ...withCameraPart("lens", createInvertedTetrahedronLensWireframeLines()),
    ...withCameraPart("reel", [
      createCircleWireframeLine({
        center: [0, 0.44 * VIEWPORT_CAMERA_VISUAL_SCALE, -0.78 * VIEWPORT_CAMERA_VISUAL_SCALE],
        radius: 0.21 * VIEWPORT_CAMERA_VISUAL_SCALE,
        plane: "yz",
      }),
      createCircleWireframeLine({
        center: [0, 0.44 * VIEWPORT_CAMERA_VISUAL_SCALE, -0.34 * VIEWPORT_CAMERA_VISUAL_SCALE],
        radius: 0.21 * VIEWPORT_CAMERA_VISUAL_SCALE,
        plane: "yz",
      }),
    ]),
  ];
}

export function getViewportCameraHitArea(): CameraHitArea {
  const points = getViewportCameraBodyWireframeLines().flatMap((line) => line.points);
  const minX = Math.min(...points.map((point) => point[0]));
  const maxX = Math.max(...points.map((point) => point[0]));
  const minY = Math.min(...points.map((point) => point[1]));
  const maxY = Math.max(...points.map((point) => point[1]));
  const minZ = Math.min(...points.map((point) => point[2]));
  const maxZ = Math.max(...points.map((point) => point[2]));

  return {
    args: [
      maxX - minX + VIEWPORT_CAMERA_HIT_PADDING * 2,
      maxY - minY + VIEWPORT_CAMERA_HIT_PADDING * 2,
      maxZ - minZ + VIEWPORT_CAMERA_HIT_PADDING * 2,
    ],
    position: [(minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2],
  };
}

function NormalizedImportedObject({ object }: { object: Object3D }) {
  const { clone, normalization } = useMemo(() => {
    const clonedObject = object.clone(true);
    clonedObject.updateMatrixWorld(true);

    return {
      clone: clonedObject,
      normalization: getImportedModelNormalization(new Box3().setFromObject(clonedObject)),
    };
  }, [object]);

  return (
    <group
      position={normalization.position}
      scale={[normalization.scale, normalization.scale, normalization.scale]}
    >
      <primitive object={clone} />
    </group>
  );
}

function FbxModel({ url }: { url: string }) {
  const object = useLoader(FBXLoader, url);

  return <NormalizedImportedObject object={object} />;
}

function ObjModel({ url }: { url: string }) {
  const object = useLoader(OBJLoader, url);

  return <NormalizedImportedObject object={object} />;
}

function ImportedModel({
  fileName,
  url,
}: {
  fileName: string;
  url: string;
}) {
  if (/\.fbx$/i.test(fileName)) return <FbxModel url={url} />;
  if (/\.obj$/i.test(fileName)) return <ObjModel url={url} />;
  return null;
}

function GeometryPrimitiveModel({
  color = "#d7e7ff",
  geometryType,
}: {
  color?: string;
  geometryType: GeometryPrimitiveType;
}) {
  const material = <meshStandardMaterial color={color} metalness={0.02} roughness={0.68} />;

  if (geometryType === "sphere") {
    return (
      <mesh name="geometry-sphere" position={[0, 0.55, 0]}>
        <sphereGeometry args={[0.55, 32, 16]} />
        {material}
      </mesh>
    );
  }

  if (geometryType === "cylinder") {
    return (
      <mesh name="geometry-cylinder" position={[0, 0.6, 0]}>
        <cylinderGeometry args={[0.45, 0.45, 1.2, 32]} />
        {material}
      </mesh>
    );
  }

  if (geometryType === "torus") {
    return (
      <mesh name="geometry-torus" position={[0, 0.14, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.45, 0.14, 16, 48]} />
        {material}
      </mesh>
    );
  }

  if (geometryType === "cone") {
    return (
      <mesh name="geometry-cone" position={[0, 0.55, 0]}>
        <coneGeometry args={[0.5, 1.1, 32]} />
        {material}
      </mesh>
    );
  }

  if (geometryType === "pyramid") {
    return (
      <mesh name="geometry-pyramid" position={[0, 0.55, 0]}>
        <coneGeometry args={[0.55, 1.1, 4]} />
        {material}
      </mesh>
    );
  }

  // 家具类组合几何体（统一着色，底部贴 y=0）
  if (geometryType === "chair") {
    return (
      <group name="geometry-chair">
        <mesh position={[0, 0.46, 0]}>
          <boxGeometry args={[0.9, 0.08, 0.9]} />
          {material}
        </mesh>
        <mesh position={[0, 0.725, -0.41]}>
          <boxGeometry args={[0.9, 0.45, 0.08]} />
          {material}
        </mesh>
        {(
          [
            [-0.41, -0.41],
            [0.41, -0.41],
            [-0.41, 0.41],
            [0.41, 0.41],
          ] as const
        ).map(([x, z], index) => (
          <mesh key={index} position={[x, 0.21, z]}>
            <boxGeometry args={[0.08, 0.42, 0.08]} />
            {material}
          </mesh>
        ))}
      </group>
    );
  }

  if (geometryType === "stool") {
    return (
      <group name="geometry-stool">
        <mesh position={[0, 0.46, 0]}>
          <boxGeometry args={[0.8, 0.08, 0.8]} />
          {material}
        </mesh>
        {(
          [
            [-0.36, -0.36],
            [0.36, -0.36],
            [-0.36, 0.36],
            [0.36, 0.36],
          ] as const
        ).map(([x, z], index) => (
          <mesh key={index} position={[x, 0.21, z]}>
            <boxGeometry args={[0.08, 0.42, 0.08]} />
            {material}
          </mesh>
        ))}
      </group>
    );
  }

  if (geometryType === "table") {
    return (
      <group name="geometry-table">
        <mesh position={[0, 0.74, 0]}>
          <boxGeometry args={[1.6, 0.08, 0.9]} />
          {material}
        </mesh>
        {(
          [
            [-0.74, -0.4],
            [0.74, -0.4],
            [-0.74, 0.4],
            [0.74, 0.4],
          ] as const
        ).map(([x, z], index) => (
          <mesh key={index} position={[x, 0.35, z]}>
            <boxGeometry args={[0.08, 0.7, 0.08]} />
            {material}
          </mesh>
        ))}
      </group>
    );
  }

  if (geometryType === "conference-table") {
    return (
      <group name="geometry-conference-table">
        <mesh position={[0, 0.74, 0]}>
          <boxGeometry args={[3.2, 0.08, 1.2]} />
          {material}
        </mesh>
        {(
          [
            [-1.48, -0.55],
            [0, -0.55],
            [1.48, -0.55],
            [-1.48, 0.55],
            [0, 0.55],
            [1.48, 0.55],
          ] as const
        ).map(([x, z], index) => (
          <mesh key={index} position={[x, 0.35, z]}>
            <boxGeometry args={[0.08, 0.7, 0.08]} />
            {material}
          </mesh>
        ))}
      </group>
    );
  }

  if (geometryType === "coffee-table") {
    return (
      <group name="geometry-coffee-table">
        <mesh position={[0, 0.4, 0]}>
          <boxGeometry args={[1.2, 0.06, 0.7]} />
          {material}
        </mesh>
        {(
          [
            [-0.55, -0.3],
            [0.55, -0.3],
            [-0.55, 0.3],
            [0.55, 0.3],
          ] as const
        ).map(([x, z], index) => (
          <mesh key={index} position={[x, 0.2, z]}>
            <boxGeometry args={[0.06, 0.4, 0.06]} />
            {material}
          </mesh>
        ))}
      </group>
    );
  }

  if (geometryType === "sofa") {
    return (
      <group name="geometry-sofa">
        <mesh position={[0, 0.15, 0]}>
          <boxGeometry args={[1.8, 0.3, 0.85]} />
          {material}
        </mesh>
        <mesh position={[0, 0.36, 0.075]}>
          <boxGeometry args={[1.6, 0.12, 0.7]} />
          {material}
        </mesh>
        <mesh position={[0, 0.6, -0.335]}>
          <boxGeometry args={[1.8, 0.45, 0.18]} />
          {material}
        </mesh>
        <mesh position={[-0.81, 0.34, 0]}>
          <boxGeometry args={[0.18, 0.38, 0.85]} />
          {material}
        </mesh>
        <mesh position={[0.81, 0.34, 0]}>
          <boxGeometry args={[0.18, 0.38, 0.85]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "bed") {
    return (
      <group name="geometry-bed">
        <mesh position={[0, 0.125, 0]}>
          <boxGeometry args={[2.0, 0.25, 1.5]} />
          {material}
        </mesh>
        <mesh position={[0, 0.32, 0]}>
          <boxGeometry args={[1.9, 0.14, 1.4]} />
          {material}
        </mesh>
        <mesh position={[0, 0.4, -0.7]}>
          <boxGeometry args={[2.0, 0.55, 0.1]} />
          {material}
        </mesh>
        <mesh position={[0, 0.265, 0.7]}>
          <boxGeometry args={[2.0, 0.28, 0.1]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "cabinet") {
    return (
      <group name="geometry-cabinet">
        <mesh position={[0, 0.9, 0]}>
          <boxGeometry args={[1.0, 1.8, 0.4]} />
          {material}
        </mesh>
        <mesh position={[0, 0.6, 0]}>
          <boxGeometry args={[1.0, 0.02, 0.4]} />
          {material}
        </mesh>
        <mesh position={[0, 1.2, 0]}>
          <boxGeometry args={[1.0, 0.02, 0.4]} />
          {material}
        </mesh>
        <mesh position={[0, 1.82, 0]}>
          <boxGeometry args={[1.1, 0.04, 0.5]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "door") {
    return (
      <group name="geometry-door">
        <mesh position={[-0.55, 1.05, 0]}>
          <boxGeometry args={[0.1, 2.1, 0.1]} />
          {material}
        </mesh>
        <mesh position={[0.55, 1.05, 0]}>
          <boxGeometry args={[0.1, 2.1, 0.1]} />
          {material}
        </mesh>
        <mesh position={[0, 2.05, 0]}>
          <boxGeometry args={[1.2, 0.1, 0.1]} />
          {material}
        </mesh>
        <mesh position={[0, 1.0, 0.02]}>
          <boxGeometry args={[1.0, 2.0, 0.04]} />
          {material}
        </mesh>
        <mesh position={[0.42, 1.0, 0.08]}>
          <sphereGeometry args={[0.03, 12, 8]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "window") {
    return (
      <group name="geometry-window">
        <mesh position={[-0.75, 1.6, 0]}>
          <boxGeometry args={[0.06, 1.2, 0.06]} />
          {material}
        </mesh>
        <mesh position={[0.75, 1.6, 0]}>
          <boxGeometry args={[0.06, 1.2, 0.06]} />
          {material}
        </mesh>
        <mesh position={[0, 2.2, 0]}>
          <boxGeometry args={[1.56, 0.06, 0.06]} />
          {material}
        </mesh>
        <mesh position={[0, 1.0, 0]}>
          <boxGeometry args={[1.56, 0.06, 0.06]} />
          {material}
        </mesh>
        <mesh position={[0, 1.6, 0]}>
          <boxGeometry args={[1.5, 0.04, 0.04]} />
          {material}
        </mesh>
        <mesh position={[0, 1.6, 0]}>
          <boxGeometry args={[0.04, 1.2, 0.04]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "stairs") {
    return (
      <group name="geometry-stairs">
        {(
          [
            [-0.6, 0.2, 0.1],
            [-0.3, 0.4, 0.2],
            [0, 0.6, 0.3],
            [0.3, 0.8, 0.4],
            [0.6, 1.0, 0.5],
          ] as const
        ).map(([x, height, centerY], index) => (
          <mesh key={index} position={[x, centerY, 0]}>
            <boxGeometry args={[0.3, height, 1.0]} />
            {material}
          </mesh>
        ))}
      </group>
    );
  }

  if (geometryType === "wall") {
    return (
      <group name="geometry-wall">
        <mesh position={[0, 1.25, 0]}>
          <boxGeometry args={[3.0, 2.5, 0.1]} />
          {material}
        </mesh>
      </group>
    );
  }

  // 道具类组合几何体
  if (geometryType === "streetlight") {
    return (
      <group name="geometry-streetlight">
        <mesh position={[0, 0.04, 0]}>
          <cylinderGeometry args={[0.1, 0.1, 0.08, 16]} />
          {material}
        </mesh>
        <mesh position={[0, 1.25, 0]}>
          <cylinderGeometry args={[0.05, 0.05, 2.5, 16]} />
          {material}
        </mesh>
        <mesh position={[0, 2.55, 0]}>
          <coneGeometry args={[0.18, 0.25, 16]} />
          {material}
        </mesh>
        <mesh position={[0, 2.5, 0]}>
          <sphereGeometry args={[0.06, 16, 12]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "cup") {
    return (
      <group name="geometry-cup">
        <mesh position={[0, 0.06, 0]}>
          <cylinderGeometry args={[0.055, 0.05, 0.12, 24]} />
          {material}
        </mesh>
        <mesh position={[0.075, 0.06, 0]} rotation={[0, Math.PI / 2, 0]}>
          <torusGeometry args={[0.04, 0.008, 8, 24]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "bottle") {
    return (
      <group name="geometry-bottle">
        <mesh position={[0, 0.11, 0]}>
          <cylinderGeometry args={[0.07, 0.07, 0.22, 24]} />
          {material}
        </mesh>
        <mesh position={[0, 0.25, 0]}>
          <cylinderGeometry args={[0.025, 0.07, 0.06, 24]} />
          {material}
        </mesh>
        <mesh position={[0, 0.3, 0]}>
          <cylinderGeometry args={[0.025, 0.025, 0.06, 16]} />
          {material}
        </mesh>
        <mesh position={[0, 0.34, 0]}>
          <cylinderGeometry args={[0.03, 0.03, 0.02, 16]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "book") {
    return (
      <group name="geometry-book">
        <mesh position={[0, 0.02, 0]}>
          <boxGeometry args={[0.22, 0.04, 0.15]} />
          {material}
        </mesh>
        <mesh position={[-0.1, 0.025, 0]}>
          <boxGeometry args={[0.02, 0.05, 0.16]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "umbrella") {
    return (
      <group name="geometry-umbrella">
        <mesh position={[0, 0.02, 0]}>
          <sphereGeometry args={[0.04, 12, 8]} />
          {material}
        </mesh>
        <mesh position={[0, 0.5, 0]}>
          <cylinderGeometry args={[0.02, 0.02, 1.0, 12]} />
          {material}
        </mesh>
        <mesh position={[0, 1.2, 0]}>
          <coneGeometry args={[0.45, 0.35, 12]} />
          {material}
        </mesh>
        <mesh position={[0, 1.425, 0]}>
          <coneGeometry args={[0.04, 0.1, 12]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "potted-plant") {
    return (
      <group name="geometry-potted-plant">
        <mesh position={[0, 0.1, 0]}>
          <cylinderGeometry args={[0.14, 0.1, 0.2, 16]} />
          {material}
        </mesh>
        <mesh position={[0, 0.21, 0]}>
          <cylinderGeometry args={[0.13, 0.13, 0.02, 16]} />
          {material}
        </mesh>
        <mesh position={[0, 0.4, 0]}>
          <sphereGeometry args={[0.16, 12, 10]} />
          {material}
        </mesh>
        <mesh position={[-0.1, 0.5, -0.05]}>
          <sphereGeometry args={[0.1, 12, 10]} />
          {material}
        </mesh>
        <mesh position={[0.1, 0.5, 0.05]}>
          <sphereGeometry args={[0.1, 12, 10]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "fence") {
    return (
      <group name="geometry-fence">
        {[-0.45, -0.15, 0.15, 0.45].map((x, index) => (
          <mesh key={index} position={[x, 0.4, 0]}>
            <boxGeometry args={[0.05, 0.8, 0.05]} />
            {material}
          </mesh>
        ))}
        <mesh position={[0, 0.25, 0]}>
          <boxGeometry args={[1.0, 0.04, 0.03]} />
          {material}
        </mesh>
        <mesh position={[0, 0.6, 0]}>
          <boxGeometry args={[1.0, 0.04, 0.03]} />
          {material}
        </mesh>
      </group>
    );
  }

  if (geometryType === "signboard") {
    return (
      <group name="geometry-signboard">
        <mesh position={[0, 0.02, 0]}>
          <cylinderGeometry args={[0.1, 0.1, 0.04, 16]} />
          {material}
        </mesh>
        <mesh position={[0, 0.75, 0]}>
          <cylinderGeometry args={[0.04, 0.04, 1.5, 12]} />
          {material}
        </mesh>
        <mesh position={[0, 1.6, 0]}>
          <boxGeometry args={[0.6, 0.4, 0.04]} />
          {material}
        </mesh>
      </group>
    );
  }

  return (
    <mesh name="geometry-box" position={[0, 0.5, 0]}>
      <boxGeometry args={[1, 1, 1]} />
      {material}
    </mesh>
  );
}

function ObjectSceneNode({
  asset,
  item,
  selected,
  showLabels,
  transformMode,
  transformable,
  translationSnap,
  onSelect,
}: {
  asset?: DirectorAssetRef;
  item: DirectorObject;
  selected: boolean;
  showLabels: boolean;
  transformMode: TransformMode;
  transformable: boolean;
  translationSnap: number | null;
  onSelect?: (item: DirectorObject) => void;
}) {
  const groupRef = useRef<Group>(null!);
  const [measuredCharacterLabel, setMeasuredCharacterLabel] = useState<{
    key: string;
    y: number;
  } | null>(null);
  const updateObjectTransform = useDirectorStore((state) => state.updateObjectTransform);
  const isImportedModel = asset?.sourceType === "model";
  const characterLabelKey = `${item.id}:${item.bodyType ?? ""}:${item.characterRig?.rigType ?? ""}`;
  const fallbackCharacterLabelY =
    item.kind === "character"
      ? item.characterRig?.rigType === "ue4-mannequin"
        ? getUE4GroundedLabelY(item.bodyType)
        : getGroundedLabelY(item.bodyType)
      : 1.25;
  const characterLabelY =
    measuredCharacterLabel?.key === characterLabelKey ? measuredCharacterLabel.y : fallbackCharacterLabelY;
  const handleCharacterLabelAnchorYChange = useCallback(
    (anchorY: number) => {
      setMeasuredCharacterLabel((current) => {
        const nextY = Number(anchorY.toFixed(4));

        if (current?.key === characterLabelKey && Math.abs(current.y - nextY) < 0.0001) {
          return current;
        }

        return {
          key: characterLabelKey,
          y: nextY,
        };
      });
    },
    [characterLabelKey]
  );

  function commitTransformFromViewport() {
    const group = groupRef.current;
    if (!group) return;

    updateObjectTransform(item.id, {
      position: [group.position.x, group.position.y, group.position.z],
      rotation: [group.rotation.x, group.rotation.y, group.rotation.z],
      scale: [group.scale.x, group.scale.y, group.scale.z],
    });
  }

  const node = (
    <group
      ref={groupRef}
      position={item.transform.position}
      rotation={item.transform.rotation}
      scale={item.transform.scale}
      onClick={(event) => {
        event.stopPropagation();
        onSelect?.(item);
      }}
    >
      {isImportedModel && asset ? (
        <Suspense fallback={null}>
          <ImportedModel fileName={asset.fileName} url={asset.url} />
        </Suspense>
      ) : item.kind === "character" ? (
        <>
          <Suspense fallback={null}>
            <CharacterModel
              bodyType={item.bodyType}
              color={item.color}
              onLabelAnchorYChange={handleCharacterLabelAnchorYChange}
              rigState={item.characterRig}
            />
          </Suspense>
          {showLabels ? (
            <ViewportObjectLabel position={[0, characterLabelY, 0]}>{item.name}</ViewportObjectLabel>
          ) : null}
        </>
      ) : item.kind === "prop" && item.geometryType ? (
        <GeometryPrimitiveModel color={item.color} geometryType={item.geometryType} />
      ) : null}
    </group>
  );

  if (!selected || !transformable) return node;

  return (
    <>
      {node}
      <ViewportTransformControls
        mode={transformMode}
        object={groupRef}
        onObjectChange={commitTransformFromViewport}
        translationSnap={transformMode === "translate" ? translationSnap : null}
      />
    </>
  );
}

function CrowdTransformRig({
  crowdId,
  objects,
  selected,
  transformMode,
  transformable,
  translationSnap,
}: {
  crowdId: string;
  objects: DirectorObject[];
  selected: boolean;
  transformMode: TransformMode;
  transformable: boolean;
  translationSnap: number | null;
}) {
  const groupRef = useRef<Group>(null!);
  const updateCrowdTransform = useDirectorStore((state) => state.updateCrowdTransform);
  const crowdAnchor = useMemo(() => getCrowdAnchorTransform(objects, crowdId), [objects, crowdId]);

  function commitCrowdTransformFromViewport() {
    const group = groupRef.current;
    if (!group) return;

    updateCrowdTransform(crowdId, {
      position: [group.position.x, group.position.y, group.position.z],
      rotation: [group.rotation.x, group.rotation.y, group.rotation.z],
      scale: [group.scale.x, group.scale.y, group.scale.z],
    });
  }

  if (!selected || !transformable || !crowdAnchor) return null;

  return (
    <>
      <group
        ref={groupRef}
        position={crowdAnchor.position}
        rotation={crowdAnchor.rotation}
        scale={crowdAnchor.scale}
      />
      <ViewportTransformControls
        mode={transformMode}
        object={groupRef}
        onObjectChange={commitCrowdTransformFromViewport}
        translationSnap={transformMode === "translate" ? translationSnap : null}
      />
    </>
  );
}

export function getViewportCameraFrustumLines(
  _camera: DirectorCameraShot
): Array<[[number, number, number], [number, number, number]]> {
  const frameDepth = VIEWPORT_CAMERA_FRUSTUM_DEPTH;
  const halfWidth = VIEWPORT_CAMERA_FRUSTUM_FRAME_WIDTH / 2;
  const halfHeight = VIEWPORT_CAMERA_FRUSTUM_FRAME_WIDTH / VIEWPORT_CAMERA_ASPECT / 2;
  const topLeft: [number, number, number] = [-halfWidth, halfHeight, frameDepth];
  const topRight: [number, number, number] = [halfWidth, halfHeight, frameDepth];
  const bottomRight: [number, number, number] = [halfWidth, -halfHeight, frameDepth];
  const bottomLeft: [number, number, number] = [-halfWidth, -halfHeight, frameDepth];

  return [
    [VIEWPORT_CAMERA_LENS_TIP, topLeft],
    [VIEWPORT_CAMERA_LENS_TIP, topRight],
    [VIEWPORT_CAMERA_LENS_TIP, bottomRight],
    [VIEWPORT_CAMERA_LENS_TIP, bottomLeft],
    [topLeft, topRight],
    [topRight, bottomRight],
    [bottomRight, bottomLeft],
    [bottomLeft, topLeft],
  ];
}

function ViewportCameraRig({
  camera,
  object,
  selected,
  showLabel,
  transformMode,
  transformable,
  translationSnap,
}: {
  camera: DirectorCameraShot;
  object?: DirectorObject;
  selected: boolean;
  showLabel: boolean;
  transformMode: TransformMode;
  transformable: boolean;
  translationSnap: number | null;
}) {
  const groupRef = useRef<Group>(null!);
  const selectObject = useDirectorStore((state) => state.selectObject);
  const updateCamera = useDirectorStore((state) => state.updateCamera);
  const bodyWireframeLines = useMemo(() => getViewportCameraBodyWireframeLines(), []);
  const cameraHitArea = useMemo(() => getViewportCameraHitArea(), []);
  const cameraLabelY = useMemo(() => getViewportCameraLabelY(), []);
  const frustumLines = useMemo(() => getViewportCameraFrustumLines(camera), [camera]);
  const cameraQuaternion = useMemo(
    () => getViewportCameraQuaternion(camera.transform.position, camera.target),
    [camera.target, camera.transform.position]
  );

  useLayoutEffect(() => {
    groupRef.current?.quaternion?.copy?.(cameraQuaternion);
  }, [cameraQuaternion]);

  function commitCameraTransformFromViewport() {
    const group = groupRef.current;
    if (!group) return;

    const position: [number, number, number] = [group.position.x, group.position.y, group.position.z];
    const forward = VIEWPORT_CAMERA_FORWARD.clone().applyQuaternion(group.quaternion).normalize();
    const currentDistance = new Vector3(...camera.target).distanceTo(group.position);
    const nextTarget = group.position.clone().add(forward.multiplyScalar(Math.max(currentDistance, 0.1)));

    updateCamera(camera.id, {
      transform: {
        position,
        rotation: [group.rotation.x, group.rotation.y, group.rotation.z],
        scale: [group.scale.x, group.scale.y, group.scale.z],
      },
      target: [nextTarget.x, nextTarget.y, nextTarget.z],
    });
  }

  function selectCameraFromViewport(event: ThreeEvent<MouseEvent>) {
    event.stopPropagation();
    selectObject(object?.id ?? null);
  }

  const node = (
    <group
      ref={groupRef}
      position={camera.transform.position}
      quaternion={cameraQuaternion}
      scale={object?.transform.scale ?? [1, 1, 1]}
      userData={{ [HIDE_FROM_VIEWPORT_CAPTURE_KEY]: true }}
      onClick={selectCameraFromViewport}
    >
      {showLabel ? (
        <ViewportObjectLabel position={[0, cameraLabelY, 0]}>{camera.name}</ViewportObjectLabel>
      ) : null}

      <mesh name={`${camera.id}-hit-area`} onClick={selectCameraFromViewport} position={cameraHitArea.position}>
        <boxGeometry args={cameraHitArea.args} />
        <meshBasicMaterial depthWrite={false} opacity={0} transparent />
      </mesh>

      {bodyWireframeLines.map((line, index) => (
        <Line
          key={`${camera.id}-${line.part}-${index}`}
          color={VIEWPORT_CAMERA_LINE}
          lineWidth={1}
          name={`${camera.id}-${line.part}-${index}`}
          onClick={selectCameraFromViewport}
          opacity={VIEWPORT_CAMERA_LINE_OPACITY}
          points={line.points}
          transparent
        />
      ))}

      {frustumLines.map((points, index) => (
        <Line
          key={`${camera.id}-frustum-${index}`}
          color={VIEWPORT_CAMERA_LINE}
          lineWidth={1}
          name={`${camera.id}-viewfinder-${index}`}
          onClick={selectCameraFromViewport}
          opacity={VIEWPORT_CAMERA_LINE_OPACITY}
          points={points}
          transparent
        />
      ))}
    </group>
  );

  if (!selected || !transformable) return node;

  return (
    <>
      {node}
      <ViewportTransformControls
        mode={transformMode}
        object={groupRef}
        onObjectChange={commitCameraTransformFromViewport}
        translationSnap={transformMode === "translate" ? translationSnap : null}
      />
    </>
  );
}

export function SceneRoot() {
  const scene = useDirectorStore((state) => state.project.scene);
  const assets = useDirectorStore((state) => state.project.assets);
  const objects = useDirectorStore((state) => state.project.objects);
  const cameras = useDirectorStore((state) => state.project.cameras);
  const panoramaAssetId = useDirectorStore((state) => state.project.panoramaAssetId);
  const viewMode = useDirectorStore((state) => state.viewMode);
  const selectedObjectId = useDirectorStore((state) => state.selectedObjectId);
  const selectedCrowdId = useDirectorStore((state) => state.selectedCrowdId);
  const transformMode = useDirectorStore((state) => state.transformMode);
  const selectObject = useDirectorStore((state) => state.selectObject);
  const selectCrowd = useDirectorStore((state) => state.selectCrowd);
  const panoramaAsset = assets.find((item) => item.id === panoramaAssetId);
  const translationSnap = scene.snapToGrid ? 1 : null;
  const assetsById = useMemo(() => new Map(assets.map((item) => [item.id, item])), [assets]);
  const cameraObjectsByCameraId = useMemo(() => {
    return new Map(
      objects
        .filter((item) => item.kind === "camera" && item.linkedCameraId)
        .map((item) => [item.linkedCameraId as string, item])
    );
  }, [objects]);
  const crowdLocksById = useMemo(() => {
    const result = new Map<string, boolean>();
    const crowdMembers = objects.filter((item) => item.kind === "character" && item.crowdId);

    crowdMembers.forEach((item) => {
      const crowdId = item.crowdId as string;
      result.set(crowdId, (result.get(crowdId) ?? false) || item.locked);
    });

    return result;
  }, [objects]);

  function handleObjectSelect(item: DirectorObject) {
    if (item.kind === "character" && item.crowdId) {
      selectCrowd(item.crowdId);
      return;
    }

    selectObject(item.id);
  }

  return (
    <group
      position={scene.position}
      rotation={scene.rotation}
      scale={[scene.scale, scene.scale, scene.scale]}
    >
      {scene.showGround ? (
        <mesh position={[0, scene.groundHeight, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[200, 200]} />
          <meshBasicMaterial
            color="#303640"
            opacity={getEffectiveGroundOpacity(scene.groundOpacity, Boolean(panoramaAsset))}
            polygonOffset
            polygonOffsetFactor={1}
            polygonOffsetUnits={1}
            transparent
          />
        </mesh>
      ) : null}
      {objects
        .filter((item) => item.visible && item.kind !== "camera")
        .map((item) => {
          const asset = item.assetRefId ? assetsById.get(item.assetRefId) : undefined;

          return (
            <ObjectSceneNode
              key={item.id}
              asset={asset}
              item={item}
              selected={item.crowdId ? false : item.id === selectedObjectId}
              showLabels={scene.showLabels}
              transformMode={transformMode}
              transformable={!item.locked}
              translationSnap={translationSnap}
              onSelect={handleObjectSelect}
            />
          );
        })}
      {Array.from(new Set(objects.map((item) => item.crowdId).filter((item): item is string => typeof item === "string"))).map(
        (crowdId) => (
          <CrowdTransformRig
            key={crowdId}
            crowdId={crowdId}
            objects={objects}
            selected={selectedCrowdId === crowdId}
            transformMode={transformMode}
            transformable={!(crowdLocksById.get(crowdId) ?? false)}
            translationSnap={translationSnap}
          />
        )
      )}
      {viewMode === "director"
        ? cameras
            .map((camera) => ({ camera, object: cameraObjectsByCameraId.get(camera.id) }))
            .filter(({ object }) => object?.visible ?? true)
            .map(({ camera, object }) => (
              <ViewportCameraRig
                key={camera.id}
                camera={camera}
                object={object}
                selected={object?.id === selectedObjectId}
                showLabel={scene.showLabels}
                transformMode={transformMode}
                transformable={Boolean(object && !object.locked)}
                translationSnap={translationSnap}
              />
            ))
        : null}
    </group>
  );
}
