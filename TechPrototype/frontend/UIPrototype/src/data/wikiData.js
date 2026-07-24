export const wikiConcepts = [
  {
    id: 'transformer',
    name: 'Transformer',
    category: '模型架构',
    description:
      '一种完全基于注意力机制的编码器-解码器架构，用于捕获序列中不同位置之间的全局依赖关系。',
    aliases: ['Self-Attention Network', 'Attention-based Model'],
    mentions: 128,
    paperCount: 24,
    trend: 86,
    updatedAt: '2026-07-07',
    keywords: ['attention', 'encoder-decoder', 'sequence modeling'],
    summaryPoints: [
      '用自注意力替代循环和卷积结构，支持高度并行的序列建模。',
      '多头注意力负责捕获不同表示子空间里的依赖关系。',
      '位置编码为无递归结构提供 token 顺序信息。',
    ],
    papers: [
      {
        id: '1706.03762',
        title: 'Attention Is All You Need',
        year: 2017,
        role: '提出核心架构',
      },
      {
        id: '1810.04805',
        title: 'BERT: Pre-training of Deep Bidirectional Transformers',
        year: 2018,
        role: '用于双向语言表示预训练',
      },
      {
        id: '2010.11929',
        title: 'An Image is Worth 16x16 Words',
        year: 2020,
        role: '扩展到视觉分类任务',
      },
    ],
    related: [
      { id: 'self-attention', type: '核心机制', strength: 96 },
      { id: 'multi-head-attention', type: '组成模块', strength: 91 },
      { id: 'bert', type: '代表模型', strength: 78 },
      { id: 'vision-transformer', type: '跨模态扩展', strength: 72 },
    ],
  },
  {
    id: 'self-attention',
    name: 'Self-Attention',
    category: '核心机制',
    description:
      '在同一序列内部计算 token 之间的相关性，使每个位置能够聚合全局上下文信息。',
    aliases: ['自注意力', 'Intra-Attention'],
    mentions: 114,
    paperCount: 21,
    trend: 82,
    updatedAt: '2026-07-06',
    keywords: ['query', 'key', 'value', 'context'],
    summaryPoints: [
      '通过 Query、Key、Value 三组表示计算注意力权重。',
      '能够直接建模远距离依赖，降低序列长度带来的路径问题。',
      '计算复杂度通常与序列长度平方相关，是长上下文优化的重点。',
    ],
    papers: [
      {
        id: '1706.03762',
        title: 'Attention Is All You Need',
        year: 2017,
        role: '定义缩放点积注意力',
      },
      {
        id: '2009.06732',
        title: 'Efficient Transformers: A Survey',
        year: 2020,
        role: '总结高效注意力变体',
      },
    ],
    related: [
      { id: 'transformer', type: '所属架构', strength: 96 },
      { id: 'multi-head-attention', type: '并行扩展', strength: 89 },
      { id: 'long-context', type: '优化方向', strength: 66 },
    ],
  },
  {
    id: 'multi-head-attention',
    name: 'Multi-Head Attention',
    category: '核心机制',
    description:
      '将多组注意力头并行计算后拼接投影，让模型在不同表示子空间中学习互补关系。',
    aliases: ['MHA', '多头注意力'],
    mentions: 76,
    paperCount: 16,
    trend: 68,
    updatedAt: '2026-07-05',
    keywords: ['attention heads', 'projection', 'parallel attention'],
    summaryPoints: [
      '每个头独立学习一组 Query、Key、Value 投影。',
      '多个注意力头能同时捕获语法、语义和位置等不同关系。',
      '头数、维度和稀疏化策略会影响计算成本与表达能力。',
    ],
    papers: [
      {
        id: '1706.03762',
        title: 'Attention Is All You Need',
        year: 2017,
        role: '提出多头注意力模块',
      },
      {
        id: '1905.10650',
        title: 'Analyzing Multi-Head Self-Attention',
        year: 2019,
        role: '分析注意力头行为',
      },
    ],
    related: [
      { id: 'transformer', type: '组成模块', strength: 91 },
      { id: 'self-attention', type: '机制扩展', strength: 89 },
      { id: 'bert', type: '广泛使用', strength: 74 },
    ],
  },
  {
    id: 'rag',
    name: 'Retrieval-Augmented Generation',
    category: '应用范式',
    description:
      '在生成回答前检索外部知识，将相关文档或片段注入上下文，以提升事实性和可追溯性。',
    aliases: ['RAG', '检索增强生成'],
    mentions: 92,
    paperCount: 18,
    trend: 88,
    updatedAt: '2026-07-07',
    keywords: ['retrieval', 'grounding', 'question answering'],
    summaryPoints: [
      '通常包含查询改写、向量检索、重排序和答案生成步骤。',
      '适合论文问答、知识库问答和需要引用来源的场景。',
      '质量依赖语料切分、召回覆盖、上下文压缩和引用校验。',
    ],
    papers: [
      {
        id: '2005.11401',
        title: 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks',
        year: 2020,
        role: '提出 RAG 框架',
      },
      {
        id: '2406.01234',
        title: 'Retrieval-Augmented Agents for Scientific Literature Review',
        year: 2026,
        role: '用于科学文献综述',
      },
    ],
    related: [
      { id: 'knowledge-graph', type: '结构化检索', strength: 84 },
      { id: 'concept-graph', type: '知识组织', strength: 77 },
      { id: 'paper-qa', type: '应用场景', strength: 81 },
    ],
  },
  {
    id: 'concept-graph',
    name: 'Concept Graph',
    category: '知识组织',
    description:
      '从论文中抽取概念、方法、任务和结论，并用边描述它们之间的依赖、包含和对比关系。',
    aliases: ['概念图谱', 'Research Concept Graph'],
    mentions: 58,
    paperCount: 11,
    trend: 74,
    updatedAt: '2026-07-04',
    keywords: ['entity extraction', 'relation extraction', 'knowledge map'],
    summaryPoints: [
      '将非结构化论文内容转成可浏览、可检索的知识节点。',
      '关系类型通常包括提出、改进、依赖、应用和对比。',
      '可作为 Wiki、推荐、研究脉络分析和问答引用的基础。',
    ],
    papers: [
      {
        id: '2406.05678',
        title: 'Concept Graph Construction from Research Papers',
        year: 2026,
        role: '提出论文概念图谱构建流程',
      },
      {
        id: '2106.01342',
        title: 'Scientific Knowledge Graph Construction',
        year: 2021,
        role: '科学知识图谱构建综述',
      },
    ],
    related: [
      { id: 'knowledge-graph', type: '上位概念', strength: 86 },
      { id: 'rag', type: '检索支撑', strength: 77 },
      { id: 'topic-aware-embedding', type: '节点表示', strength: 69 },
    ],
  },
  {
    id: 'topic-aware-embedding',
    name: 'Topic-Aware Embedding',
    category: '表示学习',
    description:
      '在文本向量表示中注入主题信息，让相近研究方向、方法和任务在语义空间中更容易聚合。',
    aliases: ['Topic Embedding', '主题感知向量'],
    mentions: 41,
    paperCount: 9,
    trend: 61,
    updatedAt: '2026-07-03',
    keywords: ['embedding', 'topic modeling', 'semantic search'],
    summaryPoints: [
      '可结合标题、摘要、关键词、分类和引用上下文生成向量。',
      '适合论文聚类、相似论文推荐和主题趋势分析。',
      '与普通语义向量相比，更强调研究领域和任务边界。',
    ],
    papers: [
      {
        id: '2406.09123',
        title: 'Automatic Paper Classification with Topic-Aware Embeddings',
        year: 2026,
        role: '用于论文自动分类',
      },
      {
        id: '2212.09748',
        title: 'Topic Modeling in Embedding Spaces',
        year: 2022,
        role: '讨论主题与向量空间关系',
      },
    ],
    related: [
      { id: 'concept-graph', type: '节点表示', strength: 69 },
      { id: 'semantic-search', type: '检索技术', strength: 75 },
      { id: 'paper-recommendation', type: '应用场景', strength: 73 },
    ],
  },
  {
    id: 'bert',
    name: 'BERT',
    category: '代表模型',
    description:
      '基于 Transformer Encoder 的双向语言表示模型，通过 MLM 和 NSP 任务进行预训练。',
    aliases: ['Bidirectional Encoder Representations from Transformers'],
    mentions: 87,
    paperCount: 15,
    trend: 64,
    updatedAt: '2026-07-02',
    keywords: ['pre-training', 'MLM', 'encoder'],
    summaryPoints: [
      '使用双向上下文建模提升自然语言理解任务效果。',
      '预训练后可通过任务头微调用于分类、问答和序列标注。',
      '后续 RoBERTa、ALBERT 等模型对训练目标和参数效率做了改进。',
    ],
    papers: [
      {
        id: '1810.04805',
        title: 'BERT: Pre-training of Deep Bidirectional Transformers',
        year: 2018,
        role: '提出 BERT 模型',
      },
      {
        id: '1907.11692',
        title: 'RoBERTa: A Robustly Optimized BERT Pretraining Approach',
        year: 2019,
        role: '改进预训练策略',
      },
    ],
    related: [
      { id: 'transformer', type: '基础架构', strength: 78 },
      { id: 'self-attention', type: '核心机制', strength: 71 },
      { id: 'multi-head-attention', type: '组成模块', strength: 74 },
    ],
  },
  {
    id: 'knowledge-graph',
    name: 'Knowledge Graph',
    category: '知识组织',
    description:
      '用实体和关系组织领域知识，支持关联发现、路径推理、检索增强和可解释推荐。',
    aliases: ['KG', '知识图谱'],
    mentions: 63,
    paperCount: 13,
    trend: 70,
    updatedAt: '2026-07-01',
    keywords: ['entity', 'relation', 'reasoning'],
    summaryPoints: [
      '节点表示论文、概念、作者、任务、方法或数据集等实体。',
      '边可以表达引用、依赖、提出、改进和应用关系。',
      '结合向量检索后可同时支持精确关系查询和语义召回。',
    ],
    papers: [
      {
        id: '2106.01342',
        title: 'Scientific Knowledge Graph Construction',
        year: 2021,
        role: '科学知识图谱构建方法',
      },
      {
        id: '2401.00005',
        title: 'Retrieval-Augmented Generation with Knowledge Graphs for Fact-Checking',
        year: 2024,
        role: 'KG 与 RAG 结合',
      },
    ],
    related: [
      { id: 'concept-graph', type: '细分形态', strength: 86 },
      { id: 'rag', type: '增强检索', strength: 84 },
      { id: 'semantic-search', type: '互补检索', strength: 68 },
    ],
  },
];

