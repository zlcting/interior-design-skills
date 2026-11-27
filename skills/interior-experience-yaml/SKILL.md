---
name: interior-experience-yaml
description: 根据 Home3D 工程、目标方案和讲解需求生成或修改方案中心体验编排 YAML，核对正式业务模板和模型冻结设备合同。用于第 2 稿导入测试、讲解镜头、设备动作、状态和联动编排。
---

# 方案中心体验编排 YAML

使用 [体验编排模板第 2 稿](assets/方案中心-体验编排模板-第2稿.yaml) 生成 UTF-8 的 `solution-experience.draft.v2`。模板中的方案版本、资源 ID 和能力值都是示例。按本次体验需要保留字段，省略未使用的可选部分。

## 确定目标和引用

- 确认目标环境、方案、体验内容及输出位置。改稿时先读取现有 YAML，保留仍在使用的章节、步骤、旁白、cue 和规则 ID，仅修改用户指定的部分。
- 使用目标方案已保存的 `sceneVersionId`，按字符串写入。用户给了目标方案且已有连接时，可以只读查询方案详情，例如 `nb api resource get --env <已配置环境> --resource plugins_sol_solutions --filter-by-tk <方案ID> -j`。也可使用用户提供的方案快照。本地与 dev 的 V2 可以有不同 ID，包内工程 ID 和版本序号不能用于绑定。在目标方案尚无已确认的场景版本时，先写讲解和已核对的镜头，使用 `'REPLACE_WITH_TARGET_SCENE_VERSION_ID'` 并在文件名和交付说明标注「待绑定，暂不可导入」。
- 从目标方案快照或对应的 Home3D 工程读取楼层、房间和设备实例 ID。有两种来源时核对一致。对于标准 Home3D v4，从 `project.json` 读取楼层、房间和模型实例 ID，用 `devices.json` 中的 `instances[].instanceId` 匹配设备对应的模型实例。设备文档里的 `instances[].id` 和显示名称不能代替模型实例 ID。目标未确认时，先用已验证的上一级镜头。

## 编排讲解与设备动作

- 依次组织章节、步骤、旁白和段内 cue。每个步骤设置 `focus`。旁白可继承或覆盖镜头；需要保持上一段画面时，仅在同一步骤的后续段落使用 `focus: keep`，且该段不叠加镜头覆盖。重复的镜头或时序写入 `defaults` 或 `cameraPresets`。
- 需要动作时，先查目标环境正式模板中的能力键、操作权限、参数类型和范围，再填写初态、动作或联动。普通设备沿用目标方案的能力绑定。补充模拟设备时，通过 `resources.templateRefs` 固定 `templateId`、`publicationId` 和 `definitionId`，并用 `resources.playbackDevices[].templateRef` 指向对应条目。能力未核实时保留镜头和讲解，列出待补动作。
- 标准 Home3D v4 还要核对包内冻结的设备合同。正式业务模板与模型合同都允许，才生成该动作；不能只凭设备类型或 UI 字段推断。按 `instanceId` 映射到 SDK 设备 ID，整机、`controlObjectId` 和 `outputId` 必须精确匹配，不能互相回退。
- 设备动作中，只有模型合同声明 `value.type: number` 的属性 `write` 可以设置非零 `transitionMs`。布尔开关、枚举、命令和 `observe` 样本统一写 `transitionMs: 0`；整数属性也不能直接假定支持数值过渡。灯光渐变应调亮度，窗帘移动应调位置；镜头的 `camera.transitionMs` 按镜头需求保留。
- 初态和枚举从同一冻结合同核对。仅覆盖剧情需要的属性，其他属性沿用模型默认值；没有初值的未知状态应保持缺省。不能通用地写 `idle`：例如合同规定扫地机器人回站状态是 `docked` 时就使用 `docked`。保留合法 `false`、`0`、`null`，不能用真值判断丢弃它们，也不能把 `{}` 当成 `null`。
- 当前 SDK 发布链路不承接重复事件、带参数命令、局部作用域规则和旧组合场景。无参数命令仅在两份合同都允许 `null` 时使用；存在不支持的需求时列为待补依赖，保留讲解和镜头，不生成注定无法发布的示例动作。
- 共用的动作放在 `scenes`，一次性的演示放在旁白的 `cues`。用 `before`、`with` 或 `after` 表达与旁白的关系。只保留本次体验会用到的规则和初态，保留有效的 `false`、`0` 等值。
- 末章保留一个启用的服务介绍，设置 `kind: service`、`finish: manual`、`serviceFlowId: service-flow-v1`，步骤使用整屋镜头和旁白。

## 检查与交付

交付独立 YAML 文件。文件名标明工程、目标环境和方案，例如 `Hello-Harmony-502-dev-方案7-体验编排.yaml`。先解析 YAML，再核对目标版本、全部资源引用、重复 ID、镜头预设及末章。可访问业务系统源码时，使用方案中心的 `importExperienceDocument` 和 `validateExperience` 对照目标场景上下文校验，设备动作同时核对正式业务能力和模型冻结合同。使用 [SDK 预检方法](references/sdk-preflight.md) 调用发布端同一套检查；一次处理全部问题，再复检到零问题。仅通过 YAML 解析不代表设备可执行；仅通过 SDK 检查也不代表业务绑定和音频已就绪。交付时写明通过的检查、待补依赖，以及实际页面导入是否已验证。

在方案中心的「体验编排 → 导入体验 YAML」选文件，确认后点「保存并应用」，查看保存后的全部配置问题，也可点「检查体验配置」。替换模型后重新核对目标 `sceneVersionId` 和实例/作用域，再检查；不要仅替换版本 ID 后宣称所有引用已兼容。需要试听时生成讲解音频，再用「手机体验」预览。生成 YAML 的任务交付文件，目标方案的保存和发布由用户操作或另行授权。
