import { getDateDaysAgo } from '../utils/date';

export const chatConversations = [
  { id: '1', title: 'Transformer 架构讨论', date: getDateDaysAgo(0), preview: '关于注意力机制的深入探讨…' },
  { id: '2', title: 'BERT 预训练方法对比', date: getDateDaysAgo(1), preview: 'MLM 与 NSP 任务的区别与应用…' },
  { id: '3', title: '大模型微调技术', date: getDateDaysAgo(2), preview: 'LoRA 和 P-Tuning 的效率对比…' },
  { id: '4', title: '图神经网络综述', date: getDateDaysAgo(3), preview: 'GCN、GAT、GraphSAGE 的关系…' },
  { id: '5', title: '扩散模型原理', date: getDateDaysAgo(4), preview: 'DDPM 与 Score-based 统一视角…' },
];

export const chatMessages = {
  1: [
    { role: 'user', content: '什么是 Transformer 中的自注意力机制？', time: '10:30' },
    {
      role: 'assistant',
      content:
        '自注意力机制（Self-Attention）是 Transformer 架构的核心组件。它允许序列中的每个位置关注所有位置，通过 Query、Key、Value 三个矩阵计算注意力权重，从而捕获全局依赖关系。\n\n核心公式：Attention(Q,K,V) = softmax(QK^T/√d_k)V\n\n与 RNN 不同，自注意力完全并行计算，大幅提升了训练效率。',
      time: '10:30',
      sources: [
        { title: 'Attention Is All You Need', paperId: '1706.03762' },
        { title: 'The Annotated Transformer', paperId: '1706.03762' },
      ],
    },
  ],
  2: [
    { role: 'user', content: 'BERT 的 MLM 和 NSP 任务分别是什么？', time: '昨天 14:20' },
    {
      role: 'assistant',
      content:
        'MLM（Masked Language Model）：随机遮盖输入中 15% 的 token，让模型预测被遮盖的词，迫使模型学习双向上下文。\n\nNSP（Next Sentence Prediction）：判断两个句子是否为连续文本，帮助模型理解句子间关系。\n\n后续研究（如 RoBERTa）表明 NSP 并非必要，仅用 MLM 也能取得更好效果。',
      time: '昨天 14:20',
      sources: [
        { title: 'BERT: Pre-training of Deep Bidirectional Transformers', paperId: '1810.04805' },
      ],
    },
  ],
};

export const chatSuggestions = [
  '什么是 Transformer 中的自注意力机制？',
  'BERT 和 GPT 的主要区别是什么？',
  'LoRA 微调的原理是什么？',
];
