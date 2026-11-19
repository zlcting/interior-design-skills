# 输入与导出约定

## 权威输入

`model/project.json` 使用共享契约的 mm、平面 X/Y 和竖向 Z。需要稳定 `project_id`、房间、直墙、洞口、家具以及层高；无家具或无洞口可显式给空数组。源几何须来自同一项目和版本。家具使用 `extras.object_id` 归组；墙和房间地板按源编号识别并由原生结构替代。

既有表现生成器的 `WINxx frame/glazing/horizontal frame` 是该生成器确定的洞口分组，不对任意第三方命名做推断。剖切 GLB 的半截窗框须提供 `--full-source`（同源全高 GLB 或带 `Full walls` 集合的 Blender 文件）；其位置和高度必须与源洞口一致。

家具部件、UV、材质、透明度和 COLOR_0 从实际网格导出，不用长方体替代缺失家具。灯光侧车必须匹配源 GLB 的真实 SHA-256，灯具 ID 对应独立模型或显式 fixtures 映射。拆分后为目标模型重写合法摘要和局部灯位，保留原亮度、色温、颜色、范围及偏移。

## 命令与依赖

`export_home3d.py PROJECT --geometry FILE --out NEW_DIRECTORY`；可选 `--name NAME`、`--lighting JSON`、`--full-source FILE`、`--object-map JSON`、`--blender EXECUTABLE`、`--node EXECUTABLE`。输出目录必须不存在。失败不发布半成品，也不覆盖原输出。

需要 Python 3.10+、Node 20+ 和支持 glTF 的 Blender；安装整套技能后复用总控技能的求值几何交换校核。运行时 SDK 是 `scripts/vendor` 内锁定的离线制品，不安装全局 Node 包，不依赖开发者绝对目录。

作者更新 SDK：在仓库根运行 `node tools/build_home3d_sdk.mjs --sdk-source <权威home3d-package目录>`。工具只接受 0.2.0，记录源码摘要、bundle摘要和依赖许可；升级版本须同步消费能力与验收样例。SDK源码仍由共用包维护，技能只维护导出适配。

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

- `project.home3d`：标准 v4 project，含结构、独立资源/实例、灯光和展示预设。
- `object-map.json`：源编号、源节点、实例 ID、资源键及模型摘要。
- `acceptance.json`：SDK身份与摘要、源文件摘要、协议/对象/几何结果、编辑和视觉状态。
- `components.json`、`world-verification.json`、`models/`、`blender.log`：实际拆分及重新导入证据。
- `state/execution-log.json`：本技能的实际执行记录，不补写其他技能执行历史。

旧业务 v2 工程迁移不是把 sourceIdentity 改成当前系统；应回到权威源数据输出标准 v4 project，保留旧包供追溯。

世界坐标验收直接读取实际包中的 GLB、归一化和实例变换，双向匹配 Blender 求值后的源顶点；不能只比较包围盒或局部几何。Blender颜色导入/导出会改变颜色存储类型；顶点AO保留与颜色数值精度须分开核对，不能声称字节一致。

目标业务系统的多私有资源导入需使用 Home3D 插件 2.2.29 或包含同等快照引用排序修复的后续版本。Blender内嵌 POINT/SPOT/SUN 需有对象编号或已归属模型父节点；不能与侧车灯具叠加。未归属的 Blender AREA/SUN 棚拍光记入跳过清单，不冒充可移植设备灯光。

## 生成曲面法线与历史资源修复

生成器为软包等曲面写入 `interior_normal_policy: triangle-area-v1`。三维导出、AO 烘焙及拆包按最终三角索引计算法线并重读验证。旧版白模采用 `low-wide-modular` 沙发且缺少标记时，拆分器根据项目沙发编号和源 GLB 的家具编号、资产编号、软包部件及材质角色恢复策略。坐垫、扶手、靠背和抱枕进入法线校验。硬质底座、滚边及无来源标记的自定义法线保留原策略。源节点显式标记或对象映射优先。其他确认同源的软包可在 `objects.<sourceId>.normalPolicy` 中显式选择 `triangle-area-v1`。

复用旧包的独立家具时，优先从同源整屋 GLB 重新拆分。旧包内的独立模型可能缺少源部件身份。发现沙发坐垫、扶手或靠背出现细黑线时，核对法线与最终三角网格是否一致，并在目标编辑器按同一机位复查整屋与独立模型的受光。

已确认异常的静态 GLB 可单独修复，使用新输出路径：

```sh
python3 /path/to/interior-orchestrator/scripts/mesh_normals.py source-sofa.glb \
  --output sofa-normal-fixed.glb --all-static --report sofa-normal-report.json
```

`--all-static` 是对此文件的明确修复请求，不是所有导入模型的默认策略；蒙皮、变形和压缩模型需原生工具处理，不能静默改写。新文件摘要变化后须用标准 writer 重建包内引用、定义摘要与包摘要，不能直接覆盖旧哈希地址下的文件。修复包需保留原实例编号、位置、尺寸、设备绑定及灯光，并重新验证。 修复项目私有模型不等于发布新版业务资源库：保留原业务 `releaseRevision`、`releaseDigest` 及对应锁版本，只更新模型与包内摘要，不能把模型文件摘要写成业务发布摘要。

## 统一 v4 输出

离线 SDK 锁定 0.2.0，默认调用 `writePackage({version: 4, kind: 'project', ...})`。包以 `project.json` 为唯一空间权威，`resources.json` 为包内私有资源目录；不再输出 v3 的 `scene.json` 或 `runtime-resources.json`。保留同一 floorplan-scene.v5 结构合同、源编号、独立实例、洞口宿主、归一化、材质、灯光和白模预设。普通模型不编造业务版本 ID。

导出器没有逻辑设备合同输入：`devices.json` 使用 `home3d.devices.v1` 和空 `instances`，`presentation.json` 使用 `home3d.presentation.v1` 和空 `bindings`。展示灯光仍写入模型侧车或 GLB，不据此生成设备合同、手动控制或真实设备绑定。不生成 `experience.json`，不声明其能力；`kind: solution`、发布和手机端交付仍由后续方案链路验收。

v4 即使设备为空，也必须声明 `device.contracts.v1`、`device.presentation.v1`、`device.simulation.v1`；另声明实际使用的结构、GLB、normalization，以及有灯光时的 lighting。`package_home3d.mjs validate` 按此导出器的七项消费能力校验 v3/v4；`validate-protocol` 使用 SDK 完整协议能力，只通过后者不等于编辑器兼容。旧版仅支持 v3 的消费者会明确拒收 v4，不删除必需能力或伪装成旧版本。

目标编辑器须包含空主房间引用的工作投影修复：合法的 `projectMetadata.mainRoomId: null` 在编辑器内应省略可选 `mainRoomId`，不能写入 `undefined` 后交给严格 JSON 编码器。已有常驻开发服务需重启以加载更新后的 SDK 和服务模块；协议预检通过不证明旧进程已更新。

协议基线由 Home3D 仓库 `docs/specs/2026-11-17-home3d-unified-v4/` 维护。升级需通过本技能行为测试、源世界几何复核，以及目标编辑器的实际保存与重导入；详细步骤见[分层验收](acceptance.md)。
