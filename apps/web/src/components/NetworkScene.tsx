import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Box, Pause, Play, RotateCcw, Truck } from "lucide-react";
import * as THREE from "three";
import type { Network } from "../types";

const colors = [0x62e5ff, 0xa991ff, 0x6c9dff, 0x72edce];

/** A schematic of dataset entities, not a claim about geographic routes or shipment volume. */
export default function NetworkScene({
  network,
  day,
  onInspect,
}: {
  network: Network;
  day: number;
  onInspect: (warehouse: Network["warehouses"][number]) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);
  const [view, setView] = useState(0);
  const groups = [
    network.suppliers,
    network.plants,
    network.warehouses,
    network.markets,
  ];
  const labels = ["Suppliers", "Plants", "Warehouses", "Markets"];
  const active = network.disruptions.filter(
    (d) => d.start_day <= day && day < d.start_day + d.duration,
  );

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: "low-power",
      });
    } catch {
      element.dataset.renderer = "unavailable";
      return;
    }
    element.dataset.renderer = "webgl";
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setClearColor(0x070c1b, 0);
    renderer.domElement.setAttribute("aria-hidden", "true");
    element.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(37, 1, 0.1, 70);
    const world = new THREE.Group();
    scene.add(world);
    scene.add(new THREE.AmbientLight(0xc0d4ff, 2));
    const key = new THREE.DirectionalLight(0xc5deff, 4);
    key.position.set(-3, 8, 4);
    scene.add(key);
    const fill = new THREE.PointLight(0x8866ff, 30, 20);
    fill.position.set(2, 4, -3);
    scene.add(fill);
    const grid = new THREE.GridHelper(14, 28, 0x293869, 0x182447);
    grid.position.y = -0.32;
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.5;
    world.add(grid);
    const stageGroups = [
      network.suppliers,
      network.plants,
      network.warehouses,
      network.markets,
    ];
    const disrupted = new Set(
      network.disruptions
        .filter((d) => d.start_day <= day && day < d.start_day + d.duration)
        .map((d) => d.target_id),
    );
    const positions = new Map<string, THREE.Vector3>();
    stageGroups.forEach((records, stage) => {
      const x = -4.2 + stage * 2.8;
      // All nodes remain represented for imported networks; crowding is explicitly schematic.
      records.forEach((record, index) => {
        const z =
          records.length === 1 ? 0 : (index / (records.length - 1) - 0.5) * 5.5;
        const size = stage === 1 ? 0.57 : stage === 2 ? 0.62 : 0.27;
        const color = disrupted.has(record.id) ? 0xffb374 : colors[stage];
        const geometry =
          stage === 3
            ? new THREE.OctahedronGeometry(size, 0)
            : new THREE.BoxGeometry(size, size * 1.35, size);
        const material = new THREE.MeshStandardMaterial({
          color,
          metalness: 0.55,
          roughness: 0.25,
          emissive: color,
          emissiveIntensity: 0.16,
        });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.set(x, size * 0.68, z);
        mesh.rotation.y = Math.PI / 4;
        world.add(mesh);
        positions.set(record.id, mesh.position.clone());
        const edge = new THREE.LineSegments(
          new THREE.EdgesGeometry(geometry),
          new THREE.LineBasicMaterial({
            color,
            transparent: true,
            opacity: 0.8,
          }),
        );
        mesh.add(edge);
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(size * 1.1, size * 1.25, 40),
          new THREE.MeshBasicMaterial({
            color,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.45,
          }),
        );
        ring.rotation.x = -Math.PI / 2;
        ring.position.set(x, -0.2, z);
        world.add(ring);
      });
      // Stage rails show process order, rather than inventing supplier/plant relationships.
      const rail = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(x, -0.22, -3.3),
          new THREE.Vector3(x, -0.22, 3.3),
        ]),
        new THREE.LineBasicMaterial({
          color: colors[stage],
          transparent: true,
          opacity: 0.4,
        }),
      );
      world.add(rail);
    });
    // Only warehouse-to-market arcs encode actual dataset relationships.
    network.markets.forEach((market) => {
      const start = positions.get(market.warehouse_id);
      const end = positions.get(market.id);
      if (!start || !end) return;
      const middle = start.clone().lerp(end, 0.5);
      middle.y += 1.15;
      const curve = new THREE.QuadraticBezierCurve3(start, middle, end);
      world.add(
        new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(curve.getPoints(32)),
          new THREE.LineBasicMaterial({
            color: 0x78aaff,
            transparent: true,
            opacity: 0.32,
          }),
        ),
      );
    });
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let visible = true,
      frame = 0,
      last = 0;
    let pointerX = 0,
      pointerY = 0;
    const resize = () => {
      const width = element.clientWidth,
        height = element.clientHeight;
      renderer.setSize(width, height);
      camera.aspect = width / Math.max(height, 1);
      camera.position.set(5.5, 7.5, Math.max(12, 18 / camera.aspect));
      camera.lookAt(0, 0, 0);
      camera.updateProjectionMatrix();
      renderer.render(scene, camera);
    };
    const render = (time: number) => {
      if (time - last >= 32) {
        last = time;
        world.rotation.y += (pointerX * 0.12 - world.rotation.y) * 0.05;
        world.rotation.x += (pointerY * 0.04 - world.rotation.x) * 0.05;
        renderer.render(scene, camera);
      }
      frame = requestAnimationFrame(render);
    };
    const motion = () => {
      cancelAnimationFrame(frame);
      if (!paused && !reduced.matches && visible && !document.hidden)
        frame = requestAnimationFrame(render);
      else renderer.render(scene, camera);
    };
    const pointer = (event: PointerEvent) => {
      if (paused || reduced.matches) return;
      const bounds = element.getBoundingClientRect();
      pointerX = (event.clientX - bounds.left) / bounds.width - 0.5;
      pointerY = (event.clientY - bounds.top) / bounds.height - 0.5;
    };
    const leave = () => {
      pointerX = 0;
      pointerY = 0;
    };
    const contextLost = (event: Event) => {
      event.preventDefault();
      cancelAnimationFrame(frame);
      element.dataset.renderer = "unavailable";
    };
    renderer.domElement.addEventListener("webglcontextlost", contextLost);
    element.addEventListener("pointermove", pointer, { passive: true });
    element.addEventListener("pointerleave", leave);
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    const intersection = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      motion();
    });
    intersection.observe(element);
    document.addEventListener("visibilitychange", motion);
    reduced.addEventListener("change", motion);
    resize();
    motion();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      intersection.disconnect();
      document.removeEventListener("visibilitychange", motion);
      reduced.removeEventListener("change", motion);
      element.removeEventListener("pointermove", pointer);
      element.removeEventListener("pointerleave", leave);
      renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        mesh.geometry?.dispose();
        if (mesh.material)
          (Array.isArray(mesh.material)
            ? mesh.material
            : [mesh.material]
          ).forEach((material) => material.dispose());
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [network, day, paused, view]);

  return (
    <section
      className="panel network-observatory"
      aria-label="Supply network visualization"
    >
      <div className="panel-title">
        <div>
          <span className="eyebrow">NETWORK OBSERVATORY</span>
          <h2>Your supply chain, in perspective.</h2>
        </div>
        <div className="scene-controls">
          <button
            type="button"
            className="icon-button"
            aria-label={
              paused ? "Resume network motion" : "Pause network motion"
            }
            onClick={() => setPaused((p) => !p)}
          >
            {paused ? <Play size={14} /> : <Pause size={14} />}
          </button>
          <button
            type="button"
            className="icon-button"
            aria-label="Reset network view"
            onClick={() => setView((v) => v + 1)}
          >
            <RotateCcw size={14} />
          </button>
        </div>
      </div>
      <div className="scene-meta">
        <span>
          <i className="status-dot" /> {network.sku_count} SKUs connected
        </span>
        <span className={active.length ? "scene-warning" : ""}>
          {active.length} active disruptions · day {day + 1} opening
        </span>
      </div>
      <div className="scene-stage">
        <div className="scene-host" ref={host} data-renderer="loading" />
        <div className="scene-fallback">
          <Box size={42} />
          <p>Supply network schematic</p>
          <span>
            3D rendering unavailable. Network details remain available below.
          </span>
        </div>
        <span className="scene-caption">SCHEMATIC VIEW / NOT GEOGRAPHIC</span>
      </div>
      <div className="scene-legend">
        {groups.map((group, i) => (
          <div
            key={labels[i]}
            style={
              { "--stage-color": `#${colors[i].toString(16)}` } as CSSProperties
            }
          >
            <span>
              <i />
              {labels[i]}
            </span>
            <strong>{group.length.toString().padStart(2, "0")}</strong>
          </div>
        ))}
      </div>
      <div className="scene-warehouses">
        {network.warehouses.map((warehouse) => (
          <button
            key={warehouse.id}
            className="text-button"
            onClick={() => onInspect(warehouse)}
          >
            <Truck size={13} />
            {warehouse.name}
          </button>
        ))}
      </div>
      <p className="scene-footnote">
        Arcs show assigned market links. Amber nodes mark active disruptions.
      </p>
    </section>
  );
}