export const wikiActivity = [
  {
    id: 'a1',
    title: '新增 RAG 与知识图谱关联',
    description: '从 2 篇论文中抽取了检索增强生成与知识图谱的组合用法。',
    time: '2026-07-07 18:20',
    color: 'blue',
  },
  {
    id: 'a2',
    title: '更新 Transformer 概念摘要',
    description: '补充 Vision Transformer 和 BERT 的关联路径。',
    time: '2026-07-07 12:10',
    color: 'green',
  },
  {
    id: 'a3',
    title: '合并 4 个重复别名',
    description: '将 Topic Embedding 和 Topic-Aware Embedding 归并为同一概念。',
    time: '2026-07-06 09:45',
    color: 'gold',
  },
];

export const wikiCategoryOptions = [
  '全部',
  ...Array.from(new Set(wikiConcepts.map((concept) => concept.category))),
];

export function getConceptById(conceptId) {
  return wikiConcepts.find((concept) => concept.id === conceptId);
}

export function getRelatedConcepts(concept) {
  if (!concept) return [];

  return concept.related.map((relation) => ({
    ...relation,
    exists: Boolean(getConceptById(relation.id)),
    concept: getConceptById(relation.id) || {
      id: relation.id,
      name: relation.id,
      category: '未分类',
      description: '该概念仍在抽取和整理中。',
    },
  }));
}

export function getWikiStats() {
  const paperIds = new Set();

  wikiConcepts.forEach((concept) => {
    concept.papers.forEach((paper) => paperIds.add(paper.id));
  });

  return {
    concepts: wikiConcepts.length,
    papers: paperIds.size,
    relations: wikiConcepts.reduce(
      (total, concept) => total + concept.related.length,
      0,
    ),
    strongRelations: wikiConcepts.reduce(
      (total, concept) =>
        total + concept.related.filter((relation) => relation.strength >= 80).length,
      0,
    ),
  };
}
