const nodes = [
  [74, 82], [158, 52], [244, 104], [332, 62], [426, 94], [522, 48],
  [620, 86], [724, 58], [824, 104], [930, 68], [1024, 98],
  [112, 180], [208, 154], [304, 202], [398, 160], [492, 214],
  [586, 158], [682, 206], [778, 164], [874, 218], [978, 172],
  [68, 280], [174, 248], [270, 296], [370, 254], [470, 304],
  [570, 258], [674, 292], [772, 250], [870, 302], [982, 264],
];

const links = [
  [0, 1], [0, 11], [0, 12], [1, 2], [1, 12], [2, 3], [2, 12], [2, 13],
  [3, 4], [3, 13], [3, 14], [4, 5], [4, 14], [4, 16], [5, 6], [5, 16],
  [6, 7], [6, 16], [6, 17], [7, 8], [7, 18], [8, 9], [8, 18], [8, 19],
  [9, 10], [9, 20], [10, 20], [11, 12], [11, 21], [11, 22], [12, 13],
  [12, 22], [13, 14], [13, 23], [14, 15], [14, 24], [15, 16], [15, 25],
  [16, 17], [16, 26], [17, 18], [17, 27], [18, 19], [18, 28], [19, 20],
  [19, 29], [20, 30], [21, 22], [22, 23], [23, 24], [24, 25], [25, 26],
  [26, 27], [27, 28], [28, 29], [29, 30], [1, 13], [5, 17], [12, 24],
  [16, 28], [20, 29],
];

const activeLinks = [[21, 22], [22, 23], [23, 24], [24, 25], [25, 16], [16, 6]];

export default function KnowledgeGraph({ className = '' }) {
  return (
    <svg
      className={`knowledge-graph ${className}`}
      viewBox="0 0 1080 350"
      role="img"
      aria-label="论文、概念和研究主题组成的动态知识网络"
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        <linearGradient id="graph-active-line" x1="0" x2="1">
          <stop offset="0" stopColor="#8b91ff" />
          <stop offset="0.52" stopColor="#65c7c2" />
          <stop offset="1" stopColor="#d58cff" />
        </linearGradient>
        <radialGradient id="graph-node-fill">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.28" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0" />
        </radialGradient>
      </defs>

      <g className="graph-links">
        {links.map(([from, to]) => (
          <line
            key={`${from}-${to}`}
            x1={nodes[from][0]}
            y1={nodes[from][1]}
            x2={nodes[to][0]}
            y2={nodes[to][1]}
          />
        ))}
      </g>

      <g className="graph-active-links">
        {activeLinks.map(([from, to], index) => (
          <line
            key={`${from}-${to}`}
            style={{ '--graph-delay': `${index * -0.42}s` }}
            x1={nodes[from][0]}
            y1={nodes[from][1]}
            x2={nodes[to][0]}
            y2={nodes[to][1]}
          />
        ))}
      </g>

      <g className="graph-nodes">
        {nodes.map(([x, y], index) => (
          <g
            key={`${x}-${y}`}
            className={activeLinks.flat().includes(index) ? 'active' : ''}
            style={{ '--graph-delay': `${(index % 9) * -0.35}s` }}
          >
            <circle className="graph-node-aura" cx={x} cy={y} r="13" />
            <circle className="graph-node-core" cx={x} cy={y} r="3.5" />
          </g>
        ))}
      </g>
    </svg>
  );
}
