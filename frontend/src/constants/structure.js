// 论文结构面板配置 —— 从旧 static/index.html 原样搬运。

export const STRUCTURE_BADGE_CFG = {
  thesis_title: { label: '论文题目', color: '#1d4ed8', bg: 'rgba(59,130,246,0.12)' },
  abstract_h: { label: '摘要', color: '#0f766e', bg: 'rgba(20,184,166,0.12)' },
  keywords_h: { label: '关键词', color: '#b45309', bg: 'rgba(245,158,11,0.12)' },
  en_title: { label: 'EN题目', color: '#1d4ed8', bg: 'rgba(99,102,241,0.12)' },
  en_abstract_h: { label: 'Abstract', color: '#0f766e', bg: 'rgba(20,184,166,0.12)' },
  en_keywords_h: { label: 'Keywords', color: '#b45309', bg: 'rgba(245,158,11,0.12)' },
  toc_h: { label: '目录', color: '#7c3aed', bg: 'rgba(139,92,246,0.12)' },
  intro_h1: { label: '引言', color: '#1e293b', bg: 'rgba(30,41,59,0.12)' },
  conclusion_h1: { label: '结论', color: '#1e293b', bg: 'rgba(30,41,59,0.12)' },
  heading_1: { label: 'H1', color: '#1e293b', bg: 'rgba(30,41,59,0.12)' },
  heading_2: { label: 'H2', color: '#475569', bg: 'rgba(71,85,105,0.10)' },
  heading_3: { label: 'H3', color: '#64748b', bg: 'rgba(100,116,139,0.10)' },
  heading_4: { label: 'H4', color: '#94a3b8', bg: 'rgba(148,163,184,0.10)' },
  heading_5: { label: 'H5', color: '#94a3b8', bg: 'rgba(148,163,184,0.10)' },
  heading_6: { label: 'H6', color: '#94a3b8', bg: 'rgba(148,163,184,0.10)' },
  figure_caption: { label: '图', color: '#0369a1', bg: 'rgba(14,165,233,0.12)' },
  table_caption: { label: '表', color: '#065f46', bg: 'rgba(5,150,105,0.12)' },
  equation: { label: '公式', color: '#9333ea', bg: 'rgba(147,51,234,0.10)' },
  acknowledgment: { label: '致谢', color: '#be185d', bg: 'rgba(236,72,153,0.10)' },
  references: { label: '参考文献', color: '#0891b2', bg: 'rgba(8,145,178,0.12)' },
  appendix: { label: '附录', color: '#64748b', bg: 'rgba(100,116,139,0.10)' },
};

export const STRUCTURE_INDENT = {
  heading_2: 12,
  heading_3: 24,
  heading_4: 36,
  heading_5: 48,
  heading_6: 60,
};

export const SECTION_LABELS = {
  cover: { zh: '封面', color: '#1d4ed8' },
  front_matter: { zh: '前置', color: '#0f766e' },
  body: { zh: '正文', color: '#1e293b' },
  back_matter: { zh: '后置', color: '#7c3aed' },
};

export const SECTION_ORDER = ['cover', 'front_matter', 'body', 'back_matter'];

export const INLINE_TYPES = new Set([
  'figure_caption',
  'table_caption',
  'equation',
]);
