# 业务模板引用与远端查询

用于把生成的 Home3D 工程交给方案中心做能力编排。标准便携合同、模型和效果绑定仍由设备源包提供；这里查询业务模板身份，不编译或覆盖便携合同，也不选择实际产品或硬件。

## 在业务系统查看

开发环境：[资源中心 → 设备模版管理](https://dev.houzzkit.com/operational/admin/ka7zm6nhe7n)。模板详情中的“源模版 UUID”是模板 ID，“模版 key”是语义标识，来源信息中还有发布 ID。不同环境应分别查询，不从名称猜 UUID。

## 推荐输入

build job 可选 `businessTemplate`。给定目标 `nb` 环境和 **templateKey 或 templateId 之一**，工具通过已配置的 nb 登录只读查询 `plugins_pm_device_templates:list`。

```json
{
  "businessTemplate": {
    "env": "houzzkit-dev",
    "templateKey": "lighting.light.general"
  }
}
```

设备源已声明 `requirementRef.templateKey` 时，可以只提供：

```json
{ "businessTemplate": { "env": "houzzkit-dev" } }
```

工具将使用这个已声明的 key，不按设备名称猜测。如果显式给出模板 UUID，查询结果的 key 仍必须与设备源声明一致；确需更换能力模板，应先审查并更新源包及其合同，不用参数掩盖不匹配。

不填 `businessTemplate` 时，原有独立设备制作和离线模拟行为保持不变。当前环境必须显式指定；账号、token、地址不放入 job 或包。`nb` 不在 PATH 时，操作者可用 `NB_BIN` 指定本机 CLI 路径。

## 单独查询

```sh
node scripts/resolve_template.mjs --env houzzkit-dev --template-key lighting.light.general
node scripts/resolve_template.mjs --env houzzkit-dev --template-id 3a30d06a-6f9a-513b-9b29-fed46b1147ae
```

可加 `--output /path/to/new-reference.json` 保存查询结果，已有文件不会覆盖。CLI 需要现有有效登录和模板读取权限；若失败，核对 `nb env` 与登录状态后再查询，不把凭据写入技能。

工具要求精确唯一、启用、未归档且有正式发布来源的模板，返回：

```json
{
  "schema": "houzzkit.device-template-reference.v1",
  "templateId": "<远端源模版 UUID>",
  "templateKey": "lighting.light.general",
  "publicationId": "sha256:<远端发布摘要>",
  "purpose": "experienceSimulation"
}
```

构建时写入新增设备实例的 `extensions["org.houzzkit.device-template"]`，验收记录保存目标环境及解析结果。独立 `.device.zip` 保持可复用源包；生成的 `.home3d` 带业务引用。查询失败不会生成替代 UUID、选择相似模板或输出关联成功。

## 与业务系统的边界

包里的引用只是输入。方案中心导入时会核对可访问目录中的模板 UUID、key、来源发布及启用状态；绑定证据由业务端刷新并保存。技能不代替这一步，也不自动导入、修改远端数据或发布方案。正式能力合同、便携合同和真实产品型号是不同身份，不能仅因名称相同而等同。
