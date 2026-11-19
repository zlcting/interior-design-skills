# 分层验收

## 1. 包协议

执行 `node scripts/package_home3d.mjs validate /path/to/project.home3d`。使用随技能携带的同一 SDK reader/validator，并按目标编辑器的七项能力校验：structure、GLB、normalization、lighting、device contracts/presentation/simulation。v4 默认是 `kind: project`，验证 `project.json`、`resources.json`、空设备/呈现文档及必需能力声明；旧 v3 校验继续支持。摘要不符、断裂资源/宿主、非法几何或不支持能力均为失败。writer对相同输入的重复输出必须逐字节一致。

SDK校验不代替所有图像解码、视觉效果或编辑器真实操作。

## 2. 源模型与几何

核对权威项目的墙、洞口、房间、家具编号与实际包；同一家具的多个零件只生成一个独立实例。检查平移、负坐标、毫米到米、朝向、洞口偏移及楼层标高，不能仅看生成器自己的对象计数。

逐模型在 Blender 重新导入，对比求值网格位置，沿用0.02mm交换容差；该数值不是测绘精度。同时检查每个 GLB 的 NORMAL 有限且归一化，标记 `triangle-area-v1` 的生成曲面须与最终三角面法线策略一致；逐模型报告保留 normals 和 normal_generation 结果。核对全高窗框、材质、透明玻璃和顶点颜色，验证灯位变换后恢复到原世界位置，灯光随对应实例移动。源文件与旧输出哈希不得变化。

## 3. 实际编辑

在目标系统导入为独立验收场景。家具竖向平移0.1m、旋转12°；墙高增加0.01m；门宽减少至少0.05m并满足编辑器墙边安全间距，记录实际保存值。保存并刷新，核对实际值和实例/宿主关系；导出再导入，重新核对结构、实例和灯光。验收变更仅作用于副本，不改原权威模型。

可对目标 Home3D 源码执行隔离的真实编辑运行时往返测试：

```sh
node tests/verify_home3d_editor.mjs /path/to/project.home3d /path/to/home-3d-uniapp /path/to/new-review-directory
HOME3D_EDITOR_SOURCE=/path/to/home-3d-uniapp python3 -m unittest discover -s tests -p 'test_home3d.py' -v
```

以上命令在技能源码仓库根执行；安装后的技能不携带仓库测试。检查实际导入、家具/墙/洞口修改、重新打开存储、导出再导入，以及几何和灯光 blob、预设与空设备文档保留。该测试单独记录运行时通过，不能冒充 UI 操作或视觉验收。在13100等地址的验收只是当前环境证据，不将其写成所有使用者必须连接的固定服务。

## 4. 视觉与记录

保留全屋和代表房间截图，检查重叠建筑、半截窗框、几何错位、玻璃、AO及局部暖光。整体模型和可编辑原生建筑的材质/剖切有差异时如实记录，不宣称逐像素相同。

`editorReview` 和 `visualReview` 初始均为 `not_reviewed`；完成实际操作后记录目标、时间、输入/包摘要、具体修改、截图及导出检查结果。未做客户视觉确认，不写 user_approved。
