# AI推理接入协议标准化：互联网标准历史的深度调研报告

## 摘要

通过系统调研IETF标准制定模式、HTTP演进历程、QUIC标准化案例以及互联网标准的失败教训，为AI推理协议的标准化提供历史参照和战略启示。核心发现：成功的互联网标准需要"运行代码"的实证支撑、关键推动者的产业影响力、以及开放共识的治理机制三者的有机结合。

---

## 一、IETF的组织模式与RFC流程

### 1.1 "Rough Consensus and Running Code"原则

这一原则由MIT教授、互联网先驱**David D. Clark**在**1992年7月**的IETF剑桥会议上提出。当时IAB曾试图用自上而下的方式将IP替换为OSI的CLNS方案，引发社区强烈反弹。

**"Rough Consensus"（粗略共识）**：
- 不是全体一致，也不是简单多数投票（约80-90%支持即可）
- 强烈反对意见必须被认真对待和回应，但不必满足所有人
- 通过"哼唱"（humming）而非举手表决来感知倾向

**"Running Code"（运行代码）**：
- 实现经验胜过设计优雅
- 需要实际可运行的原型系统
- 理想情况下需要两个以上独立、可互操作的实现

这一原则后被写入**RFC 3935**（2004年）和**RFC 7282**（2014年）。

### 1.2 RFC成熟度流程

```
Internet-Draft (6个月有效期)
    -> 工作组审查与迭代
    -> IESG审查与"Last Call"
    -> Proposed Standard (建议标准)
    -> Draft Standard (需多个互操作实现)
    -> Internet Standard (广泛部署)
```

IETF标准完全是**自愿采纳**的——"没有标准警察"（There are no standards police）。推动力来自技术权威、网络效应、互操作性需求和市场选择。

### 1.3 商业博弈

2023年《Research Policy》研究发现：与最大利益相关者关联的个人更容易被任命为IETF领导职位，但 paradoxically，这些工作组产出的标准被引用率更低。

Google在IETF中的角色：共同主办IETF 119、推动QUIC标准化、robots.txt标准化、参与AI Preferences工作组。

---

## 二、HTTP的演进

### 2.1 完整演进

| 版本 | 年份 | 关键创新 |
|------|------|---------|
| HTTP/0.9 | 1991 | 基本GET请求 |
| HTTP/1.0 | 1996 | 头部、状态码 |
| HTTP/1.1 | 1997 | 持久连接、管道化 |
| SPDY (Google) | 2009-2015 | 多路复用、头部压缩 |
| HTTP/2 | 2015 | 二进制协议、标准化SPDY |
| HTTP/3 (QUIC) | 2022 | UDP上的多路复用 |

### 2.2 SPDY如何推动HTTP/2

Google在2009年宣布SPDY，到2012年Chrome、Google服务、Twitter、Facebook都已采用。这形成了**de facto标准**的压力，迫使IETF在2012年选择SPDY作为HTTP/2基础。

### 2.3 HTTP/2的争议

- **Poul-Henning Kamp**（FreeBSD、Varnish作者）强烈批评：称SPDY到HTTP/2的整合是"惨败"，过程被政治驱动
- **加密争议**：HTTP/2标准本身不强制加密，但浏览器厂商声明不实现TLS就不支持HTTP/2，使加密成为de facto要求
- **性能质疑**：SPDY/HTTP/2在高延迟网络表现更好，但在低延迟网络收益有限；TCP层队头阻塞完全未解决

### 2.4 为什么需要HTTP/3

核心问题：TCP层队头阻塞——一个流的丢包会阻塞所有流。HTTP/3用QUIC over UDP解决，每个流独立。

Google部署数据：搜索延迟降低3.6-8%，YouTube重缓冲降低15-18%。

---

## 三、QUIC的标准化——典型案例

### 3.1 历程

- 2012年：Google工程师Jim Roskind设计QUIC
- 2013年：Google向IETF公开介绍，Chrome小规模实验
- 2014年：Chrome大规模部署gQUIC
- 2015年6月：向IETF提交QUIC Internet-Draft

### 3.2 Google的部署策略

控制Chrome浏览器（全球最大桌面浏览器份额）和Google服务（Search、Gmail、YouTube）。到2014年，Chrome到Google服务器的连接中超过50%使用QUIC。

### 3.3 IETF接管后的改动

| 方面 | Google QUIC | IETF QUIC |
|------|------------|-----------|
| 加密层 | 专有QUIC-Crypto | 标准TLS 1.3 |
| 互操作性 | 限于Google生态 | 开放多厂商兼容 |
| 连接ID | 较简单 | 支持连接迁移 |
| 头部压缩 | HPACK | QPACK |

