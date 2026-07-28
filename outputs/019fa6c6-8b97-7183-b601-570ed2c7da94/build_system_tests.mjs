import fs from 'node:fs/promises';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const outputDir = '/Users/mac/CodeField/SE26Project-05/outputs/019fa6c6-8b97-7183-b601-570ed2c7da94';
const outputPath = `${outputDir}/论文知识系统_系统测试用例_已填写.xlsx`;

const workbook = Workbook.create();
const infoSheet = workbook.worksheets.add('Information');
const testSheet = workbook.worksheets.add('Test Cases');
const methodSheet = workbook.worksheets.add('常用测试方法');

const cases = [
  ['论文抓取范围配置', '功能测试', '按学科或关键词配置抓取范围', '高', '管理员已登录；arXiv服务可访问', '1.新建抓取规则，选择学科cs.AI并填写关键词“knowledge graph”；\n2.保存并启用规则；\n3.执行一次抓取。', '规则保存成功；仅入库符合学科或关键词条件的论文；规则可停用、修改。', 'FR-1.1'],
  ['定时抓取任务', '功能测试', '按设定周期自动从arXiv抓取论文', '高', '已启用抓取规则；调度服务正常', '1.设置每日定时任务；\n2.等待调度时间或推进测试时钟；\n3.查看任务日志与新增论文。', '任务按时启动并结束；日志记录开始、结束、抓取数和异常；符合条件的新论文入库。', 'FR-1.1'],
  ['论文元数据入库', '功能测试', '完整保存和展示论文基本信息', '高', '存在包含完整元数据的arXiv论文', '1.抓取目标论文；\n2.打开论文列表和详情页；\n3.核对标题、作者、摘要、类别、发布时间、原文链接。', '六类基本信息均正确保存并展示；原文链接可访问；作者顺序与来源一致。', 'FR-1.2'],
  ['多维分类管理', '功能测试', '按主题、作者和时间分类浏览论文', '高', '知识库已有跨主题、跨作者、跨年份论文', '1.分别进入主题、作者、时间分类；\n2.选择一个分类；\n3.核对结果集。', '分类入口可用；每类结果与论文元数据一致；切换分类不会产生重复记录。', 'FR-1.1'],
  ['精确去重', '功能测试', '相同arXiv ID论文重复抓取不重复入库', '高', '目标论文已入库', '1.再次执行覆盖该论文的抓取任务；\n2.查询该arXiv ID；\n3.检查抓取日志。', '库中仍只有一条记录；允许更新变更的元数据；日志标识为重复或更新。', 'FR-1.1'],
  ['近似重复识别', '功能测试', '同一论文不同链接或版本的去重处理', '高', '准备标题近似且DOI/作者一致的两条来源数据', '1.依次导入两个来源；\n2.查看论文列表；\n3.检查版本信息。', '系统识别为同一论文并合并或建立版本关系；不生成两个独立主记录。', 'FR-1.1'],
  ['PDF结构化解析', '功能测试', '从PDF生成summary.md', '高', '论文PDF可下载且文本可解析', '1.触发论文解析；\n2.等待任务完成；\n3.打开summary.md。', '生成非空summary.md；内容覆盖研究背景、问题、方法和主要结论；与原文一致。', 'FR-2.1'],
  ['HTML结构化解析', '功能测试', '从HTML正文生成summary.md', '高', '论文存在可解析HTML页面', '1.选择HTML作为解析源；\n2.触发解析；\n3.打开summary.md并核对章节。', 'HTML正文被正确提取；生成summary.md；导航、脚注等噪声不进入核心摘要。', 'FR-2.1'],
  ['概念文档生成', '功能测试', '自动生成concept.md并提取核心概念', '高', '论文解析成功', '1.打开concept.md；\n2.核对核心概念、定义与原文位置；\n3.检查概念标签。', 'concept.md生成成功；核心概念、解释和来源位置完整；概念标签可用于检索。', 'FR-2.1/2.2'],
  ['方法文档生成', '功能测试', '自动生成methods.md并提取研究方法', '高', '论文解析成功且含方法章节', '1.打开methods.md；\n2.核对方法名称、步骤、数据集和评价指标；\n3.点击来源定位。', 'methods.md结构清晰；方法要素与原文一致；来源定位可跳转到对应页或段落。', 'FR-2.1/2.2'],
  ['知识要素抽取', '功能测试', '抽取研究问题、方法和实验结论', '高', '准备带人工标注答案的论文样本', '1.执行知识抽取；\n2.查看结构化字段；\n3.与人工标注逐项比对。', '研究问题、方法、实验设置、结论均有结构化结果；缺失信息不臆造。', 'FR-2.2'],
  ['概念关联建立', '功能测试', '建立论文内及跨论文概念关联', '高', '至少两篇论文包含相同或上下位概念', '1.完成两篇论文解析；\n2.打开概念关系视图；\n3.检查关系类型及来源。', '生成合理的同义、上下位或相关关系；每条关系可追溯到论文与内容位置。', 'FR-2.2'],
  ['解析异常处理', '功能测试', '损坏或扫描型PDF解析失败可见且可重试', '中', '准备损坏PDF和无OCR文本PDF', '1.分别提交解析；\n2.观察状态与提示；\n3.修复文件后点击重试。', '任务不假成功；显示明确失败原因；重试后可恢复；已生成内容不被错误覆盖。', 'FR-2.1'],
  ['标题检索', '功能测试', '按完整或部分标题检索论文', '高', '知识库已有目标论文', '1.输入完整标题检索；\n2.输入连续部分标题检索；\n3.输入不存在标题。', '完整和部分标题均命中目标；结果高亮关键词；不存在时返回空态而非错误。', 'FR-3.1'],
  ['作者检索', '功能测试', '按作者姓名检索论文', '高', '知识库包含同名及多作者论文', '1.输入作者全名；\n2.输入姓名片段；\n3.核对多作者论文。', '返回该作者相关论文；多作者论文不遗漏；结果可继续筛选和排序。', 'FR-3.1'],
  ['多条件检索', '功能测试', '按关键词、研究方向和概念标签组合检索', '高', '知识库已有多主题和多标签论文', '1.分别按关键词、研究方向、概念标签检索；\n2.组合两个以上条件；\n3.清除筛选。', '单条件结果正确；组合条件按界面约定的逻辑过滤；清除后恢复完整结果。', 'FR-3.1'],
  ['结果排序分页', '功能测试', '检索结果按时间和相关度排序并分页', '中', '检索结果超过一页', '1.切换相关度/发布时间排序；\n2.翻页；\n3.返回上一页。', '排序顺序正确且稳定；翻页无重复、无遗漏；筛选条件与页码状态符合设计。', 'FR-3.1'],
  ['论文详情查看', '功能测试', '查看论文详情及结构化知识内容', '高', '目标论文已完成解析', '1.从结果列表打开详情；\n2.查看元数据、摘要、概念和方法；\n3.打开原文链接。', '详情内容完整；结构化文档可切换；原文链接正确；不存在字段有明确空态。', 'FR-1.2/3.1'],
  ['引用关系查看', '功能测试', '查看论文之间的引用关系', '高', '知识库中存在已知引用链', '1.打开目标论文关系视图；\n2.查看引用与被引论文；\n3.点击节点跳转。', '引用方向正确；关系节点不重复；点击可进入对应论文详情；缺失论文有合理占位。', 'FR-3.2'],
  ['主题与概念关系查看', '功能测试', '查看论文的主题关联和概念关联', '高', '多篇论文已有主题和概念关系', '1.切换主题关联视图；\n2.切换概念关联视图；\n3.按关系类型筛选。', '两类关系均正确显示；节点和边可识别；筛选结果与后台关系数据一致。', 'FR-3.2'],
  ['论文内容问答', '功能测试', '围绕论文内容提问并返回有出处的答案', '高', '目标论文已入库并建立索引', '1.选择目标论文；\n2.询问其主要贡献；\n3.查看答案引用。', '答案基于论文内容；至少给出论文标题及页码/章节/段落定位；引用可打开。', 'FR-4.1/4.2'],
  ['概念解释问答', '功能测试', '询问核心概念并结合论文语境解释', '高', '知识库包含目标概念及关联论文', '1.询问“论文中的目标概念是什么”；\n2.继续追问与相关概念的区别；\n3.查看出处。', '回答说明概念及语境；追问保持上下文；每个关键结论有可核验出处。', 'FR-4.1/4.2'],
  ['方法与研究脉络问答', '功能测试', '比较研究方法并回答研究脉络问题', '高', '知识库有同主题多篇论文', '1.询问两篇论文方法差异；\n2.询问该主题方法演进；\n3.检查引用清单。', '答案包含可核对的比较维度和时间脉络；不混淆论文；引用覆盖关键判断。', 'FR-4.1/AR-1'],
  ['内容定位', '功能测试', '从问答引用跳转到对应原文位置', '高', '问答已返回至少一条引用', '1.点击引用；\n2.核对打开的论文及页码/段落；\n3.返回问答页面。', '定位到支持该答案的原文内容；高亮或上下文足以核验；返回后会话保留。', 'FR-4.2'],
  ['无依据问题处理', '功能测试', '知识库无充分证据时拒绝臆造', '高', '知识库不包含问题所需事实', '1.提出知识库外的具体事实问题；\n2.要求给出出处；\n3.观察回答。', '明确说明证据不足或未收录；不生成虚假论文或定位；可建议相关检索。', 'FR-4.2'],
  ['论文收藏', '功能测试', '收藏和取消收藏论文', '高', '用户已登录；目标论文存在', '1.在列表收藏论文；\n2.进入收藏列表核对；\n3.取消收藏。', '收藏状态跨页面一致且持久化；收藏列表出现目标论文；取消后移除且不删除论文。', 'FR-5.1'],
  ['论文笔记', '功能测试', '新增、编辑和删除论文笔记', '高', '用户已登录；目标论文存在', '1.新增含多行文本的笔记；\n2.编辑并保存；\n3.删除笔记。', '各操作成功且内容正确；刷新后仍保留；删除前有确认；笔记仅对授权用户可见。', 'FR-5.1'],
  ['论文评论', '功能测试', '发表评论并查看评论列表', '中', '用户已登录；目标论文存在', '1.发表正常评论；\n2.刷新详情页；\n3.提交空评论和超长评论。', '正常评论显示作者和时间；刷新后保留；非法长度被校验且有提示。', 'FR-5.1'],
  ['对比阅读', '功能测试', '选择多篇论文进行对比阅读', '高', '至少三篇论文已完成解析', '1.从列表选择2至3篇论文；\n2.进入对比阅读；\n3.切换摘要、概念、方法维度。', '并排显示所选论文；维度切换同步；差异清晰；移除论文后布局正常。', 'FR-5.1'],
  ['阅读历史', '功能测试', '自动记录并管理阅读历史', '中', '用户已登录', '1.依次打开多篇论文；\n2.进入阅读历史；\n3.重复打开一篇论文。', '记录论文与最近阅读时间；按最近时间排序；重复阅读更新记录而非无限重复。', 'FR-5.2'],
  ['关注主题', '功能测试', '新增和取消关注研究主题', '中', '用户已登录；系统有主题数据', '1.关注一个主题；\n2.查看个人关注主题；\n3.取消关注。', '关注状态持久化；个人页显示该主题；取消后移除；不影响历史阅读数据。', 'FR-5.2'],
  ['研究脉络图', '功能测试', '自动生成研究主题发展脉络图', '高', '同一主题下有跨年份论文和引用关系', '1.选择研究主题；\n2.生成发展脉络；\n3.检查时间轴、节点和关系。', '脉络按时间组织；关键论文和演进关系可追溯；节点可跳转论文详情。', 'AR-1'],
  ['代表论文与趋势', '功能测试', '生成代表性论文列表和研究趋势分析', '高', '主题下数据量足以分析', '1.生成主题分析；\n2.查看代表论文排序依据；\n3.核对趋势区间和证据。', '输出代表论文列表、选择依据、趋势结论和数据范围；结论能追溯到论文或统计结果。', 'AR-1'],
  ['主题订阅', '功能测试', '创建、修改和取消研究主题订阅', '高', '用户已登录；通知渠道可用', '1.订阅主题并选择每日频率；\n2.修改关键词；\n3.取消订阅。', '订阅规则正确保存；修改后立即生效；取消后不再生成推送任务。', 'AR-2'],
  ['每日新增论文推送', '功能测试', '每日推送订阅主题的新增论文摘要', '高', '存在有效订阅；当天有新增论文', '1.触发每日推送任务；\n2.查看推送内容；\n3.再次执行同日任务。', '仅推送新增且匹配的论文；每篇包含标题、摘要和链接；同日重复任务不重复推送。', 'AR-2'],
  ['个性化推荐', '功能测试', '根据阅读历史推荐相关论文', '高', '用户有足够阅读历史；库中有候选论文', '1.阅读同主题多篇论文；\n2.打开推荐页；\n3.改变阅读主题后重新生成。', '推荐与近期兴趣相关；已读/重复项按规则处理；兴趣改变后结果有合理变化；可查看推荐理由。', 'AR-2'],
  ['解析准确率', '准确性测试', '结构化解析与知识抽取准确率不低于90%', '高', '准备不少于100篇含人工金标准的代表性论文', '1.批量执行解析与抽取；\n2.按统一评分规则比较标题层级、概念、问题、方法和结论；\n3.统计正确项/总评测项。', '总体准确率≥90%；各维度结果可复核；失败样本和评分明细可导出。', 'NFR-3'],
  ['检索准确率', '准确性测试', '多维检索准确率不低于90%', '高', '准备标注相关论文集合和不少于100条查询', '1.依次执行标题、作者、关键词、方向和标签查询；\n2.记录Top-K结果；\n3.按验收口径统计准确率。', '检索准确率≥90%；查询、命中结果和计算过程留痕；无明显跨用户数据混入。', 'NFR-3'],
  ['问答准确率', '准确性测试', '论文问答准确率不低于90%', '高', '准备覆盖内容、概念、方法和脉络的人工标注问答集', '1.批量提问；\n2.按答案正确性与引用支持性评分；\n3.统计通过题数/总题数。', '准确率≥90%；关键结论由正确出处支持；拒答样本按既定评分规则处理。', 'NFR-3'],
  ['检索并发性能', '性能测试', '100条以上数据和100并发下检索响应小于3秒', '高', '库中不少于100条论文元数据；性能环境稳定', '1.准备混合检索脚本；\n2.以100并发持续压测；\n3.统计服务端响应时间、错误率和资源。', '检索响应时间按验收统计口径<3s；无错误或数据错乱；资源使用无持续异常增长。', 'NFR-4'],
  ['问答链路并发性能', '性能测试', '100并发下问答非LLM链路响应小于3秒', '高', '知识索引已建立；可单独计量LLM外耗时', '1.100并发提交混合问题；\n2.扣除或隔离LLM推理耗时；\n3.统计检索、组装、引用定位耗时。', '非LLM部分响应时间<3s；请求隔离正确；无引用串线或会话串扰。', 'NFR-4'],
  ['学习管理并发性能', '性能测试', '100并发下学习管理操作响应小于3秒', '高', '准备100个测试用户和不少于100篇论文', '1.并发执行收藏、笔记、评论、历史查询；\n2.持续压测；\n3.核对响应和最终数据。', '各操作响应时间<3s；成功率符合验收标准；最终数据完整且无重复、丢失。', 'NFR-4'],
  ['抓取解析批处理性能', '性能测试', '批量抓取与解析不阻塞在线查询', '中', '准备批量论文任务和在线查询脚本', '1.启动批量抓取与解析；\n2.同时执行检索和学习管理；\n3.观察队列与在线响应。', '后台任务可排队和限流；在线功能保持可用；任务进度可查；无资源耗尽。', 'FR-1/2,NFR-4'],
  ['抓取任务幂等性', '可靠性测试', '调度任务重复触发时数据保持一致', '高', '同一抓取任务可被重复投递', '1.并发触发同一时间窗任务两次；\n2.等待完成；\n3.核对论文、解析任务和推送记录。', '不产生重复论文、重复解析或重复推送；任务状态最终一致；异常有日志。', 'FR-1.1/AR-2'],
  ['外部依赖故障恢复', '可靠性测试', 'arXiv或解析服务暂时不可用时可恢复', '高', '可模拟超时、限流和服务中断', '1.抓取中注入超时/429/5xx；\n2.恢复依赖；\n3.观察重试与补偿。', '采用退避重试或进入可恢复队列；不丢失任务；恢复后完成处理；前台有可理解状态。', 'FR-1/2'],
  ['服务重启一致性', '可靠性测试', '服务重启后任务和用户数据保持一致', '高', '存在运行中解析任务及已保存笔记', '1.处理过程中重启服务；\n2.重新登录；\n3.检查任务、收藏、笔记和索引。', '已提交任务可恢复或明确失败可重试；用户数据不丢失；无脏数据和重复记录。', 'FR-2/5'],
  ['身份认证与数据隔离', '安全性测试', '未登录访问受限且不同用户数据隔离', '高', '准备两个普通用户', '1.未登录访问收藏/笔记接口；\n2.用户A创建笔记；\n3.用户B尝试读取或修改。', '未登录请求被拒绝；用户B无法访问或修改A的私有数据；服务端校验而非仅前端隐藏。', 'FR-5'],
  ['输入与查询安全', '安全性测试', '搜索、笔记、评论和问答输入抵御注入与XSS', '高', '系统部署在测试环境', '1.在各输入点提交SQL/脚本/提示注入样本；\n2.查看页面和日志；\n3.重复访问保存内容。', '无SQL注入、脚本执行或越权指令生效；内容安全转义；错误不泄露敏感堆栈。', 'FR-3/4/5'],
  ['外部内容安全', '安全性测试', '恶意PDF或HTML内容不影响系统安全', '高', '准备含异常脚本、超大对象或畸形结构的样本', '1.提交恶意样本解析；\n2.监控解析进程；\n3.访问生成内容。', '解析在受控环境完成；恶意内容不执行；资源限制有效；失败不影响其他任务。', 'FR-2'],
  ['主流浏览器兼容', '兼容性测试', 'Web客户端在主流浏览器正常使用', '高', '部署可访问的Web测试环境', '1.使用当前受支持的Chrome、Edge、Firefox和Safari；\n2.覆盖抓取管理、检索、详情、问答和学习管理；\n3.比较结果。', '核心功能和交互一致可用；无阻塞性脚本错误；字体、图表和关系视图正常。', 'NFR-1'],
  ['响应式布局', '兼容性测试', '不同分辨率和尺寸下界面自适应', '高', 'Web客户端可访问', '1.测试桌面1920×1080、笔记本1366×768、平板768×1024、手机390×844；\n2.逐页检查；\n3.横竖屏切换。', '无关键内容遮挡或横向溢出；导航可用；表格/图谱提供合理折叠、滚动或适配。', 'NFR-2'],
  ['缩放与高分屏', '兼容性测试', '浏览器缩放和高DPI下内容清晰可操作', '中', '准备普通屏和高DPI设备', '1.在80%、100%、125%、150%、200%缩放下访问核心页面；\n2.检查文本、按钮和图谱；\n3.执行键鼠操作。', '文本和图标清晰；控件不重叠；焦点与点击区域准确；核心流程可完成。', 'NFR-2'],
  ['状态反馈与空态', '易用性测试', '加载、成功、失败和无结果反馈清晰', '中', '系统可模拟慢请求与错误', '1.触发抓取、解析、检索和保存；\n2.模拟失败与空结果；\n3.观察提示和恢复入口。', '加载状态可见；成功/失败提示明确；空态给出下一步；失败操作可重试且不重复提交。', 'FR-1~5'],
  ['核心流程易用性', '易用性测试', '新用户无需培训可完成核心任务', '中', '准备未接触系统的目标用户', '1.让用户完成检索论文、查看解析、提问、收藏和记笔记；\n2.记录完成率与障碍；\n3.收集反馈。', '用户可依据界面文案完成任务；关键入口易发现；没有阻塞性理解歧义。', 'NFR-1/2'],
  ['首次部署', '部署测试', '按部署文档首次安装系统', '高', '干净服务器；配置、数据库和缓存服务可用', '1.配置环境变量；\n2.安装前后端依赖并执行数据库迁移；\n3.启动服务；\n4.运行健康检查和冒烟测试。', '服务成功启动；数据库结构正确；Web可访问；抓取、检索、问答和学习管理冒烟通过。', 'NFR-1'],
  ['升级与回滚', '部署测试', '版本升级和失败回滚不丢失数据', '高', '已部署上一版本并准备测试数据', '1.备份数据；\n2.执行升级和迁移；\n3.验证数据与功能；\n4.模拟升级失败并回滚。', '升级后历史论文和用户数据完整；迁移可审计；失败时可恢复到可用版本。', 'FR-1~5'],
];

