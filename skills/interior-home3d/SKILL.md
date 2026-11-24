---
name: interior-home3d
description: 从统一室内项目模型与同源几何生成可逐对象编辑的标准 .home3d 工程，保留墙体、门窗、房间、家具和灯光，并执行协议、几何与编辑验收。用于交付 Home3D 或业务系统可编辑场景。
---

# Home3D 可编辑工程

交付标准 v4 project `.home3d`，使墙、门窗和家具保持独立对象。先读[输入与导出约定](references/export-contract.md)，再读取[共享项目契约](../interior-orchestrator/references/project-contract.md)中与交付有关的字段。预算、采购和现场状态不作为模型导出的前置条件。

## 输入与准备

- 权威 `model/project.json`、同源 GLB／Blender 文件；已有灯光配置时一并携带。
- 缺少结构模型时转交总控、现状与平面阶段补齐；缺少可追溯家具几何时衔接空间表现阶段。单个整屋 GLB 不足以恢复原生墙、房间和洞口。
- 沿用已选家具精细度、风格和表现预设。生成新几何时遵循现有表现技能，不自行替换家具或默认切为白模。
- 确认稳定对象编号与模型节点标记对应；未知节点需要显式映射，不能靠相似外观猜墙或漏掉家具。

## 导出

在新输出目录执行，保留既有工程与原模型：

```sh
python3 scripts/export_home3d.py /path/to/project \
  --geometry /path/to/project/visuals/white-web-v1/white-web.glb \
  --lighting /path/to/project/visuals/white-web-v1/white-render-config.json \
  --full-source /path/to/project/visuals/white-minimal/interior.blend \
  --out /path/to/project/Home3D-standard-v4
```

目录外使用脚本绝对路径。参数、显式对象映射与运行依赖见[导出约定](references/export-contract.md)。

工具把源毫米/Z-up坐标转换为米制/Y-up，墙转中心线，房间保留分区，门窗保留宿主；家具零件按逻辑对象归组，独立灯具和装饰保留独立实例。墙与地板由原生结构表达，不能重复塞入整屋家具模型。窗框取同源全高几何，预览低墙不作为真实墙高。

技能生成曲面沿用 `triangle-area-v1` 法线策略，在最终三角网格上生成并验证法线。对可识别的旧版生成沙发软包，拆分时补齐法线策略。未知来源和手工加权法线保留。复用旧工程中的独立家具时，按[导出约定](references/export-contract.md#生成曲面法线与历史资源修复)核对受光并修复异常，保留原文件。

资源使用包内模型与内容摘要；不编造业务 modelVersionId、不写业务系统身份或凭据。包结构、摘要、引用和能力由锁定共用 SDK 处理，不另写验证器或绕过失败检查。

白模实时配置带有效 `white-home3d-v1` 来源和几何摘要时，导出器自动写入完整 `rendering.json`、冻结环境 PNG 和光影能力声明。其他可信配置通过 `--rendering` / `--rendering-assets` 显式提供；没有配置的旧工程保留原路径，不从预设名称猜测灯位、曝光或阴影。输入与严格兼容范围见[光影导出](references/export-contract.md#光影配置导出)。

## 验收与交付

依次执行[分层验收](references/acceptance.md)。SDK通过、对象/几何通过、实际编辑通过和视觉通过分别记录。

输出 `project.home3d`、`object-map.json`、`acceptance.json`、逐模型交换记录与实际执行日志。包可通过业务系统“导入可编辑工程”导入，不能用“导入模型”入口重新包成整屋家具。

首次版本及导出工具改动需实际导入目标编辑器，修改一件家具、一段墙和一个门窗，保存、刷新、导出再导入，并检查灯光位置、材质及白模预设。未执行的检查保持 `not_reviewed`；程序通过不等同客户视觉批准。

离线 SDK 0.3.0 默认写入统一 v4 project；旧 v3 工程仍可校验。没有已确认的逻辑设备合同时，`devices.json` 与 `presentation.json` 显式为空；模型灯光照常保留，不从灯具外观推断设备。能力边界见[导出约定](references/export-contract.md#统一-v4-输出)。

SDK支持某能力不代表目标编辑器已实现。当前交付能力限原生直墙/洞口/房间、静态模型、归一化与展示灯光；真实设备控制、动态 effects 和 openingFit 需另行接入，不能删除必需能力声明后冒充兼容。

单件家居设备的独立源包、能力/状态定义及基础模拟装配，使用[设备模型包技能](../interior-device-package/SKILL.md)。本技能现有整屋导出器继续保持空设备文档，直到有显式设备合同与装配任务；不从灯具外观推断逻辑设备。
