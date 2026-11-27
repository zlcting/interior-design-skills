---
name: interior-device-package
description: 制作可复用的家居设备模型包，定义独立设备的能力、可操作状态、模型反馈和 SDK 读取，并装配为标准 Home3D v4 测试工程。用于灯、窗帘、空调等单件设备资产；整屋结构与家具导出使用 interior-home3d。
---

# 家居设备模型包

将设备外观、状态和效果连接组织成独立`.device.zip`，交付标准v4`.home3d`测试工程与验收记录。先读[设备包约定](references/package-contract.md)；选择形态和效果时查[形态与效果](references/model-effects.md)及[首批范围](references/scope.json)。规范快照来自2026-11-23评审稿，需求清单不代表已实现能力。

## 输入与制作

确认具体形态、产品或设计尺寸、安装方式、状态与控制、资料来源、目标客户端和输出位置。未知项明确记录，继续不依赖它的工作；不把样例尺寸、模拟值或同名业务能力当产品事实。一份包对应一种形态，多次放置后各实例状态独立；真实账号和硬件连接在业务系统绑定。

使用米、右手Y-up、正面-Z。通过normalization统一到底中心；安装点单独记录在归一化局部空间。为发光面、左右帘片、升降部件等设置唯一稳定的目标名，标定出光/出风位置、方向和转轴。材质纹理自包含，发光面与实际照明分开；按目标预算提供运行LOD1及必要LOD和制作源文件。

窗帘保留窗洞/开合侧/材质参数，灯带保留路径与截面；生成器、范围和输入需可追溯。工具装配**固定几何、模拟模式、基础通道和标准 experience 状态规则**；程序化、真实硬件和高级效果缺口具体记录，不改成fixed或删能力来绕过。

## 状态与效果

新制作的设备不能只交付外观：先列“能力 → 操作 → 当前状态 → 模型反馈 → SDK读取”的对照表。每项能力说明类型、权限、范围/枚举和来源；可操作项提供可见反馈，信息类设备提供可读状态。不清楚的能力保持待确认，不补造硬件功能。

新交互包声明`device.state-simulation`，同时交付`device-contract.json`和`device-state.json`；派生状态及有限动作使用`behavior.template.json`，装配为标准`experience.json`。出风、喷雾等持续视觉效果使用合同`simulation.visualCycles`，不写成无限业务规则。制作或迁移持续效果时读[持续效果与交接](references/continuous-effects.md)。按[能力、状态与SDK配方](references/capabilities-and-state.md)组织字段、效果和验证；查看器执行通用SDK指令，不按设备类型硬编码结果。

按[状态与验收](references/state-and-acceptance.md)区分当前反馈、控制目标、命令和事件。能力使用标准`home3d.device-contract.v1`；模型使用`home3d.model-definition.v1`，不加入未支持的字段。效果槽连接真实目标，公共资产不写deviceId。未知不填0/false，控制指令不当运行反馈。

首次制作灯或帘时按[基础配方](references/basic-recipes.md)组织合同和模型，不从零猜SDK字段；示例参数只用于明确标注的模拟，产品数据另行确认。

源格式`home3d.device-asset.v1`是本项目评审约定，不是编辑器直接导入格式。已有`.demo.v1`要补齐资料和显式迁移，不能只改schema。

## 检查与装配

```sh
node scripts/device_package.mjs seal /path/to/device-source
node scripts/device_package.mjs check /path/to/device-source
node scripts/device_package.mjs build /path/to/build-job.json
```

目录外使用绝对脚本路径。运行需Node20+、Python3；复用同组`interior-home3d/scripts/vendor`锁定SDK 0.3.4制品，兼容旧源包，不另写Home3D验证器。持续效果需目标SDK至少0.3.4并声明`device.visual-cycles.v1`；消费者能力仍须另验。独立搬运本技能时用`--sdk-dir`指向兼容SDK制品目录。文件字段、job和工具边界见[设备包约定](references/package-contract.md)。

工具检查文件清单、摘要和基础兼容，再由SDK校验GLB、合同、绑定和v4协议。build交付新的设备ZIP、测试工程及acceptance；可以装入既有v4，保留原对象、资源、光影及能力声明。不能完整表达的必需功能明确受阻，待执行器和消费者验证后扩展。

交给方案中心做业务能力编排时，读[业务模板引用](references/business-template.md)。build job 的 `businessTemplate` 可按目标环境加模板 key 或 UUID 只读解析远端引用；源包已有 `requirementRef.templateKey` 时可只给环境。复用已有 `nb` 登录，解析结果写入新工程实例，产品选型和远端绑定证据另由业务流程处理。

## 验收与交付

新交互包至少放置两个相同设备，并在build job中断言SDK当前状态；存在模型效果时再断言效果值。检查正常操作、切换、关闭/停止、异常和实例独立性，交付SDK读取示例；只写能力名称或只验证按钮触发不算完成。SDK状态隔离不等于实际渲染材质隔离。客户端还需安装点、旋转缩放、效果跟随、保存重开、导出重导入与光影检查，详见[状态与验收](references/state-and-acceptance.md)。

持续效果的build自动检查相位推进、讲解末态确认与稳定状态交接，并在`continuousEffects`记录证据；这是独立gate样本测试，正常开关/异常触发仍由job场景验证。`hasPendingTransitions()`用于继续设备帧，有限动作查询用`hasBlockingTransitions()`，交接以SDK正式校验为准。

交付源包、测试工程、制作源文件位置和证据。协议、状态模拟、几何/视觉、真实编辑、在线保存、硬件分别报告通过/失败/受阻/未测试；未做的保持not-reviewed。本技能不发布产品、不绑定硬件、不改业务数据库，按当前任务授权完成资产制作与装配。
