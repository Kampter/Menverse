# 云计算标准化失败案例深度调研报告

## 摘要

系统调研了云计算领域标准化尝试的历史案例，从OCCI、CDMI、DMTF CIM等正式标准，到Apache Libcloud/jclouds等开源抽象层，再到OpenStack的碎片化经历和Kubernetes的成功路径。核心发现：**成功的标准从运营系统中演化而来，获得市场采纳后才被形式化；委员会设计的标准几乎总是失败。**

---

## 一、OCCI (Open Cloud Computing Interface) — 已死亡

### 1.1 设计目标

由**Open Grid Forum (OGF)**于2009-2010年提出，旨在为IaaS提供统一标准化接口。

### 1.2 为什么失败

| 因素 | 具体表现 |
|------|---------|
| **市场时机太晚** | OCCI 1.0发布于2011年，AWS EC2已于2006年上线 |
| **委员会设计 vs 市场驱动** | 由标准组织设计，非从实际运营系统演化 |
| **商业利益冲突** | AWS、Azure、GCP的核心竞争优势正是独特API生态 |
| **技术复杂度** | 多渲染格式（JSON/XML/HTTP）增加实现负担 |
| **缺乏实际部署** | 无主流云厂商在生产环境中采用 |

### 1.3 当前状态

- OCCI 1.2于2016年发布，此后无实质性更新
- OGF的OCCI工作组已**进入休眠状态**
- **结论：OCCI实质上已死亡**

---

## 二、CDMI (Cloud Data Management Interface) — 已边缘化

### 2.1 由SNIA提出

目标是成为云存储的标准接口：RESTful API、能力发现机制、元数据管理。

### 2.2 技术问题

| 版本 | 问题数量 |
|------|---------|
| CDMI 1.0.1 (2011) | 100+ Trac Tickets |
| CDMI 1.0.2 (2012) | 800+ Trac Tickets |

HTTP状态码误用、安全语义错误、URI处理不一致、对象访问生命周期混乱。

### 2.3 为什么输给S3 API

| 因素 | CDMI | Amazon S3 API |
|------|------|---------------|
| 发布时间 | 2010年 | 2006年 |
| 设计哲学 | 全面标准化REST | 简单、务实的HTTP |
| 操作复杂度 | 复杂对象类型、能力协商 | PUT/GET/DELETE + 简单元数据 |
| 市场采纳 | 几乎无厂商支持 | 成为事实标准 |
| 学习曲线 | 高 | 低 |

**核心教训**：CDMI代表"委员会过度设计"的典型失败——追求理论上的RESTful完美，输给了S3的简单实用主义。

---

## 三、DMTF CIM (Common Information Model) — 已休眠

### 3.1 云计算管理中的尝试

- CIMI (Cloud Infrastructure Management Interface, 2012)
- OVF (Open Virtualization Format, 2008)
- CADF (Cloud Auditing Data Federation, 2011)

### 3.2 为什么复杂到几乎没人完整实现

- CIM Schema涵盖计算、存储、网络、虚拟化、外设、应用——**过于全面**
- 协议栈复杂：CIM → WBEM → HTTP/XML，多层抽象
- DMTF专门发布DSP0264规范来映射CIMI到CIM元模型
- **现代替代**：DMTF推出**Redfish**（2015年，JSON/REST）

### 3.3 当前状态

- Cloud Management Initiative已"**休眠**"
- DMTF当前重点转向Redfish、MCTP、PLDM、SPDM等更简单标准
- **结论：CIM在云计算管理中的尝试已失败**

---

## 四、Apache Libcloud / jclouds — 最低公分母问题

### 4.1 根本局限性

学术研究明确记录：

> "In either case, agreement on a least common denominator API between the different cloud systems supported by such abstraction environments does mean loss of specialized services."

### 4.2 jclouds的具体不一致性

| 问题类型 | 具体表现 |
|---------|---------|
| 位置列表不一致 | EC2/GCE列出所有可用区，OpenStack Nova行为不同 |
| 模板选项不一致 | OpenStack需要显式指定可用区和SSH密钥 |
| 安全组管理不一致 | 不同提供商行为差异 |
| Windows支持缺失 | 跨提供商不可用 |

### 4.3 性能退化

- jclouds：FaaS场景下AWS运行时增加25%，Google增加36%
- 即使使用jclouds，FaaS迁移成功率仅**50%**（22名学生中11人失败）

### 4.4 根本问题

1. 差异化服务无法抽象
2. 性能损失
3. 抽象泄漏
4. 迁移成功率低

---

## 五、AWS/Azure/GCP的API锁定策略

### 5.1 为什么主动制造差异

> "Many cloud providers are concerned with the loss of customers that may come with standardization initiatives which may flatten profits."

### 5.2 S3兼容API——罕见的成功案例

| 提供商 | 兼容性 | 状态 |
|--------|--------|------|
| Wasabi | 声称"100% bit-compatible" | 活跃 |
| Backblaze B2 | S3兼容端点 | 活跃 |
| Cloudflare R2 | S3兼容 | 活跃 |
| MinIO | S3兼容（本地部署）| 广泛采用 |

**关键洞察**：S3兼容层的成功是因为S3 API**足够简单**且**先发优势足够大**。

### 5.3 Egress费用的设计如何锁定用户

| 方向 | 费用 | 战略目的 |
|------|------|---------|
| 数据传入(Ingress) | **免费** | 鼓励数据迁入 |
| 数据传出(Egress) | $0.05-$0.09/GB | 阻止数据迁出 |
| NAT Gateway | $0.045/小时 + $0.045/GB | 有效出口成本高达$0.135/GB |