**关键决策**：IETF拒绝Google的专有加密方案，强制使用TLS 1.3。

### 3.4 政治博弈

| 反对方 | 担忧 |
|--------|------|
| ISP/运营商 | 无法检查流量、失去元数据 |
| 企业防火墙 | 无法做DPI |
| 审查机构 | 更难过滤内容 |
| NAT设备 | 连接迁移破坏IP跟踪 |

应对策略：优雅降级——先尝试QUIC，超时后回退到HTTP/2。

### 3.5 成为RFC 9000

- 26次面对面会议
- 1,749个跟踪问题
- Last Call前34版修订草案
- 2021年5月发布

---

## 四、失败案例

### 4.1 XMPP的失败

XMPP（RFC 3920/3921）被WhatsApp、微信等封闭系统取代。

**失败原因**：
- 太多可选扩展导致碎片化
- 志愿者驱动，标准开发滞后于需求
- 无标准化推送通知方案，电池消耗大
- 2013年Google放弃XMPP服务器间联邦
- XML开销大（发送1字节需>0.5KB）
- OMEMO端到端加密标准化太晚

IETF已成立**MIMI（More Instant Messaging Interoperability）**工作组反思这一失败。

### 4.2 OAuth 1.0 -> 2.0

**OAuth 1.0问题**：
- 每个请求需要HMAC-SHA1签名
- 59.7%的开发者误解流程
- 无刷新令牌
- 给Google分布式系统增加约120ms延迟

**Eran Hammer的退出**（2012年7月26日）：
- 辞去OAuth 2.0主编职务
- 撤下自己的名字
- 发表"OAuth 2.0 and the Road to Hell"
- 称其"职业生涯最大的专业失望"

核心批评：OAuth 2.0为了开发者体验牺牲了消息级安全。

尽管有争议，OAuth 2.0于2012年10月作为RFC 6749发布，成为事实上的行业标准。

### 4.3 WebSockets

Ian Hickson后来表示将WebSocket规范交给IETF"是一个巨大的错误"，认为IETF过程延迟开发约一年，某些改动降低了安全性。

---

## 五、对AI推理协议标准化的核心启示

### 5.1 是否适用IETF模式？

**适用性**：高度匹配——开放参与、粗略共识+运行代码、市场驱动。

**关键差异**：
- AI推理领域变化速度远超传统协议（TCP用了20年，AI模型每季度更新）
- 涉及更多商业敏感信息（模型权重、推理成本）
- 当前由少数厂商主导（OpenAI、Anthropic、Google）

### 5.2 需要"Google"来推动吗？

**当前格局**：

| 协议/标准 | 发起者 | 角色 |
|-----------|--------|------|
| OpenAI Responses API | OpenAI | De facto标准 |
| MCP | Anthropic -> Linux Foundation | 新兴开放标准 |
| A2A | Google -> Linux Foundation | Agent间协作 |
| Chat Completions API | OpenAI | 基础推理接口 |

**最可能的路径**：类似QUIC——一个主导厂商先建立de facto标准，然后通过开放治理将其标准化。

### 5.3 "Running Code"如何应用

| 传统IETF | AI推理对应实践 |
|---------|---------------|
| 两个独立互操作实现 | 多个推理服务提供商实现兼容API |
| 运营经验 | 大规模生产环境的推理调用数据 |
| 真实网络测试 | 跨模型、跨厂商的互操作性测试 |
| 性能基准 | 延迟、吞吐量、成本的实际对比 |

### 5.4 五大教训

1. **De facto先于de jure**：SPDY先于HTTP/2，gQUIC先于RFC 9000
2. **"Running Code"是核心验证**：没有实际部署的协议设计容易脱离现实
3. **开放治理是长期关键**：Google将SPDY/QUIC交给IETF，Anthropic将MCP交给Linux Foundation
4. **简洁性胜过完美性**：OAuth 2.0虽然被批评安全性不足，但简洁性推动了universal adoption
5. **安全必须是默认而非扩展**：XMPP的端到端加密失败和OAuth 1.0的签名复杂性都说明安全设计必须在核心协议中

---

## 参考来源

- RFC 7282, 3935, 2026, 9000, 7540, 9114
- Fastly: QUIC is now RFC 9000
- APNIC: Running code at IETF
- Mark Nottingham: There Are No Standards Police
- Research Policy: Wearing multiple hats
- ExtremeTech: Developer criticizes HTTP/2 protocol
- The Register: OAuth 2.0 editor quits
- EFF: Google Abandons Open Standards for Instant Messaging
- IETF: Multi-Provider Extensions for Agentic AI Inference APIs
