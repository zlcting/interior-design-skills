# 设备动作与初态预检

先取得目标方案的已保存版本、体验 YAML、对应 Home3D 和正式能力上下文。模型合同位于 `devices.json` 的 `contractPath`，必须由官方 SDK 读包并验证摘要。设备映射使用 `instances[].instanceId`，不是名称或 SDK ID。

| 内容 | 写法 |
| --- | --- |
| 布尔开关、枚举 | 合法值 + `transitionMs: 0` |
| 数值过渡 | 仅合同为 `number` 且操作为 `write`；如窗帘 `position` 2400ms |
| 只读属性演示 | `observe` 合法样本 + 0ms，不能改成 `write` |
| 无参数命令 | 双方合同都允许时用 `execute`、`value: null`、0ms |
| 初态 | 沿用冻结默认；仅覆盖必要属性，未知值不擅自补齐 |
| 输出与内部对象 | 精确保留 `outputId` 或 `controlObjectId`，二者互斥 |

不要猜状态同义词。例如 `idle` 不能自动转换成 `docked`；先查目标模型的枚举和默认值，再修改剧情。也不要通过删除过渡字段、自动替换非法枚举来伪造校验通过。

## 在方案中心检查

保存并应用后查看问题清单，或使用「检查体验配置」。预检检查已保存的修订，不修改设备、工程、音频或发布记录。发布时同样检查；未通过就不创建打包任务。草稿可以保留待完善的问题。

只读 API：`GET /api/plugins_sol_solutions:experiencePreflight?id=<方案ID>&revision=<已保存修订号>`。需要方案读取和体验字段权限；修订不一致返回 409。返回 `revision`、`sceneVersionId`、`applicable` 和全部 `issues[{path,key}]`。`applicable: false` 表示关闭体验或旧模型格式，不代表通过标准 SDK 合同校验。

## 本地检查交付文件

仓库包含 `scripts/check-experience.mjs`，调用业务系统原有导入器、同一预检函数和官方 SDK，不复制状态机或枚举校验。依赖已安装 node_modules 且已构建新版 Home3D 宿主的业务代码仓库。缺少依赖或接口时停止并说明，不冒充检查通过。

```sh
node /path/to/business/node_modules/tsx/dist/cli.mjs /path/to/skill/scripts/check-experience.mjs \
  --business-root /path/to/business \
  --home3d /path/to/scene.home3d --yaml /path/to/experience.yaml \
  --scene-version '<目标方案已保存的版本ID>' --context /path/to/target-context.json
```

`target-context.json` 使用目标方案 `experienceContext` 的数据部分，可附带 `narrationAudio`。正式模板引用、发布 ID 和输出定义不能由模型能力推造。无此上下文时，必须显式用 `--sdk-only` 代替 `--context`，报告会标注 `businessValidation: not-run`；该模式只能验证冻结模型的设备适配，不能宣称业务发布验收完成。

可用 `--output /path/to/new-report.json` 写新报告，已有文件不会被覆盖。退出码 0 表示该范围已通过；1 表示发现问题或不适用；2 表示参数或依赖失败。脚本不改写 YAML、Home3D 或目标方案。能力问题处理完后重新运行，再按任务范围验证镜头、音频与页面导入。