---

## 六、OpenStack——从标准化希望到碎片化

### 6.1 "小分支"问题

> "It's these forks of the mainline framework that creates the challenges..."

### 6.2 主要发行版及其差异

| 发行版 | 厂商 | 差异化方式 |
|--------|------|-----------|
| RHEL OpenStack Platform | Red Hat | 企业级支持、与RHEL深度集成 |
| Mirantis OpenStack | Mirantis | Kubernetes原生控制平面 |
| Canonical Charmed OpenStack | Canonical | Ubuntu生态集成 |
| VMware Integrated OpenStack | VMware | vSphere深度集成 |

### 6.3 深层教训

1. **开源 ≠ 标准化**：开源代码的可获得性不等于接口和行为的统一
2. **商业激励破坏标准化**：厂商需要通过差异化竞争
3. **模块化设计的双刃剑**：本意是灵活，实际导致"选择你自己的冒险"式碎片化
4. **上游与下游的张力**：上游社区追求通用性，下游发行版追求差异化

---

## 七、Kubernetes——为什么成功了？

### 7.1 历程

| 时间 | 里程碑 |
|------|--------|
| 2003-2004 | **Borg**在Google内部开发 |
| 2014年6月 | Kubernetes首次代码提交 |
| 2015年7月 | **v1.0发布；同一天捐赠给CNCF** |
| 2018年3月 | 成为CNCF**首个Graduated项目** |

### 7.2 CNCF治理模式

> "CNCF's purpose was to break the monopoly of cloud giants"

| 机制 | 具体措施 |
|------|---------|
| 多公司Steering Committee | 没有单一厂商控制技术方向 |
| 280万+公司贡献 | 提交者来自多家公司 |
| Graduation标准 | 证明蓬勃的采用、结构化治理 |
| vendor-neutral承诺 | Broadcom将Velero捐赠给CNCF |

### 7.3 K8s成功的关键因素

| 因素 | Kubernetes | 失败的标准 |
|------|-----------|-----------|
| 起源 | 从实际运营系统（Borg）演化 | 委员会设计 |
| 治理 | Vendor-neutral基金会（CNCF） | 单一标准组织 |
| 时机 | 容器编排市场早期（2014） | 市场已成熟 |
| 采用策略 | 所有主流云厂商提供托管服务 | 无主流厂商采纳 |
| 生态飞轮 | 采用→贡献→功能丰富→更多采用 | 无飞轮效应 |
| 生产验证 | Google内部10年运营经验 | 无生产验证 |

**2025年数据**：
- **82%**的容器用户在生产环境运行Kubernetes
- **66%**运行生成式AI的组织使用Kubernetes进行推理

### 7.4 K8s成功的独特条件

1. **Google的战略捐赠**：主动放弃控制权，换取生态繁荣
2. **容器标准的先行**：Docker建立了OCI标准
3. **云厂商的"囚徒困境"**：不提供K8s托管 = 失去客户
4. **开发者体验优先**：声明式API、自愈合、滚动更新

---

## 八、核心教训

### 8.1 云计算标准化的五条铁律

1. **事实标准 > 法定标准**
2. **简单战胜复杂**
3. **运营验证 > 委员会设计**
4. **Vendor-neutral治理是必要条件**
5. **客户集体行动是唯一驱动力**

### 8.2 K8s路径是否可复刻到AI推理？

**可复刻**：
- OpenAI API已从实际服务中演化 ✅
- 解决真实痛点（模型部署复杂性）✅
- 生态飞轮部分发生 ⚠️

**不可复刻**：
- AI推理层次更多（模型格式、硬件、优化技术）
- AI推理是差异化核心战场，厂商更不愿标准化
- 缺乏类似Docker的先行标准
- OpenAI、Anthropic、Google是竞争对手，无捐赠动机

### 8.3 AI推理特有的标准化障碍

| 障碍 | 说明 |
|------|------|
| 模型异质性 | Transformer、MoE、Diffusion需要不同优化 |
| 硬件异质性 | CUDA、ROCm、oneAPI、TPU完全不同 |
| 优化技术快速演进 | 连续批处理、PagedAttention、投机解码、FP8量化 |
| 推理引擎碎片化 | vLLM、TensorRT-LLM、TGI、SGLang、Ollama |
| API语义差异 | 工具调用、推理过程、缓存、结构化输出 |
| 性能与标准化的张力 | 最大性能需要硬件特定优化 |
| 模型权重即软件 | 参数是核心资产，分发和授权复杂 |

### 8.4 正在发生的标准化尝试

| 倡议 | 状态 |
|------|------|
| **OpenAI API兼容** | 已成为事实标准（80%+提供商支持）|
| **IETF Multi-Provider Inference API** | 2026年3月Internet-Draft |
| **MCP** | Anthropic发起，Agentic AI Foundation |
| **A2A** | Linux Foundation (Google) |
| **KServe (CNCF)** | 2025年11月成为CNCF Incubating |

**最可能成功的路径**：OpenAI API成为事实标准（类似S3 API），然后被形式化。

---

## 参考来源

- OCCI 1.2 Specification - StandICT
- CDMI 1.0.2 Errata - SNIA (800+ tickets)
- DMTF Cloud Standards
- USENIX HotCloud 2016 - Multi-cloud provisioning
- AWS Data Transfer Pricing 2026
- OpenStack doesn't prevent vendor lock-in
- CNCF Kubernetes Graduation Announcement
- CNCF 2025 Survey
- KServe Joins CNCF
- IETF Multi-Provider Inference API Draft
- vLLM vs TGI vs TensorRT-LLM
