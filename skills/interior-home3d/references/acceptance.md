# 分层验收

## 1. 包协议

执行 `node scripts/package_home3d.mjs validate /path/to/project.home3d`。使用随技能携带的同一 SDK reader/validator，并按目标编辑器的基础七项能力及光影两项能力校验：structure、GLB、normalization、lighting、device contracts/presentation/simulation，另有 render.scene.v1 与 render.pipeline.three-r171-white.v1。v4 默认是 `kind: project`，验证 `project.json`、`resources.json`、空设备/呈现文档及必需能力声明；旧 v3 校验继续支持。摘要不符、断裂资源/宿主、非法几何或不支持能力均为失败。writer对相同输入的重复输出必须逐字节一致。

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

### 全高与剖切展示

比较前先对齐相机、投影、墙体显示模式和渲染管线。保留目标客户端全高画面；若提供剖切预览，再保留开关后的画面，检查家具可见性、墙顶封口、门窗与宿主对齐。剖切开关往返不改变原模型；保存、导出、再导入后核对真实墙高和洞口参数。标准参考捕获不得继承会话剖切或淡出状态。

离线效果图应标注其来源和显示模式，实际导入截图单独交付。只有离线截图或运行时单元测试时，客户端视觉验收仍为 not_reviewed；发现显示差异时按包内描述缺失、资源绑定错误或消费端显示行为分别定位，再修改对应责任方。


## 5. 光影协议与跨端参考图

柔和光影验收使用同一机位的应用前/后图，检查投影边缘、家具接触暗部、墙面层次、玻璃和暖光；记录包内预设摘要、实际VSM半径与采样。导出、刷新与重导入后参数应保留，模型/材质/设备文档与资源blob不得被光影预设改写。客户端使用SDK公共渲染入口；将代码复制到多个客户端不算公共实现接入。

有光影配置时核对实际包内 `rendering.json`、两项必需能力、环境PNG的精确摘要与尺寸、最终工程摘要、逐模型灯策略和参考相机。检查曝光与灯光改动在保存、刷新、导出和重导入后仍生效；几何编辑保留环境及模型blob，烘焙AO失效提示不等于重算完成。真实编辑运行时测试会核对完整光影文档并修改曝光及主光强度，旧包无光影入口时保持旧行为。

SDK升级执行仓库行为测试，并用 `tools/build_home3d_sdk.mjs` 连续构建核对离线bundle摘要；不能手改bundle或只换版本字符串。技能入口与相对引用通过skill-creator校验。本机安装使用先全量预检、保留旧版本备份、更新后 `install.py --check` 按字节核对的安装器。

跨端视觉验收使用实际H5的版本化参考捕获，固定机位、1600×1200、DPR 1、契约初态及时间，等待资源和阴影就绪。桌面/移动两个客户端分别采集全屋与代表房间，再比较原包和重导入包。全图RGB归一化平均绝对误差≤2/255，每像素最大通道误差最近秩P99≤8/255；不能排除阴影或高光区域。另做曝光、主光、投影和环境开关样例，确认配置确实影响像素。未知能力、损坏环境或不足硬件须拒绝严格就绪，不能用降质画面标为通过。

仓库 `tests/verify_home3d_rendering.cjs` 可针对包含 `tests/acceptance/rendering-client.html` 的Home3D开发验收服务采集浏览器证据；Playwright、Chrome与WebKit仅属于开发验收依赖，不进入已安装技能运行时。报告明确模拟还是手机真机，并保留浏览器与GPU诊断。现有独立HTML、H5参考管线、其他GPU分别记录；程序或单机模拟通过不代表所有终端或用户视觉批准。

开发验收命令（在仓库根运行，目标服务必须使用独立验收数据）：

```sh
HOME3D_EDITOR_SOURCE=/path/to/home3d python3 tools/validate_suite.py --output-dir /path/to/new-test-results
node tests/verify_home3d_rendering.cjs /path/to/project.home3d http://localhost:PORT /path/to/new-browser-review
python3 tests/compare_home3d_rendering.py /path/to/new-browser-review
```

浏览器工具会创建验收副本并编辑，不能指向正在协作编辑的生产工程。`HOME3D_PLAYWRIGHT_MODULE` 可指定Playwright模块，`HOME3D_CHROME_EXECUTABLE` 可指定Chrome；WebKit按Playwright安装位置配置。合成夹具只验证算法和对象往返，仍需对实际项目做构图、细节及灯光来源复核。
