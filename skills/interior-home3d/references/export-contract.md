# 输入与导出约定

## 权威输入

`model/project.json` 使用共享契约的 mm、平面 X/Y 和竖向 Z。需要稳定 `project_id`、房间、直墙、洞口、家具以及层高；无家具或无洞口可显式给空数组。源几何须来自同一项目和版本。家具使用 `extras.object_id` 归组；墙和房间地板按源编号识别并由原生结构替代。

既有表现生成器的 `WINxx frame/glazing/horizontal frame` 是该生成器确定的洞口分组，不对任意第三方命名做推断。剖切 GLB 的半截窗框须提供 `--full-source`（同源全高 GLB 或带 `Full walls` 集合的 Blender 文件）；其位置和高度必须与源洞口一致。

家具部件、UV、材质、透明度和 COLOR_0 从实际网格导出，不用长方体替代缺失家具。灯光侧车必须匹配源 GLB 的真实 SHA-256，灯具 ID 对应独立模型或显式 fixtures 映射。拆分后为目标模型重写合法摘要和局部灯位，保留原亮度、色温、颜色、范围及偏移。

## 命令与依赖

`export_home3d.py PROJECT --geometry FILE --out NEW_DIRECTORY`；可选 `--name NAME`、`--lighting JSON`、`--full-source FILE`、`--object-map JSON`、`--blender EXECUTABLE`、`--node EXECUTABLE`。输出目录必须不存在。失败不发布半成品，也不覆盖原输出。

需要 Python 3.10+、Node 20+ 和支持 glTF 的 Blender；安装整套技能后复用总控技能的求值几何交换校核。运行时 SDK 是 `scripts/vendor` 内锁定的离线制品，不安装全局 Node 包，不依赖开发者绝对目录。

作者更新 SDK：在仓库根运行 `node tools/build_home3d_sdk.mjs --sdk-source <权威home3d-package目录>`。工具只接受 0.1.0，记录源码摘要、bundle摘要和依赖许可；升级版本须同步消费能力与验收样例。SDK源码仍由共用包维护，技能只维护导出适配。

## 显式映射

可选映射文件示例：

```json
{
  "nodeOwners": {"ImportedMesh.001": "SOFA-A"},
  "objects": {"SOFA-A": {"name": "客厅沙发", "room": "LOUNGE", "facing": "south"}},
  "fixtures": {"LIGHT-A": "LAMP-A"}
}
```

`nodeOwners` 将实际节点归入源逻辑对象；同一家具的多个零件映射同一 ID。`objects` 只补名称、房间和资源局部朝向；不覆盖权威墙、洞口或房间。`fixtures` 给出灯具归属，不能将一盏光复制给所有模型。

源毫米坐标 `(X,Y,Z)` 转为 `(X/1000,Z/1000,-Y/1000)`。墙的 `at` 表示实体一侧，中心线取 `at+thickness/2`；洞口 offset 是从墙起点到洞口中心的距离，源开口起点需加上半个宽度。每个模型归一化到米制底中心，实例负责世界位置和旋转。相同完整资源定义及几何字节复用模型定义，不把实例身份写进公共业务库。

## 输出

- `project.home3d`：标准 v3，含结构、独立资源/实例、灯光和展示预设。
- `object-map.json`：源编号、源节点、实例 ID、资源键及模型摘要。
- `acceptance.json`：SDK身份与摘要、源文件摘要、协议/对象/几何结果、编辑和视觉状态。
- `components.json`、`world-verification.json`、`models/`、`blender.log`：实际拆分及重新导入证据。
- `state/execution-log.json`：本技能的实际执行记录，不补写其他技能执行历史。

旧业务 v2 工程迁移不是把 sourceIdentity 改成当前系统；应回到权威源数据输出标准 v3，保留旧包供追溯。

世界坐标验收直接读取实际包中的 GLB、归一化和实例变换，双向匹配 Blender 求值后的源顶点；不能只比较包围盒或局部几何。Blender颜色导入/导出会改变颜色存储类型；顶点AO保留与颜色数值精度须分开核对，不能声称字节一致。

目标业务系统的多私有资源导入需使用 Home3D 插件 2.2.29 或包含同等快照引用排序修复的后续版本。Blender内嵌 POINT/SPOT/SUN 需有对象编号或已归属模型父节点；不能与侧车灯具叠加。未归属的 Blender AREA/SUN 棚拍光记入跳过清单，不冒充可移植设备灯光。
