// The one orchestrated moment: seedlings grow out of the soil layers (CSS animation, see globals.css).

const STEMS: Array<[number, number, number]> = [
  [70, 92, 0.5], [180, 64, 0.2], [290, 104, 0.65], [400, 70, 0.35], [510, 98, 0.1], [620, 60, 0.45], [730, 92, 0.25],
  [840, 66, 0.55], [950, 100, 0.15], [1060, 62, 0.4], [1170, 96, 0.6], [1280, 68, 0.3], [1390, 102, 0.05], [1500, 74, 0.5],
];

export function Sprouts() {
  return (
    <svg className="field" viewBox="0 0 1600 240" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
      <g className="stems">
        {STEMS.map(([x, top, delay]) => (
          <g key={x} style={{ "--d": `${delay}s` } as React.CSSProperties}>
            <path className="stem" pathLength={1} d={`M${x} 168 C${x} ${168 - (168 - top) * 0.45}, ${x + 6} ${top + 30}, ${x + 3} ${top}`} />
            <path className="leaf" d={`M${x + 3} ${top} q 26 -20 46 -4 q -20 22 -46 4z`} />
            <path className="leaf leaf-b" d={`M${x + 3} ${top + 26} q -26 -18 -44 -2 q 20 20 44 2z`} />
          </g>
        ))}
      </g>
      <path className="soil soil-1" d="M0 168 C240 160 520 176 800 168 S1360 160 1600 170 V240 H0Z" />
      <path className="soil soil-2" d="M0 190 C280 182 600 198 880 190 S1400 184 1600 192 V240 H0Z" />
      <path className="soil soil-3" d="M0 214 C320 208 640 220 920 214 S1440 210 1600 216 V240 H0Z" />
    </svg>
  );
}
