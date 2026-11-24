// site/src/lib/atlas-program.ts -- P2-S5-T02 (10 V1 "Node colour"; 09 S4.3, S4.4). The Atlas's one node program for
// sigma 3.0.3: a ring, and inside it a fill rising from the bottom to the node's level, the rest of the disc in the page
// background. "Saturation renders as fill level rather than hue, so a benchmark at 90% headroom consumed looks 90% full"
// (10 V1). It is sigma's own NodeCircleProgram (sigma/rendering) with two more colours and a level: the same three-vertex
// triangle around the disc, the same picking pass, so hit-testing is sigma's.
//
// Per node it reads, from the display data lib/atlas.ts paint() fills through the island's nodeReducer:
//   color   the fill (sigma's own attribute, so the picking and hover passes need nothing new)
//   ring    the outline, RING_PX wide
//   empty   the disc above the fill: the page background, so an edge drawn beneath stops at the node's rim
//   level   0..1, the fill's height as a fraction of the diameter
//
// This module touches WebGLRenderingContext when it loads, as sigma's own programs do, so only the browser imports it:
// islands/Atlas.tsx loads it with sigma, after hydration.
import { NodeProgram, type ProgramInfo } from 'sigma/rendering';
import type { NodeDisplayData, RenderParams } from 'sigma/types';
import { floatColor } from 'sigma/utils';

/** The display data this program reads beyond sigma's own. */
export interface FillData {
  ring: string;
  empty: string;
  level: number;
}

const RING_PX = 1.5;

// language=GLSL
const VERTEX = /* glsl */ `
attribute vec4 a_id;
attribute vec4 a_color;
attribute vec4 a_ring;
attribute vec4 a_empty;
attribute float a_level;
attribute vec2 a_position;
attribute float a_size;
attribute float a_angle;

uniform mat3 u_matrix;
uniform float u_sizeRatio;
uniform float u_correctionRatio;

varying vec4 v_color;
varying vec4 v_ring;
varying vec4 v_empty;
varying float v_level;
varying vec2 v_diffVector;
varying float v_radius;

const float bias = 255.0 / 254.0;

void main() {
  float size = a_size * u_correctionRatio / u_sizeRatio * 4.0;
  vec2 diffVector = size * vec2(cos(a_angle), sin(a_angle));
  vec2 position = a_position + diffVector;
  gl_Position = vec4((u_matrix * vec3(position, 1)).xy, 0, 1);

  v_diffVector = diffVector;
  v_radius = size / 2.0;
  v_level = a_level;

  #ifdef PICKING_MODE
  v_color = a_id;
  #else
  v_color = a_color;
  #endif
  v_ring = a_ring;
  v_empty = a_empty;

  v_color.a *= bias;
  v_ring.a *= bias;
  v_empty.a *= bias;
}
`;

// One pixel is 2 * u_correctionRatio in v_diffVector's units (sigma's NodeCircleProgram feathers its edge by that much).
// language=GLSL
const FRAGMENT = /* glsl */ `
precision highp float;

varying vec4 v_color;
varying vec4 v_ring;
varying vec4 v_empty;
varying float v_level;
varying vec2 v_diffVector;
varying float v_radius;

uniform float u_correctionRatio;

const vec4 transparent = vec4(0.0, 0.0, 0.0, 0.0);

void main(void) {
  float px = u_correctionRatio * 2.0;
  float dist = length(v_diffVector) - v_radius;

  #ifdef PICKING_MODE
  gl_FragColor = dist > 0.0 ? transparent : v_color;
  #else
  // the height of this fragment across the disc: 0 at the bottom, 1 at the top
  float height = (v_diffVector.y / v_radius + 1.0) / 2.0;
  vec4 inside = height <= v_level ? v_color : v_empty;
  vec4 colour = dist > -${RING_PX.toFixed(1)} * px ? v_ring : inside;
  float t = clamp((dist + px) / px, 0.0, 1.0);
  gl_FragColor = mix(colour, transparent, t);
  #endif
}
`;

const { UNSIGNED_BYTE, FLOAT } = WebGLRenderingContext;
const UNIFORMS = ['u_sizeRatio', 'u_correctionRatio', 'u_matrix'] as const;
const ANGLES = [0, (2 * Math.PI) / 3, (4 * Math.PI) / 3];

export default class FillNodeProgram extends NodeProgram<(typeof UNIFORMS)[number]> {
  getDefinition() {
    return {
      VERTICES: 3,
      VERTEX_SHADER_SOURCE: VERTEX,
      FRAGMENT_SHADER_SOURCE: FRAGMENT,
      METHOD: WebGLRenderingContext.TRIANGLES,
      UNIFORMS,
      ATTRIBUTES: [
        { name: 'a_position', size: 2, type: FLOAT },
        { name: 'a_size', size: 1, type: FLOAT },
        { name: 'a_color', size: 4, type: UNSIGNED_BYTE, normalized: true },
        { name: 'a_ring', size: 4, type: UNSIGNED_BYTE, normalized: true },
        { name: 'a_empty', size: 4, type: UNSIGNED_BYTE, normalized: true },
        { name: 'a_level', size: 1, type: FLOAT },
        { name: 'a_id', size: 4, type: UNSIGNED_BYTE, normalized: true },
      ],
      CONSTANT_ATTRIBUTES: [{ name: 'a_angle', size: 1, type: FLOAT }],
      CONSTANT_DATA: ANGLES.map((a) => [a]),
    };
  }

  processVisibleItem(nodeIndex: number, startIndex: number, data: NodeDisplayData): void {
    const d = data as NodeDisplayData & Partial<FillData>;
    const a = this.array;
    let i = startIndex;
    a[i++] = d.x;
    a[i++] = d.y;
    a[i++] = d.size;
    a[i++] = floatColor(d.color);
    a[i++] = floatColor(d.ring ?? d.color);
    a[i++] = floatColor(d.empty ?? d.color);
    a[i++] = d.level ?? 0;
    a[i++] = nodeIndex;
  }

  setUniforms(params: RenderParams, { gl, uniformLocations }: ProgramInfo): void {
    gl.uniform1f(uniformLocations.u_correctionRatio, params.correctionRatio);
    gl.uniform1f(uniformLocations.u_sizeRatio, params.sizeRatio);
    gl.uniformMatrix3fv(uniformLocations.u_matrix, false, params.matrix);
  }
}
