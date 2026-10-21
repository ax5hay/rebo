// Liquid Glass for the navigation layer (Apple HIG "Materials", WWDC25 session 219): content scrolls under
// floating controls, and the glass shows it through lensing, not a flat frost. Here that is:
//   1. Lensing: a displacement map computed for the element's own size and corner radius (a convex
//      bezel: light bends inward near the edge, the middle stays true), applied to the backdrop with an
//      SVG feDisplacementMap. Chromium renders url() in backdrop-filter; other engines get blur only.
//   2. Material: blur + saturation + a translucent tint from the theme (--glass-tint).
//   3. Specular rim: inset highlights whose angle follows the pointer (--lx/--ly), so the edge catches
//      light as you move over it. Apple ties this to device motion; on a desktop the pointer is the light.
// "Reduce transparency" (prefers-reduced-transparency) and forced colours switch it to solid surfaces.
import { createElement, useEffect, useId, useRef, type ElementType, type HTMLAttributes, type ReactNode } from "react";

const lensing = typeof navigator !== "undefined" && /Chrome\//.test(navigator.userAgent) &&  // Chromium engines
  !(typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-transparency: reduce)").matches);

// Displacement map for a rounded rectangle: R/G = 0.5 ± offset, where offset points inward along the
// surface normal and grows toward the edge with the slope of a squircle profile.
function lensMap(w: number, h: number, radius: number, bezel: number): string {
  const s = 0.5;  // the map is drawn at half size and stretched; the lens is smooth enough for it
  const W = Math.max(2, Math.round(w * s)), H = Math.max(2, Math.round(h * s));
  const canvas = document.createElement("canvas");
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext("2d")!;
  const img = ctx.createImageData(W, H);
  const r = Math.min(radius, w / 2, h / 2), hw = w / 2, hh = h / 2;
  const sdf = (x: number, y: number) => {
    const qx = Math.abs(x - hw) - (hw - r), qy = Math.abs(y - hh) - (hh - r);
    return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - r;
  };
  for (let j = 0; j < H; j++) {
    for (let i = 0; i < W; i++) {
      const x = (i + 0.5) / s, y = (j + 0.5) / s;
      const d = -sdf(x, y);                       // depth inside the shape, 0 at the edge
      let ox = 0, oy = 0;
      if (d > 0 && d < bezel) {
        const t = 1 - d / bezel;                  // 1 at the edge, 0 where the flat middle starts
        const m = t * t * (3 - 2 * t);            // smooth bezel slope
        const nx = sdf(x + 1, y) - sdf(x - 1, y), ny = sdf(x, y + 1) - sdf(x, y - 1);
        const n = Math.hypot(nx, ny) || 1;
        ox = (-nx / n) * m; oy = (-ny / n) * m;   // sample from further inside: the edge magnifies
      }
      const k = (j * W + i) * 4;
      img.data[k] = 128 + ox * 127; img.data[k + 1] = 128 + oy * 127; img.data[k + 2] = 128; img.data[k + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return canvas.toDataURL();
}

function useLens(ref: React.RefObject<HTMLElement | null>, id: string, strength: number) {
  useEffect(() => {
    const el = ref.current;
    if (!el || !lensing) return;
    let frame = 0;
    const build = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width < 4 || height < 4) return;
      const radius = parseFloat(getComputedStyle(el).borderTopLeftRadius) || 0;
      const bezel = Math.min(18, Math.max(radius, 10), height / 2);
      const svg = document.getElementById(`${id}-svg`);
      if (!svg) return;
      svg.innerHTML = `<filter id="${id}" x="0" y="0" width="${width}" height="${height}" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
        <feImage href="${lensMap(width, height, radius, bezel)}" x="0" y="0" width="${width}" height="${height}" preserveAspectRatio="none" result="map"/>
        <feDisplacementMap in="SourceGraphic" in2="map" scale="${strength}" xChannelSelector="R" yChannelSelector="G"/></filter>`;
      el.style.setProperty("--lens", `url(#${id})`);
    };
    const ro = new ResizeObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(build); });
    ro.observe(el);
    return () => { ro.disconnect(); cancelAnimationFrame(frame); };
  }, [ref, id, strength]);
}

// The rim light follows the pointer while it is near the element.
function onPointer(e: React.PointerEvent<HTMLElement>) {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--lx", (((e.clientX - r.left) / r.width) * 2 - 1).toFixed(2));
  e.currentTarget.style.setProperty("--ly", (((e.clientY - r.top) / r.height) * 2 - 1).toFixed(2));
}
function onLeave(e: React.PointerEvent<HTMLElement>) {
  e.currentTarget.style.removeProperty("--lx");
  e.currentTarget.style.removeProperty("--ly");
}

type GlassProps = HTMLAttributes<HTMLElement> & { as?: ElementType; strength?: number; children?: ReactNode; [k: string]: any };

export function Glass({ as = "div", className = "", strength = 36, children, ...rest }: GlassProps) {
  const ref = useRef<HTMLElement>(null);
  const id = `lens${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  useLens(ref, id, strength);
  return (
    <>
      {lensing && <svg id={`${id}-svg`} width="0" height="0" style={{ position: "absolute" }} aria-hidden />}
      {createElement(as, { ref, className: `glass ${lensing ? "lensed" : ""} ${className}`, onPointerMove: onPointer, onPointerLeave: onLeave, ...rest }, children)}
    </>
  );
}