const headers = [
  'Test Case ID\n测试用例编号',
  'Test Item\n测试项',
  'Test Type\n测试类型',
  'Test Case Title\n测试用例标题',
  'Test Criticality\n测试优先级',
  'Pre-condition\n预置条件',
  'Input & Procedure\n输入与操作',
  'Expected Output\n预期结果',
  'Result\n实际结果',
  'Status\n是否通过',
  'BUG Severity\n错误严重等级',
  'BUG ID\n缺陷编号',
  'Remark\n备注',
];

testSheet.getRange('A1:M2').merge();
testSheet.getRange('A1').values = [['测试用例']];
testSheet.getRange('A1:M2').format = {
  fill: '#FFFFFF',
  font: { bold: true, typeface: '宋体', fontSize: 20, color: '#111827' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
};
testSheet.getRange('A4:M4').values = [headers];

const rows = cases.map((item, index) => [
  `TC-${String(index + 1).padStart(3, '0')}`,
  item[0],
  item[1],
  item[2],
  item[3],
  item[4],
  item[5],
  item[6],
  null,
  null,
  null,
  null,
  `需求追踪：${item[7]}`,
]);
const lastRow = 4 + rows.length;
testSheet.getRange(`A5:M${lastRow}`).values = rows;

const bodyRange = testSheet.getRange(`A5:M${lastRow}`);
bodyRange.format = {
  fill: '#EAF1DC',
  font: { typeface: '宋体', fontSize: 10, color: '#1F2937' },
  borders: { preset: 'all', style: 'thin', color: '#4B5563' },
  verticalAlignment: 'center',
  wrapText: true,
};
testSheet.getRange(`A5:A${lastRow}`).format.horizontalAlignment = 'center';
testSheet.getRange(`C5:C${lastRow}`).format.horizontalAlignment = 'center';
testSheet.getRange(`E5:E${lastRow}`).format.horizontalAlignment = 'center';
testSheet.getRange(`I5:L${lastRow}`).format.horizontalAlignment = 'center';
testSheet.getRange(`M5:M${lastRow}`).format.horizontalAlignment = 'left';
testSheet.getRange(`A5:M${lastRow}`).format.rowHeight = 86;

testSheet.getRange('A4:M4').format = {
  fill: '#225D6B',
  font: { bold: true, color: '#FFFFFF', typeface: '宋体', fontSize: 11 },
  borders: { preset: 'all', style: 'thin', color: '#1F2937' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
  wrapText: true,
  rowHeight: 60,
};

const widths = [82, 110, 88, 180, 78, 190, 280, 220, 150, 82, 82, 82, 150];
widths.forEach((width, index) => {
  testSheet.getRangeByIndexes(0, index, lastRow, 1).format.columnWidthPx = width;
});
testSheet.freezePanes.freezeRows(4);
testSheet.showGridLines = false;

testSheet.getRange(`C5:C${lastRow}`).dataValidation = {
  rule: {
    type: 'list',
    values: ['功能测试', '准确性测试', '性能测试', '可靠性测试', '安全性测试', '兼容性测试', '易用性测试', '部署测试'],
  },
};
testSheet.getRange(`E5:E${lastRow}`).dataValidation = {
  rule: { type: 'list', values: ['高', '中', '低'] },
};
testSheet.getRange(`J5:J${lastRow}`).dataValidation = {
  rule: { type: 'list', values: ['通过', '不通过', '阻塞', '未执行'] },
};
testSheet.getRange(`K5:K${lastRow}`).dataValidation = {
  rule: { type: 'list', values: ['致命', '严重', '一般', '轻微', '建议'] },
};

testSheet.getRange(`J5:J${lastRow}`).conditionalFormats.deleteAll();
testSheet.getRange(`J5:J${lastRow}`).conditionalFormats.add('containsText', {
  text: '通过',
  format: { fill: '#DCFCE7', font: { color: '#166534', bold: true } },
});
testSheet.getRange(`J5:J${lastRow}`).conditionalFormats.add('containsText', {
  text: '不通过',
  format: { fill: '#FEE2E2', font: { color: '#991B1B', bold: true } },
});
testSheet.getRange(`J5:J${lastRow}`).conditionalFormats.add('containsText', {
  text: '阻塞',
  format: { fill: '#FEF3C7', font: { color: '#92400E', bold: true } },
});

const categories = ['功能测试', '准确性测试', '性能测试', '可靠性测试', '安全性测试', '兼容性测试', '易用性测试', '部署测试'];
infoSheet.getRange('A1:F1').merge();
infoSheet.getRange('A1').values = [['论文知识管理与智能问答系统测试用例']];
infoSheet.getRange('A1:F1').format = {
  fill: '#225D6B',
  font: { bold: true, color: '#FFFFFF', typeface: '宋体', fontSize: 18 },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
  rowHeight: 38,
};
infoSheet.getRange('A3:B3').merge();
infoSheet.getRange('C3:F3').merge();
infoSheet.getRange('A4:B4').merge();
infoSheet.getRange('A5:B5').merge();
infoSheet.getRange('D5:E5').merge();
infoSheet.getRange('A6:B6').merge();
infoSheet.getRange('D6:E6').merge();
infoSheet.getRange('A3:F6').values = [
  ['项目名称\nProject Name', null, '论文知识管理与智能问答系统', null, null, null],
  ['项目编号\nProject ID', null, 'SE26Project-05', '版本\nVersion', '1.0', 'SE26Project-05_STC_001'],
  ['拟制\nPrepared by', null, '项目组', '日期\nDate', null, new Date('2026-07-28T00:00:00')],
  ['评审人\nReviewed by', null, null, '日期\nDate', null, null],
];
infoSheet.getRange('F5:F6').setNumberFormat('yyyy-mm-dd');
infoSheet.getRange('A3:F6').format = {
  font: { typeface: '宋体', fontSize: 11 },
  borders: { preset: 'all', style: 'thin', color: '#4B5563' },
  verticalAlignment: 'center',
  wrapText: true,
  rowHeight: 38,
};
infoSheet.getRange('A3:B6').format = {
  fill: '#DCE6F1',
  font: { bold: true, typeface: '宋体', fontSize: 11 },
  borders: { preset: 'all', style: 'thin', color: '#4B5563' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
  wrapText: true,
};
infoSheet.getRange('D4:E6').format = {
  fill: '#DCE6F1',
  font: { bold: true, typeface: '宋体', fontSize: 11 },
  borders: { preset: 'all', style: 'thin', color: '#4B5563' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
  wrapText: true,
};
infoSheet.getRange('A8:F8').merge();
infoSheet.getRange('A8').values = [['修订记录 Revision Record']];
infoSheet.getRange('A8:F8').format = {
  fill: '#225D6B',
  font: { bold: true, color: '#FFFFFF', typeface: '宋体', fontSize: 11 },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
};
infoSheet.getRange('A9:F10').values = [
  ['日期', '修订版本', '修改描述', null, null, '作者'],
  [new Date('2026-07-28T00:00:00'), '1.00', '依据功能、非功能和进阶需求完成系统测试用例', null, null, '项目组'],
];
infoSheet.getRange('C9:E9').merge();
infoSheet.getRange('C10:E10').merge();
infoSheet.getRange('A10').setNumberFormat('yyyy-mm-dd');
infoSheet.getRange('A9:F10').format = {
  font: { typeface: '宋体', fontSize: 10 },
  borders: { preset: 'all', style: 'thin', color: '#4B5563' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
  wrapText: true,
  rowHeight: 32,
};
infoSheet.getRange('A9:F9').format = {
  fill: '#DCE6F1',
  font: { bold: true, typeface: '宋体', fontSize: 10 },
  borders: { preset: 'all', style: 'thin', color: '#4B5563' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
};
infoSheet.getRange('A12:F12').merge();
infoSheet.getRange('A12').values = [['测试结果分析']];
infoSheet.getRange('A12:F12').format = {
  fill: '#225D6B',
  font: { bold: true, color: '#FFFFFF', typeface: '宋体', fontSize: 12 },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
};
infoSheet.getRange('A13:C13').merge();
infoSheet.getRange('A13:F13').values = [['类别', null, null, '用例数', '通过数', '通过率']];
infoSheet.getRange('A13:F13').format = {
  fill: '#DCE6F1',
  font: { bold: true, typeface: '宋体', fontSize: 11 },
  borders: { preset: 'all', style: 'thin', color: '#4B5563' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
};
for (let row = 14; row <= 22; row += 1) {
  infoSheet.getRange(`A${row}:C${row}`).merge();
}
infoSheet.getRange('A14:A21').values = categories.map((category) => [category]);
for (let row = 14; row <= 21; row += 1) {
  infoSheet.getRange(`D${row}`).formulas = [[`=COUNTIF('Test Cases'!$C$5:$C$${lastRow},A${row})`]];
  infoSheet.getRange(`E${row}`).formulas = [[`=COUNTIFS('Test Cases'!$C$5:$C$${lastRow},A${row},'Test Cases'!$J$5:$J$${lastRow},"通过")`]];
  infoSheet.getRange(`F${row}`).formulas = [[`=IFERROR(E${row}/D${row},0)`]];
}
infoSheet.getRange('A22').values = [['合计']];
infoSheet.getRange('D22').formulas = [['=SUM(D14:D21)']];
infoSheet.getRange('E22').formulas = [['=SUM(E14:E21)']];
infoSheet.getRange('F22').formulas = [['=IFERROR(E22/D22,0)']];
infoSheet.getRange('F14:F22').setNumberFormat('0.0%');
infoSheet.getRange('A14:F21').format = {
  fill: '#EAF1DC',
  font: { typeface: '宋体', fontSize: 11 },
  borders: { preset: 'all', style: 'thin', color: '#4B5563' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
  rowHeight: 28,
};
infoSheet.getRange('A22:F22').format = {
  fill: '#D7E3BC',
  font: { bold: true, typeface: '宋体', fontSize: 11 },
  borders: { preset: 'all', style: 'medium', color: '#374151' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
};
infoSheet.getRange('A1:A22').format.columnWidthPx = 110;
infoSheet.getRange('B1:B22').format.columnWidthPx = 110;
infoSheet.getRange('C1:C22').format.columnWidthPx = 190;
infoSheet.getRange('D1:E22').format.columnWidthPx = 100;
infoSheet.getRange('F1:F22').format.columnWidthPx = 150;
infoSheet.showGridLines = false;

methodSheet.getRange('A1:B9').clear({ applyTo: 'contents' });
methodSheet.getRange('A1:B9').values = [
  ['测试类型', '常用测试方法'],
  ['功能测试', '采用场景法覆盖主流程、备选流程和异常流程；结合等价类、边界值、判定表、错误猜测法验证输入输出。'],
  ['准确性测试', '使用人工标注金标准数据集，按统一口径计算解析、检索、问答的准确率，并保留逐样本评分明细。'],
  ['性能测试', '在规定数据量和并发数下使用压测工具统计响应时间、吞吐率、错误率及CPU、内存、网络资源。'],
  ['可靠性测试', '通过重复投递、服务重启、依赖超时/限流等故障注入验证幂等、恢复、补偿和数据一致性。'],
  ['安全性测试', '验证认证授权、用户数据隔离、输入注入、XSS、恶意文档解析及敏感错误信息泄露。'],
  ['兼容性测试', '覆盖主流浏览器、桌面/平板/手机分辨率、横竖屏、浏览器缩放和高DPI显示。'],
  ['易用性测试', '通过任务完成率、入口可发现性、状态反馈、错误恢复和新用户试用观察易理解、易学与易操作性。'],
  ['部署测试', '执行首次部署、升级、迁移、健康检查、冒烟、备份和失败回滚验证。'],
];
methodSheet.getRange('A1:B9').format = {
  font: { typeface: '宋体', fontSize: 10 },
  borders: { preset: 'all', style: 'thin', color: '#4B5563' },
  verticalAlignment: 'center',
  wrapText: true,
};
methodSheet.getRange('A1:B1').format = {
  fill: '#DCE6F1',
  font: { bold: true, typeface: '宋体', fontSize: 11 },
  borders: { preset: 'all', style: 'thin', color: '#4B5563' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
};
methodSheet.getRange('A2:A9').format = {
  fill: '#EAF1DC',
  font: { bold: true, typeface: '宋体', fontSize: 10 },
  borders: { preset: 'all', style: 'thin', color: '#4B5563' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
};
methodSheet.getRange('A1:A9').format.columnWidthPx = 110;
methodSheet.getRange('B1:B9').format.columnWidthPx = 650;
methodSheet.getRange('A2:B9').format.rowHeight = 52;
methodSheet.freezePanes.freezeRows(1);
methodSheet.showGridLines = false;

const testCheck = await workbook.inspect({
  kind: 'table',
  range: `Test Cases!A4:M${lastRow}`,
  include: 'values,formulas',
  tableMaxRows: 12,
  tableMaxCols: 13,
  tableMaxCellChars: 120,
});
console.log(testCheck.ndjson);

const infoCheck = await workbook.inspect({
  kind: 'table',
  range: 'Information!A12:F22',
  include: 'values,formulas',
  tableMaxRows: 12,
  tableMaxCols: 5,
});
console.log(infoCheck.ndjson);

const errors = await workbook.inspect({
  kind: 'match',
  searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',
  options: { useRegex: true, maxResults: 300 },
  summary: 'final formula error scan',
});
console.log(errors.ndjson);

for (const [sheetName, range, fileName] of [
  ['Information', 'A1:F22', 'after_Information.png'],
  ['Test Cases', 'A1:M16', 'after_Test_Cases_top.png'],
  ['Test Cases', `A${Math.max(5, lastRow - 7)}:M${lastRow}`, 'after_Test_Cases_bottom.png'],
  ['常用测试方法', 'A1:B9', 'after_常用测试方法.png'],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.25, format: 'png' });
  await fs.writeFile(`${outputDir}/${fileName}`, new Uint8Array(await preview.arrayBuffer()));
}

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, caseCount: cases.length, lastRow }));
