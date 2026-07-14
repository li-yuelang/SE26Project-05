export const dailyDigest = {
  date: '2026-07-09',
  summary: '今日共追踪到你关注的 5 个主题中有 12 篇新增论文，其中 3 篇与你的阅读历史高度相关，建议优先阅读。',
  topics: [
    {
      topicId: 'rag', topicName: 'Retrieval-Augmented Generation', newCount: 5,
      highlights: [
        { id: '2501.01001', title: 'RAG with Multi-Hop Evidence Retrieval for Scientific QA', authors: ['Jun Wang', 'Alice Chen'], categories: ['cs.CL', 'cs.AI'], matchScore: 94, reason: '与你近期阅读的 Agent 检索链高度相关', abstract: '提出多跳证据检索增强生成框架，通过迭代查询分解和证据链构建，提升科学问答中的复杂推理能力。' },
        { id: '2501.01002', title: 'Citation-Aware RAG: Grounding LLM Answers with Paper Evidence', authors: ['Bo Wang', 'Carol Smith'], categories: ['cs.CL'], matchScore: 88, reason: '与问答出处定位研究方向匹配', abstract: '在 RAG 流程中引入引用感知机制，确保生成答案可追溯到具体论文段落，降低幻觉率。' },
      ],
    },
    { topicId: 'concept-graph', topicName: '论文概念图谱', newCount: 2, highlights: [{ id: '2501.02001', title: 'Iterative Concept Graph Refinement via Section-Aware Parsing', authors: ['David Liu', 'Emma Brown'], categories: ['cs.CL', 'cs.IR'], matchScore: 91, reason: '与你关注的章节解析和概念合并策略一致', abstract: '通过章节结构感知解析和迭代归并，构建高质量学术概念图谱，减少重复节点和错误关系。' }] },
    { topicId: 'paper-recommendation', topicName: '个性化论文推荐', newCount: 1, highlights: [{ id: '2501.03001', title: 'Collaborative Filtering Meets Semantic Search for ArXiv Papers', authors: ['Olivia Martin', 'Hao Chen'], categories: ['cs.IR'], matchScore: 79, reason: '与阅读行为建模研究相关', abstract: '结合协同过滤和语义搜索的混合推荐方法，在 ArXiv 数据集上取得优于纯协同或纯语义方法的效果。' }] },
    { topicId: 'llm-finetuning', topicName: '大模型高效微调', newCount: 3, highlights: [{ id: '2501.04001', title: 'Dynamic LoRA Allocation with Importance Ranking', authors: ['Sarah Chen', 'Raj Patel'], categories: ['cs.LG', 'cs.CL'], matchScore: 86, reason: '与你已读的 Adaptive LoRA 论文延续性很强', abstract: '提出基于参数重要性排名的动态 LoRA 秩分配策略，在更少的可训练参数下实现更优的领域适配效果。' }] },
    { topicId: 'qa', topicName: '科学问答与引用定位', newCount: 1, highlights: [{ id: '2501.05001', title: 'Long-Range Citation Grounding for Multi-Paper QA', authors: ['Nora Kim', 'Ivan Petrov'], categories: ['cs.CL'], matchScore: 82, reason: '与 Long-Context Scientific QA 方法论互补', abstract: '面向多论文场景的长距离引用定位方法，在 Qasper 和 PaperQA 基准上显著提升答案可验证性。' }] },
  ],
};

export const historyBasedRecommendations = [
  { id: '2502.06001', title: 'Self-Evolving Agent Architectures for Continuous Literature Monitoring', authors: ['Alice Chen', 'David Liu'], categories: ['cs.AI', 'cs.CL'], matchScore: 93, sourcePaperId: '2406.01234', sourcePaperTitle: 'Retrieval-Augmented Agents for Scientific Literature Review', reason: '基于你阅读的 RAG Agent 论文，该工作将检索增强智能体从单次综述扩展为持续监听框架', abstract: '提出一种自进化智能体架构，可持续监听新发表文献，自动更新知识库和综述摘要。' },
  { id: '2502.06002', title: 'Multi-Granularity Concept Alignment Across Research Communities', authors: ['Emma Brown', 'David Liu'], categories: ['cs.CL', 'cs.IR'], matchScore: 89, sourcePaperId: '2406.05678', sourcePaperTitle: 'Concept Graph Construction from Research Papers', reason: '基于你阅读的概念图谱论文，该工作解决了跨社区概念对齐和归并问题', abstract: '提出多粒度概念对齐方法，桥接不同研究社区对相似概念的命名差异，提升知识图谱互操作性。' },
  { id: '2502.06003', title: 'Behavior-Aware Cold-Start Recommendation via Topic Priors', authors: ['Olivia Martin', 'Grace Miller'], categories: ['cs.IR', 'cs.HC'], matchScore: 85, sourcePaperId: '2404.06543', sourcePaperTitle: 'Reading Behavior Modeling for Personalized Paper Recommendation', reason: '基于你阅读的推荐建模论文，该工作解决了冷启动推荐的难题', abstract: '利用显式主题订阅作为先验信息，为新用户提供可靠推荐，并在行为数据积累后平滑过渡到行为模型。' },
  { id: '2502.06004', title: 'Reasoning over Citation Graphs with Hierarchical Attention', authors: ['Nora Kim', 'Maya Singh'], categories: ['cs.CL'], matchScore: 83, sourcePaperId: '2405.11890', sourcePaperTitle: 'Long-Context Scientific Question Answering with Citation Grounding', reason: '基于你阅读的引用定位论文，该工作引入层次注意力机制提升引用图推理', abstract: '提出层次注意力引用图推理方法，在问答中同时考虑引用关系和段落内容，提升推理深度。' },
  { id: '2502.06005', title: 'Sparse-Gated Mixture of LoRA Experts for Multi-Domain Adaptation', authors: ['Raj Patel', 'Sarah Chen'], categories: ['cs.LG', 'cs.CL'], matchScore: 81, sourcePaperId: '2405.08777', sourcePaperTitle: 'Adaptive LoRA for Efficient Domain Adaptation of Large Language Models', reason: '基于你关注的 LoRA 微调方向，该工作探索多领域适配', abstract: '使用稀疏门控混合专家机制，让多个 LoRA 模块协同工作，实现单模型多领域高效适配。' },
];
